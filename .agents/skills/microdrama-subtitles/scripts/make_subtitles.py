from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import stat
import sys
import unicodedata
from dataclasses import dataclass, replace
from itertools import pairwise
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
DEFAULT_MAX_CHARS = 32
DEFAULT_MAX_CPS = 17.0
LANGUAGE_DEFAULTS = {
    "zh": (16, 9.0),
    "ja": (13, 7.0),
    "ko": (16, 12.0),
}
RTL_LANGUAGES = {"ar", "he", "fa", "ur", "ps", "sd", "ug", "yi", "dv", "ckb"}
RTL_SCRIPTS = {"arab", "hebr", "thaa", "syrc", "nkoo"}
RIGHT_TO_LEFT_MARK = "\u200f"
ZERO_WIDTH_SPACE = "\u200b"
ZERO_WIDTH_JOINER = "\u200d"
ZERO_WIDTH_NON_JOINER = "\u200c"
LANGUAGE_PATTERN = re.compile(r"^[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})*$")
STEM_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
NO_LINE_START = set("、。，．！？：；）］｝】」』》〉”’ー々ゝゞ,.!?:;)]}%…‥")
NO_LINE_END = set("（［｛【「『《〈“‘([{")
UNBROKEN_PAIRS = set("…—‥─")
CLAUSE_END = set(".!?…。！？؟;:,，、؛،")
IDEOGRAPHIC_RANGES = (
    (0x3000, 0x30FF),
    (0x3400, 0x4DBF),
    (0x4E00, 0x9FFF),
    (0xF900, 0xFAFF),
    (0xFF00, 0xFFEF),
    (0x20000, 0x2FFFF),
)
FORMATS = ("srt", "vtt")


class SubtitleError(ValueError):
    pass


@dataclass(frozen=True)
class Line:
    line_id: str
    speaker: str
    start_ms: int
    end_ms: int
    text: dict[str, str]


@dataclass(frozen=True)
class Settings:
    max_chars: int
    max_lines: int
    min_duration_ms: int
    max_duration_ms: int
    max_cps: float
    min_gap_ms: int


@dataclass(frozen=True)
class Token:
    text: str
    glue: str
    width: int


@dataclass(frozen=True)
class Cue:
    start_ms: int
    end_ms: int
    lines: tuple[str, ...]
    source_id: str = ""

    @property
    def characters(self) -> int:
        return sum(
            len(grapheme_clusters(line.replace(RIGHT_TO_LEFT_MARK, "")))
            for line in self.lines
        )


def seconds_to_ms(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SubtitleError(f"{label} must be a number of seconds")
    if not math.isfinite(value):
        raise SubtitleError(f"{label} must be finite")
    return round(value * 1000)


def base_language(language: str) -> str:
    return language.lower().split("-")[0]


def normalize_language(language: str) -> str:
    if not LANGUAGE_PATTERN.match(language):
        raise SubtitleError(f"invalid language code {language!r}")
    return language.lower()


def is_right_to_left(language: str) -> bool:
    parts = language.lower().split("-")
    return parts[0] in RTL_LANGUAGES or any(part in RTL_SCRIPTS for part in parts[1:])


def extends_cluster(cluster: str, char: str) -> bool:
    code = ord(char)
    if unicodedata.category(char) in {"Mn", "Mc", "Me"}:
        return True
    if char in (ZERO_WIDTH_JOINER, ZERO_WIDTH_NON_JOINER):
        return True
    if (
        0x1F3FB <= code <= 0x1F3FF
        or 0x1160 <= code <= 0x11FF
        or 0xD7B0 <= code <= 0xD7FF
    ):
        return True
    last = cluster[-1]
    if last == ZERO_WIDTH_JOINER or unicodedata.combining(last) == 9:
        return True
    regional = 0x1F1E6 <= code <= 0x1F1FF
    return regional and len(cluster) == 1 and 0x1F1E6 <= ord(last) <= 0x1F1FF


def grapheme_clusters(text: str) -> list[str]:
    clusters: list[str] = []
    for char in text:
        if clusters and extends_cluster(clusters[-1], char):
            clusters[-1] += char
        else:
            clusters.append(char)
    return clusters


def is_ideographic(cluster: str) -> bool:
    code = ord(cluster[0])
    return any(low <= code <= high for low, high in IDEOGRAPHIC_RANGES)


def may_break_between(previous: str, current: str) -> bool:
    if not (is_ideographic(previous) or is_ideographic(current)):
        return False
    if current[0] in NO_LINE_START or previous[0] in NO_LINE_END:
        return False
    return not (previous[0] == current[0] and current[0] in UNBROKEN_PAIRS)


def split_word(word: str) -> list[str]:
    clusters = grapheme_clusters(word)
    pieces = [clusters[0]]
    for previous, current in pairwise(clusters):
        if may_break_between(previous, current):
            pieces.append(current)
        else:
            pieces[-1] += current
    return pieces


def tokenize(text: str) -> list[Token]:
    tokens: list[Token] = []
    for index, word in enumerate(text.split()):
        for part_index, part in enumerate(word.split(ZERO_WIDTH_SPACE)):
            if not part:
                continue
            for piece_index, piece in enumerate(split_word(part)):
                glue = " " if index and not part_index and not piece_index else ""
                tokens.append(Token(piece, glue, len(grapheme_clusters(piece))))
    if tokens:
        tokens[0] = Token(tokens[0].text, "", tokens[0].width)
    return tokens


def split_oversize_tokens(
    tokens: list[Token], max_chars: int
) -> tuple[list[Token], int]:
    result: list[Token] = []
    split_count = 0
    for token in tokens:
        if token.width <= max_chars:
            result.append(token)
            continue
        split_count += 1
        clusters = grapheme_clusters(token.text)
        for offset in range(0, len(clusters), max_chars):
            piece = "".join(clusters[offset : offset + max_chars])
            glue = token.glue if offset == 0 else ""
            result.append(Token(piece, glue, len(grapheme_clusters(piece))))
    return result, split_count


def span_width(tokens: list[Token], start: int, stop: int) -> int:
    width = sum(token.width for token in tokens[start:stop])
    return width + sum(len(token.glue) for token in tokens[start + 1 : stop])


def lines_needed(tokens: list[Token], max_chars: int) -> int:
    count = 1
    width = 0
    for token in tokens:
        if width == 0:
            width = token.width
            continue
        candidate = width + len(token.glue) + token.width
        if candidate > max_chars:
            count += 1
            width = token.width
        else:
            width = candidate
    return count


def wrap_tokens(
    tokens: list[Token], max_chars: int, max_lines: int
) -> list[str] | None:
    total = len(tokens)
    needed = lines_needed(tokens, max_chars)
    if needed > max_lines:
        return None
    memo: dict[tuple[int, int], tuple[float, tuple[int, ...]]] = {}

    def best(start: int, lines_left: int) -> tuple[float, tuple[int, ...]]:
        key = (start, lines_left)
        if key in memo:
            return memo[key]
        outcome: tuple[float, tuple[int, ...]] = (math.inf, ())
        if lines_left == 1:
            width = span_width(tokens, start, total)
            if width <= max_chars:
                outcome = (float((max_chars - width) ** 2), (total,))
        else:
            for stop in range(start + 1, total):
                width = span_width(tokens, start, stop)
                if width > max_chars:
                    break
                rest_cost, rest_stops = best(stop, lines_left - 1)
                cost = (max_chars - width) ** 2 + rest_cost
                if cost < outcome[0]:
                    outcome = (cost, (stop, *rest_stops))
        memo[key] = outcome
        return outcome

    _, stops = best(0, needed)
    lines: list[str] = []
    start = 0
    for stop in stops:
        lines.append(
            "".join(token.glue + token.text for token in tokens[start:stop]).strip()
        )
        start = stop
    return lines


def prefer_clause_boundary(tokens: list[Token], start: int, stop: int) -> int:
    full = span_width(tokens, start, stop)
    for candidate in range(stop, start, -1):
        if span_width(tokens, start, candidate) * 2 < full:
            break
        if tokens[candidate - 1].text[-1] in CLAUSE_END:
            return candidate
    return stop


def capacity_chunks(tokens: list[Token], settings: Settings) -> list[list[Token]]:
    chunks: list[list[Token]] = []
    start = 0
    while start < len(tokens):
        stop = start + 1
        while (
            stop < len(tokens)
            and lines_needed(tokens[start : stop + 1], settings.max_chars)
            <= settings.max_lines
        ):
            stop += 1
        if stop < len(tokens):
            stop = prefer_clause_boundary(tokens, start, stop)
        chunks.append(tokens[start:stop])
        start = stop
    return chunks


def split_by_weight(tokens: list[Token], parts: int) -> list[list[Token]]:
    parts = max(1, min(parts, len(tokens)))
    total = span_width(tokens, 0, len(tokens))
    groups: list[list[Token]] = []
    start = 0
    for part in range(1, parts):
        target = total * part / parts
        stop = start + 1
        limit = len(tokens) - (parts - part)
        while stop < limit and span_width(tokens, 0, stop) < target:
            stop += 1
        groups.append(tokens[start:stop])
        start = stop
    groups.append(tokens[start:])
    return groups


def allocate_times(
    chunks: list[list[Token]], start_ms: int, end_ms: int
) -> list[tuple[int, int, list[Token]]]:
    weights = [span_width(chunk, 0, len(chunk)) for chunk in chunks]
    total_weight = sum(weights)
    span = end_ms - start_ms
    allocated: list[tuple[int, int, list[Token]]] = []
    cumulative = 0
    chunk_start = start_ms
    for chunk, weight in zip(chunks, weights):
        cumulative += weight
        chunk_end = start_ms + round(span * cumulative / total_weight)
        allocated.append((chunk_start, chunk_end, chunk))
        chunk_start = chunk_end
    return allocated


def cues_for_line(
    line: Line, language: str, settings: Settings, rtl_marks: bool
) -> tuple[list[Cue], list[str]]:
    warnings: list[str] = []
    tokens, split_count = split_oversize_tokens(
        tokenize(line.text[language]), settings.max_chars
    )
    if split_count:
        warnings.append(
            f"{line.line_id} [{language}]: {split_count} unbroken run(s) longer than "
            f"{settings.max_chars} characters were split; add spaces or U+200B at word boundaries"
        )
    if not tokens:
        raise SubtitleError(f"line {line.line_id} has no {language} text")
    cues: list[Cue] = []
    for chunk_start, chunk_end, chunk in allocate_times(
        capacity_chunks(tokens, settings), line.start_ms, line.end_ms
    ):
        duration = chunk_end - chunk_start
        parts = math.ceil(duration / settings.max_duration_ms)
        groups = split_by_weight(chunk, parts) if parts > 1 else [chunk]
        for group_start, group_end, group in allocate_times(
            groups, chunk_start, chunk_end
        ):
            rendered = wrap_tokens(group, settings.max_chars, settings.max_lines)
            if rendered is None:
                raise SubtitleError(
                    f"{line.line_id} [{language}]: text cannot be wrapped"
                )
            if rtl_marks:
                rendered = [RIGHT_TO_LEFT_MARK + text for text in rendered]
            group_end = min(group_end, group_start + settings.max_duration_ms)
            cues.append(Cue(group_start, group_end, tuple(rendered), line.line_id))
    return cues, warnings


def resolve_overlaps(
    cues: list[Cue], settings: Settings, policy: str, warnings: list[str]
) -> list[Cue]:
    ordered = sorted(cues, key=lambda cue: (cue.start_ms, cue.end_ms))
    for index in range(len(ordered) - 1):
        current, following = ordered[index], ordered[index + 1]
        overlapping = current.end_ms > following.start_ms
        crowded = current.end_ms > following.start_ms - settings.min_gap_ms
        same_line = current.source_id == following.source_id
        if not crowded or (same_line and not overlapping):
            continue
        if overlapping and policy == "error":
            raise SubtitleError(
                f"cues overlap: {current.source_id} ends at {current.end_ms} ms but "
                f"{following.source_id} starts at {following.start_ms} ms"
            )
        new_end = following.start_ms - settings.min_gap_ms
        if new_end <= current.start_ms:
            if overlapping:
                raise SubtitleError(
                    f"cannot trim {current.source_id}: {following.source_id} starts at "
                    f"{following.start_ms} ms, too close to its start {current.start_ms} ms"
                )
            continue
        if overlapping:
            warnings.append(
                f"{current.source_id} trimmed to {new_end} ms to clear {following.source_id}"
            )
        ordered[index] = replace(current, end_ms=new_end)
    return ordered


def extend_for_reading(
    cues: list[Cue], settings: Settings, ceiling_ms: int | None, warnings: list[str]
) -> list[Cue]:
    result: list[Cue] = []
    for index, cue in enumerate(cues):
        wanted = max(
            settings.min_duration_ms,
            math.ceil(cue.characters * 1000 / settings.max_cps),
        )
        wanted = min(wanted, settings.max_duration_ms)
        limit = (
            cues[index + 1].start_ms - settings.min_gap_ms
            if index + 1 < len(cues)
            else ceiling_ms
        )
        new_end = cue.start_ms + wanted
        if limit is not None:
            new_end = min(new_end, limit)
        if new_end > cue.end_ms:
            cue = replace(cue, end_ms=new_end)
        duration = cue.end_ms - cue.start_ms
        if duration < settings.min_duration_ms:
            warnings.append(
                f"{cue.source_id}: cue lasts {duration} ms, below the {settings.min_duration_ms} ms minimum"
            )
        if cue.characters * 1000 > settings.max_cps * duration:
            warnings.append(
                f"{cue.source_id}: reading speed {cue.characters * 1000 / duration:.1f} cps "
                f"exceeds {settings.max_cps:g}"
            )
        result.append(cue)
    return result


def build_cues(
    lines: list[Line],
    language: str,
    settings: Settings,
    *,
    overlap: str = "trim",
    master_duration_ms: int | None = None,
    rtl_marks: bool | None = None,
) -> tuple[list[Cue], list[str]]:
    language = normalize_language(language)
    use_marks = is_right_to_left(language) if rtl_marks is None else rtl_marks
    for line in lines:
        if not line.text.get(language, "").strip():
            raise SubtitleError(
                f"line {line.line_id} ({line.speaker}) has no {language} text"
            )
    warnings: list[str] = []
    cues: list[Cue] = []
    for line in lines:
        line_cues, line_warnings = cues_for_line(line, language, settings, use_marks)
        cues.extend(line_cues)
        warnings.extend(line_warnings)
    cues = resolve_overlaps(cues, settings, overlap, warnings)
    cues = extend_for_reading(cues, settings, master_duration_ms, warnings)
    if master_duration_ms is not None:
        late = [cue for cue in cues if cue.end_ms > master_duration_ms]
        if late:
            raise SubtitleError(
                f"{late[0].source_id} ends at {late[0].end_ms} ms, after the master "
                f"duration {master_duration_ms} ms"
            )
    return cues, warnings


def format_timestamp(milliseconds: int, separator: str) -> str:
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}{separator}{millis:03d}"


def render_srt(cues: list[Cue]) -> str:
    blocks = []
    for number, cue in enumerate(cues, 1):
        start = format_timestamp(cue.start_ms, ",")
        end = format_timestamp(cue.end_ms, ",")
        blocks.append(f"{number}\n{start} --> {end}\n" + "\n".join(cue.lines))
    return "\n\n".join(blocks) + "\n"


def escape_vtt(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_vtt(cues: list[Cue]) -> str:
    blocks = []
    for cue in cues:
        start = format_timestamp(cue.start_ms, ".")
        end = format_timestamp(cue.end_ms, ".")
        body = "\n".join(escape_vtt(text) for text in cue.lines)
        blocks.append(f"{start} --> {end}\n{body}")
    return "WEBVTT\n\n" + "\n\n".join(blocks) + "\n"


def parse_line(entry: Any, index: int, offset_ms: int, source: str) -> Line:
    if not isinstance(entry, dict):
        raise SubtitleError(f"{source}: lines[{index}] must be an object")
    line_id = str(entry.get("id") or f"line-{index + 1:03d}")
    label = f"{source}: {line_id}"
    speaker = entry.get("speaker")
    if not isinstance(speaker, str) or not speaker.strip():
        raise SubtitleError(f"{label} needs a nonempty speaker")
    start_ms = seconds_to_ms(entry.get("start_s"), f"{label} start_s") + offset_ms
    end_ms = seconds_to_ms(entry.get("end_s"), f"{label} end_s") + offset_ms
    if start_ms < 0:
        raise SubtitleError(f"{label} starts before zero after the offset")
    if end_ms <= start_ms:
        raise SubtitleError(f"{label} must end after it starts")
    raw_text = entry.get("text")
    if not isinstance(raw_text, dict) or not raw_text:
        raise SubtitleError(f"{label} needs a text object keyed by language code")
    text: dict[str, str] = {}
    for key, value in raw_text.items():
        if not isinstance(value, str):
            raise SubtitleError(f"{label} text for {key!r} must be a string")
        text[normalize_language(key)] = value.strip()
    return Line(line_id, speaker.strip(), start_ms, end_ms, text)


def load_lines(path: Path, extra_offset_ms: int = 0) -> list[Line]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise SubtitleError(f"{path}: invalid JSON: {error}") from error
    if (
        not isinstance(document, dict)
        or document.get("schema_version") != SCHEMA_VERSION
    ):
        raise SubtitleError(
            f"{path}: expected an object with schema_version {SCHEMA_VERSION}"
        )
    entries = document.get("lines")
    if not isinstance(entries, list) or not entries:
        raise SubtitleError(f"{path}: lines must be a nonempty list")
    offset_ms = extra_offset_ms + seconds_to_ms(
        document.get("offset_s", 0), f"{path} offset_s"
    )
    return [
        parse_line(entry, index, offset_ms, path.name)
        for index, entry in enumerate(entries)
    ]


def resolve_settings(
    language: str,
    *,
    max_chars: int | None = None,
    max_lines: int = 2,
    min_duration_s: float = 1.0,
    max_duration_s: float = 7.0,
    max_cps: float | None = None,
    min_gap_s: float = 0.04,
    chars_for: dict[str, int] | None = None,
    cps_for: dict[str, float] | None = None,
) -> Settings:
    language = normalize_language(language)
    default_chars, default_cps = LANGUAGE_DEFAULTS.get(
        base_language(language), (DEFAULT_MAX_CHARS, DEFAULT_MAX_CPS)
    )
    chars_for = chars_for or {}
    cps_for = cps_for or {}
    chars = chars_for.get(language, chars_for.get(base_language(language)))
    cps = cps_for.get(language, cps_for.get(base_language(language)))
    resolved = Settings(
        max_chars=chars or max_chars or default_chars,
        max_lines=max_lines,
        min_duration_ms=seconds_to_ms(min_duration_s, "min duration"),
        max_duration_ms=seconds_to_ms(max_duration_s, "max duration"),
        max_cps=cps or max_cps or default_cps,
        min_gap_ms=seconds_to_ms(min_gap_s, "min gap"),
    )
    if resolved.max_chars < 1 or resolved.max_lines < 1 or resolved.max_cps <= 0:
        raise SubtitleError("max chars, max lines and max cps must be positive")
    if not 0 < resolved.min_duration_ms <= resolved.max_duration_ms:
        raise SubtitleError("durations must satisfy 0 < min <= max")
    return resolved


def parse_overrides(values: list[str], cast: type) -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    for value in values:
        language, separator, amount = value.partition("=")
        if not separator:
            raise SubtitleError(f"expected LANG=NUMBER, got {value!r}")
        try:
            overrides[normalize_language(language)] = cast(amount)
        except ValueError as error:
            raise SubtitleError(f"expected LANG=NUMBER, got {value!r}") from error
    return overrides


def validate_target(path: Path, overwrite: bool) -> None:
    if path.is_symlink():
        raise SubtitleError(f"{path}: refusing a symlink target")
    if path.exists() and not overwrite:
        raise SubtitleError(
            f"{path} exists; pass --overwrite or choose a new --out-dir"
        )
    if path.exists() and (not path.is_file() or path.stat().st_nlink != 1):
        raise SubtitleError(f"{path}: target must be a regular file without hardlinks")


def write_sidecar(path: Path, content: str, overwrite: bool) -> str:
    validate_target(path, overwrite)
    flags = os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK
    if not overwrite:
        flags |= os.O_EXCL
    descriptor = os.open(path, flags, 0o666)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        metadata = os.fstat(handle.fileno())
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise SubtitleError(f"{path}: target must be a regular file without hardlinks")
        handle.truncate(0)
        handle.write(content)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def generate(arguments: argparse.Namespace) -> dict[str, Any]:
    if not STEM_PATTERN.match(arguments.master_stem):
        raise SubtitleError(f"invalid master stem {arguments.master_stem!r}")
    offset_ms = seconds_to_ms(arguments.offset_s, "offset")
    lines = [
        line for path in arguments.input for line in load_lines(Path(path), offset_ms)
    ]
    master_ms = (
        None
        if arguments.master_duration_s is None
        else seconds_to_ms(arguments.master_duration_s, "master duration")
    )
    chars_for = parse_overrides(arguments.max_chars_for, int)
    cps_for = parse_overrides(arguments.max_cps_for, float)
    rtl_marks = {"auto": None, "on": True, "off": False}[arguments.rtl_marks]
    formats = FORMATS if arguments.format == "both" else (arguments.format,)
    out_dir = Path(arguments.out_dir)
    files: list[dict[str, Any]] = []
    pending: list[tuple[Path, str, str, str, int]] = []
    warnings: list[str] = []
    inputs = {Path(path).resolve() for path in arguments.input}
    for language in arguments.language:
        code = normalize_language(language)
        settings = resolve_settings(
            code,
            max_chars=arguments.max_chars,
            max_lines=arguments.max_lines,
            min_duration_s=arguments.min_duration_s,
            max_duration_s=arguments.max_duration_s,
            max_cps=arguments.max_cps,
            min_gap_s=arguments.min_gap_s,
            chars_for=chars_for,
            cps_for=cps_for,
        )
        cues, language_warnings = build_cues(
            lines,
            code,
            settings,
            overlap=arguments.overlap,
            master_duration_ms=master_ms,
            rtl_marks=rtl_marks,
        )
        warnings.extend(f"[{code}] {warning}" for warning in language_warnings)
        for extension in formats:
            content = render_srt(cues) if extension == "srt" else render_vtt(cues)
            target = out_dir / f"{arguments.master_stem}.{code}.{extension}"
            if target.resolve() in inputs or (
                target.exists() and any(target.samefile(source) for source in inputs)
            ):
                raise SubtitleError(f"{target}: output must not overwrite a dialogue input")
            validate_target(target, arguments.overwrite)
            if any(target == previous[0] for previous in pending):
                raise SubtitleError(f"{target}: duplicate output language")
            pending.append((target, content, code, extension, len(cues)))
    out_dir.mkdir(parents=True, exist_ok=True)
    for target, content, code, extension, cue_count in pending:
        digest = write_sidecar(target, content, arguments.overwrite)
        files.append(
            {
                "path": str(target),
                "language": code,
                "format": extension,
                "cues": cue_count,
                "sha256": digest,
            }
        )
    return {"files": files, "warnings": warnings}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Write per-language SRT/WebVTT sidecars from locked dialogue and measured timing"
    )
    parser.add_argument(
        "--input", action="append", required=True, help="dialogue JSON; repeatable"
    )
    parser.add_argument("--master-stem", required=True)
    parser.add_argument("--language", nargs="+", required=True)
    parser.add_argument("--out-dir", default=".")
    parser.add_argument("--format", choices=["srt", "vtt", "both"], default="srt")
    parser.add_argument("--offset-s", type=float, default=0.0)
    parser.add_argument("--master-duration-s", type=float)
    parser.add_argument("--max-chars", type=int)
    parser.add_argument("--max-lines", type=int, default=2)
    parser.add_argument("--min-duration-s", type=float, default=1.0)
    parser.add_argument("--max-duration-s", type=float, default=7.0)
    parser.add_argument("--max-cps", type=float)
    parser.add_argument("--min-gap-s", type=float, default=0.04)
    parser.add_argument(
        "--max-chars-for", action="append", default=[], metavar="LANG=N"
    )
    parser.add_argument("--max-cps-for", action="append", default=[], metavar="LANG=N")
    parser.add_argument("--overlap", choices=["trim", "error"], default="trim")
    parser.add_argument("--rtl-marks", choices=["auto", "on", "off"], default="auto")
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        result = generate(build_parser().parse_args(argv))
    except (OSError, SubtitleError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
