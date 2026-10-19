from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import quote

import production_context
from production_context import ProductionContext, discover_unit_shots, resolve_context
from production_profiles import resolve_brief
from validate_request import (
    contained_path,
    parse_frontmatter,
    project_market_card_problems,
    project_mode_snapshot,
    schema_findings,
)

HYPERFRAMES_VERSION = "0.8.141"
GSAP_URL = "https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"
STUDIO_DIRNAME = "studio"
FRAMES_MARKER = "<!-- hf-studio-frames -->"
DEFAULT_FPS = 24
LENGTH_TOLERANCE_S = 0.25
CHECK_TIMEOUT_S = 900
RENDER_TIMEOUT_S = 7200
PROBE_TIMEOUT_S = 120
MEDIA_SUFFIXES = {".mp4", ".mov", ".webm", ".m4v"}
SHOWCASE_SKILL = Path(__file__).resolve().parents[1] / "skills/showcase-html"
REVIEW_PAGE_CSS = SHOWCASE_SKILL / "assets/review-page.css"
SHOT_ID_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")
RESERVED_SHOT_IDS = {"main", "root"}
NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
FILENAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
ASSET_PATTERN = re.compile(r"^(.+)__([0-9a-f]{12})(\.[A-Za-z0-9]+)$")
HYPERFRAMES_ENV = {
    "HYPERFRAMES_SKIP_SKILLS": "1",
    "HYPERFRAMES_NO_UPDATE_CHECK": "1",
    "HYPERFRAMES_NO_TELEMETRY": "1",
    "DO_NOT_TRACK": "1",
}
ENV_ALLOWED_KEYS = {
    "PATH",
    "HOME",
    "USER",
    "LOGNAME",
    "SHELL",
    "TMPDIR",
    "LANG",
    "TERM",
    "TZ",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
}
ENV_ALLOWED_PREFIXES = (
    "LC_",
    "NODE_",
    "NPM_",
    "NVM_",
    "XDG_",
    "PRODUCER_",
    "PUPPETEER_",
    "npm_config_",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "NO_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "no_proxy",
    "all_proxy",
)
STAGES = (
    "brief-development",
    "scene-breakdown",
    "canon-elements",
    "storyboard-visual-plan",
    "audio-preparation",
    "shot-generation",
    "assembly-review",
    "delivery",
)
OPTIONAL_STAGES = {"storyboard-visual-plan", "audio-preparation"}
STAGE_LOCKS = {
    "picture": "assembly-review",
    "audio": "assembly-review",
    "final_master": "delivery",
}
LOCK_FIELDS = (
    "decision_id",
    "decision_sha256",
    "result",
    "artifact_path",
    "artifact_sha256",
    "review_path",
    "review_sha256",
    "actor",
    "reason",
)
FRAME_STAGES = {"shot-generation", "assembly-review", "delivery"}
SELECTION_STAGES = {"assembly-review", "delivery"}
DONE_STATUSES = {"complete", "skipped"}
RENDER_QUALITIES = {"draft", "looks", "standard", "delivery", "high"}
DELIVERY_QUALITIES = {"standard", "delivery", "high"}
BLOCKING_CODES = {
    "asset_missing",
    "asset_modified",
    "unmanaged_asset",
    "take_changed",
    "placed_differs_from_selection",
    "not_on_timeline",
    "frame_missing",
    "no_frame",
    "selection_stale",
}
SELECTION_CODE = "selection_pending"
SAFE_HF_COMMANDS = {
    "preview",
    "lint",
    "snapshot",
    "add",
    "catalog",
    "compositions",
    "info",
    "doctor",
    "keyframes",
    "compare",
}
ATTRIBUTE_PATTERN = re.compile(r"""([A-Za-z][\w-]*)=(?:"([^"]*)"|'([^']*)')""")
HOST_PATTERN = re.compile(r"""<div\b[^>]*\bdata-composition-src=["'][^"']*["'][^>]*>""")
ROOT_PATTERN = re.compile(r"""<div\b[^>]*\bdata-composition-id=["']main["'][^>]*>""")
VIDEO_SRC_PATTERN = re.compile(r"""<video\b[^>]*\bsrc=["']assets/([^"']+)["']""")
BULLET_PATTERN = re.compile(
    r"^\s*[-*]\s*(ratio|aspect|resolution)\s*:\s*[`\"']?([^\s`\"']+)",
    re.MULTILINE | re.IGNORECASE,
)
SHOT_GLOBS = ("scenes/scene-*/*/shot.md", "scenes/*/shot.md")
SECTION_START = re.compile(r"(?m)^(?=## Frame \d+)")

Runner = Callable[..., subprocess.CompletedProcess[str]]
Probe = Callable[[Path], float | None]
SizeProbe = Callable[[Path], tuple[int, int] | None]


class StudioError(ValueError):
    pass


@dataclass(frozen=True)
class Shot:
    shot_id: str
    manifest: str
    directory: str
    title: str
    duration_s: float | None
    aspect: str
    resolution: str
    status: str
    selected_variant: str | None
    active_take: str | None
    recommended_take: str | None
    size_declared: bool
    takes: dict[str, dict[str, Any]]
    narrative: str


@dataclass
class SyncReport:
    added: list[str] = field(default_factory=list)
    preserved: list[str] = field(default_factory=list)
    outlined: list[str] = field(default_factory=list)
    skipped: list[dict[str, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PreparedFrame:
    shot: Shot
    filename: str
    sha: str
    asset: str
    duration: float


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


UNCHANGED_UNCHECKED = object()


def atomic_write(
    path: Path, content: str, *, expected: str | None | object = UNCHANGED_UNCHECKED,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".studio-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o644)
        if expected is not UNCHANGED_UNCHECKED:
            require_unchanged(path, expected)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def require_unchanged(path: Path, expected: str | None | object) -> None:
    current = read_text(path) if path.exists() else None
    if current != expected:
        raise StudioError(f"{path.name} changed during the operation; preserve the edit and retry")


def write_checked(path: Path, value: dict[str, Any], schema: str) -> None:
    findings = schema_findings(value, schema)
    if findings:
        raise StudioError(f"{path.name} failed {schema}: {findings[0].message}")
    atomic_write(path, json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def production_root(project: Path | ProductionContext) -> Path:
    return project.production_root if isinstance(project, ProductionContext) else project.resolve()


def studio_context(project: Path | ProductionContext) -> ProductionContext:
    try:
        if isinstance(project, ProductionContext):
            if project._candidate_manifest is not None:
                raise StudioError("A candidate context is read-only; it cannot authorize Studio operations")
            current = resolve_context(project.production_root, project.unit_id)
            if current != project:
                raise StudioError("Stale Studio context; resolve the current unit again")
            return current
        if (project / "studio").is_symlink():
            raise StudioError("studio directory must be a real directory in the project")
        return resolve_context(project)
    except ValueError as error:
        raise StudioError(str(error)) from error


def scope_fields(project: Path | ProductionContext) -> dict[str, Any]:
    context = studio_context(project)
    if context.legacy:
        return {"schema_version": 1}
    return {
        "schema_version": 2,
        "context": context.identity(),
        "scene_ids": list(context.scene_ids),
    }


def scope_matches(project: Path | ProductionContext, record: dict[str, Any]) -> bool:
    expected = scope_fields(project)
    return all(record.get(key) == value for key, value in expected.items())


@contextmanager
def studio_writer(project: Path | ProductionContext) -> Iterator[ProductionContext]:
    context = studio_context(project)
    root = studio_root(context)
    digest = hashlib.sha256(str(root).encode()).hexdigest()
    path = Path(tempfile.gettempdir()) / f"microdrama-studio-{digest}.lock"
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "r+") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield studio_context(context)
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def studio_root(project: Path | ProductionContext) -> Path:
    context = studio_context(project)
    project = context.production_root
    if (production_root(project) / "showcase.json").exists():
        raise StudioError(
            "This project has a showcase.json canvas; Studio is for projects without one"
        )
    root = context.studio_root
    if root.is_symlink() or (
        root.exists() and not root.resolve().is_relative_to(project)
    ):
        raise StudioError("studio directory must be a real directory in the project")
    return root


def studio_path(project: Path | ProductionContext, *parts: str) -> Path:
    root = studio_root(project)
    path = root.joinpath(*parts)
    if not path.resolve().is_relative_to(root.resolve()):
        raise StudioError(f"{'/'.join(parts)} must stay inside the studio directory")
    return path


def dimensions(aspect: str, resolution: str) -> tuple[int, int]:
    match = re.fullmatch(r"(\d+):(\d+)", aspect)
    height_match = re.fullmatch(r"(\d+)p", resolution)
    if not match or not height_match:
        raise StudioError(f"Unsupported aspect or resolution: {aspect} {resolution}")
    ratio_w, ratio_h = int(match[1]), int(match[2])
    short = int(height_match[1])
    if min(ratio_w, ratio_h, short) <= 0:
        raise StudioError("Aspect and resolution must be positive")
    if ratio_w >= ratio_h:
        width, height = round(short * ratio_w / ratio_h), short
    else:
        width, height = short, round(short * ratio_h / ratio_w)
    return width + width % 2, height + height % 2


def number(value: float) -> str:
    return f"{value:.3f}".rstrip("0").rstrip(".")


def shot_narrative(body: str) -> str:
    action = re.search(r"^## Action\s*\n(.+?)(?=^#|\Z)", body, re.MULTILINE | re.DOTALL)
    if action:
        text = action[1]
    else:
        after = re.split(r"^# .+$", body, maxsplit=1, flags=re.MULTILINE)[-1]
        text = after.split("\n## ")[0]
    prose = [
        " ".join(part.split())
        for part in text.split("\n\n")
        if part.strip()
        and not all(
            line.lstrip().startswith(("-", "*", "|"))
            for line in part.splitlines()
            if line.strip()
        )
    ]
    return prose[0][:600] if prose else ""


def read_shot(project: Path | ProductionContext, manifest: Path) -> Shot:
    relative = manifest.relative_to(production_root(project)).as_posix()
    text = read_text(manifest)
    meta = parse_frontmatter(text)
    identifier = meta.get("shot_id") or meta.get("shot") or meta.get("id")
    shot_id = str(identifier or manifest.parent.name)
    if not SHOT_ID_PATTERN.match(shot_id) or shot_id in RESERVED_SHOT_IDS:
        raise StudioError(f"{relative}: invalid or reserved shot id {shot_id!r}")
    body = text.split("---", 2)[-1]
    heading = re.search(r"^# (.+)$", body, re.MULTILINE)
    bullets = {key.lower(): value for key, value in BULLET_PATTERN.findall(body)}
    duration = meta.get("duration_s", meta.get("duration"))
    listed = meta.get("takes")
    takes = {
        str(take["filename"]): take
        for take in (listed if isinstance(listed, list) else [])
        if isinstance(take, dict) and take.get("filename")
    }
    aspect = (
        meta.get("aspect")
        or meta.get("ratio")
        or bullets.get("aspect")
        or bullets.get("ratio")
    )
    resolution = meta.get("resolution") or bullets.get("resolution")
    return Shot(
        shot_id=shot_id,
        manifest=relative,
        directory=manifest.parent.relative_to(production_root(project)).as_posix(),
        title=str(meta.get("title") or (heading[1].strip() if heading else shot_id)),
        duration_s=float(duration) if isinstance(duration, int | float) else None,
        aspect=str(aspect or "16:9"),
        resolution=str(resolution or "720p"),
        status=str(meta.get("status", "")),
        selected_variant=meta.get("selected_variant") or meta.get("selected_take"),
        active_take=meta.get("active_take"),
        recommended_take=meta.get("recommended_take"),
        size_declared=bool(aspect and resolution),
        takes=takes,
        narrative=shot_narrative(body),
    )


def discover_shots(project: Path | ProductionContext) -> list[Shot]:
    context = studio_context(project)
    if context.legacy:
        root = context.production_root
        shots: list[Shot] = []
        seen: dict[str, str] = {}
        for manifest in sorted({path for pattern in SHOT_GLOBS for path in root.glob(pattern)}):
            contained_path(root, manifest.relative_to(root).as_posix())
            shot = read_shot(root, manifest)
            key = shot.shot_id.lower()
            if key in seen:
                raise StudioError(
                    f"Duplicate shot id {shot.shot_id!r} in {seen[key]} and {shot.manifest}"
                )
            seen[key] = shot.manifest
            shots.append(shot)
        return shots
    return [
        read_shot(context.production_root, context.production_root / shot.manifest)
        for shot in discover_unit_shots(context)
    ]


def take_path(shot: Shot, filename: str) -> str:
    if (
        not FILENAME_PATTERN.match(filename)
        or Path(filename).suffix not in MEDIA_SUFFIXES
    ):
        raise StudioError(f"{shot.shot_id}: invalid take filename {filename!r}")
    return f"{shot.directory}/{filename}"


def choose_take(project: Path | ProductionContext, shot: Shot, requested: dict[str, str]) -> str | None:
    if shot.shot_id in requested:
        return requested[shot.shot_id]
    if shot.selected_variant:
        return str(shot.selected_variant)
    if shot.active_take:
        matches = [
            name for name in shot.takes if name.endswith(f"_{shot.active_take}.mp4")
        ]
        if len(matches) == 1:
            return matches[0]
    recommended = shot.recommended_take
    if recommended and (production_root(project) / shot.directory / str(recommended)).is_file():
        return str(recommended)
    return None


def asset_name(sha: str, filename: str) -> str:
    path = Path(filename)
    return f"{path.stem}__{sha[:12]}{path.suffix}"


def split_asset(asset: str) -> tuple[str, str]:
    match = ASSET_PATTERN.match(asset)
    return (match[2], match[1] + match[3]) if match else ("", asset)


def duration_for(shot: Shot, filename: str) -> float:
    entry = shot.takes.get(filename, {})
    value = entry.get("duration_s", shot.duration_s)
    if not isinstance(value, int | float) or value <= 0:
        raise StudioError(f"{shot.shot_id}: no duration recorded for {filename}")
    return float(value)


def probe_duration(path: Path, runner: Runner = subprocess.run) -> float | None:
    try:
        completed = runner(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=PROBE_TIMEOUT_S,
        )
        value = float(json.loads(completed.stdout)["format"]["duration"])
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired):
        return None
    return value if completed.returncode == 0 and value > 0 else None


def probe_size(path: Path, runner: Runner = subprocess.run) -> tuple[int, int] | None:
    try:
        completed = runner(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=PROBE_TIMEOUT_S,
        )
        stream = json.loads(completed.stdout)["streams"][0]
        width, height = int(stream["width"]), int(stream["height"])
    except (
        OSError,
        ValueError,
        KeyError,
        IndexError,
        TypeError,
        subprocess.TimeoutExpired,
    ):
        return None
    ok = completed.returncode == 0 and width > 0 and height > 0
    return (width + width % 2, height + height % 2) if ok else None


def probe_has_audio(path: Path, runner: Runner = subprocess.run) -> bool | None:
    try:
        completed = runner(
            ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type",
             "-of", "json", str(path)],
            capture_output=True, text=True, check=False, timeout=PROBE_TIMEOUT_S,
        )
        streams = json.loads(completed.stdout)["streams"]
        if completed.returncode != 0 or not isinstance(streams, list):
            return None
        kinds = {stream.get("codec_type") for stream in streams if isinstance(stream, dict)}
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired):
        return None
    return "audio" in kinds if "video" in kinds else None


def root_html(width: int, height: int, fps: float) -> str:
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={width}, height={height}" />
    <script src="{GSAP_URL}"></script>
    <style>
      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      html, body {{ margin: 0; width: {width}px; height: {height}px; overflow: hidden; background: #000; }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="1" data-fps="{fps}" data-width="{width}" data-height="{height}">
      {FRAMES_MARKER}
    </div>
    <script>
      const tl = gsap.timeline({{ paused: true }});
      window.__timelines["main"] = tl;
      tl.seek(0);
    </script>
  </body>
</html>
"""


def frame_html(
    shot_id: str, asset: str, duration: float, track: int, width: int, height: int,
    has_audio: bool = True,
) -> str:
    return f"""<!doctype html>
<html>
  <head><meta charset="UTF-8" /></head>
  <body>
    <template>
      <style>
        #root {{ position: absolute; inset: 0; background: #000; }}
        #{shot_id}-video {{ position: absolute; inset: 0; width: 100%; height: 100%; object-fit: contain; }}
      </style>
      <div id="root" data-composition-id="{shot_id}" data-width="{width}" data-height="{height}">
        <video id="{shot_id}-video" src="assets/{asset}" data-start="0" data-duration="{number(duration)}" data-track-index="{track}" data-has-audio="{str(has_audio).lower()}" playsinline></video>
      </div>
      <script>
        window.__timelines = window.__timelines || {{}};
        window.__timelines["{shot_id}"] = gsap.timeline({{ paused: true }});
      </script>
    </template>
  </body>
</html>
"""


def host_html(
    shot_id: str, start: float, duration: float, width: int, height: int
) -> str:
    return (
        f'<div id="{shot_id}" data-composition-id="{shot_id}" '
        f'data-composition-src="compositions/{shot_id}.html" data-start="{number(start)}" '
        f'data-duration="{number(duration)}" data-track-index="1" data-track-kind="graphics" '
        f'data-width="{width}" data-height="{height}"></div>'
    )


def attributes(tag: str) -> dict[str, str]:
    return {match[1]: match[2] or match[3] for match in ATTRIBUTE_PATTERN.finditer(tag)}


def host_tags(html: str) -> list[dict[str, str]]:
    return [attributes(tag) for tag in HOST_PATTERN.findall(html)]


def timing(value: str | None, label: str) -> float:
    try:
        result = float(value if value is not None else 0)
    except ValueError:
        result = math.nan
    if not math.isfinite(result):
        raise StudioError(
            f"{label} uses relative or invalid timing {value!r}; set a numeric data-start and data-duration in Studio"
        )
    return result


def timeline_end(html: str) -> float:
    return max(
        (
            timing(tag.get("data-start"), tag.get("id", "a host"))
            + timing(tag.get("data-duration"), tag.get("id", "a host"))
            for tag in host_tags(html)
        ),
        default=0.0,
    )


def hosted_ids(html: str) -> set[str]:
    return {
        tag["data-composition-id"]
        for tag in host_tags(html)
        if "data-composition-id" in tag
    }


def root_duration(html: str) -> float:
    match = ROOT_PATTERN.search(html)
    if not match:
        raise StudioError("index.html has no root composition with id 'main'")
    try:
        return float(attributes(match[0]).get("data-duration", 0))
    except ValueError:
        return 0.0


def with_root_duration(html: str, total: float) -> str:
    match = ROOT_PATTERN.search(html)
    if not match:
        raise StudioError("index.html has no root composition with id 'main'")
    if re.search(r"data-duration=", match[0]):
        tag = re.sub(
            r"""data-duration=(?:"[^"]*"|'[^']*')""",
            f'data-duration="{number(total)}"',
            match[0],
        )
    else:
        tag = match[0][:-1] + f' data-duration="{number(total)}">'
    return html[: match.start()] + tag + html[match.end() :]


def root_dimensions(html: str) -> tuple[int, int] | None:
    match = ROOT_PATTERN.search(html)
    if not match:
        return None
    found = attributes(match[0])
    try:
        return int(found["data-width"]), int(found["data-height"])
    except (KeyError, ValueError):
        return None


def canvas_dimensions(project: Path | ProductionContext) -> tuple[int, int]:
    index = studio_path(project, "index.html")
    found = root_dimensions(read_text(index)) if index.is_file() else None
    return found or dimensions("16:9", "720p")


def effective_brief(project: Path | ProductionContext) -> dict[str, Any]:
    context = studio_context(project)
    if not context.legacy:
        return production_context.context_fingerprint_payload(context)["effective_settings"]  # type: ignore[no-any-return]
    shared = parse_frontmatter(read_text(context.production_root / "project.md"))
    return resolve_brief(shared)


def brief_body(text: str) -> str:
    if not text.startswith("---"):
        return text
    match = re.match(r"\A---[ \t]*\r?\n.*?\r?\n---(?=\r?\n|$)", text, re.DOTALL)
    if match is None:
        raise StudioError("Malformed brief frontmatter")
    return text[match.end():]


def brief_adapter(project: Path | ProductionContext) -> tuple[Path, str] | None:
    context = studio_context(project)
    if context.legacy:
        return None
    path = studio_path(context, "BRIEF.md")
    if path.is_symlink():
        raise StudioError("BRIEF.md must be a real generated adapter")
    if path.exists():
        existing = read_text(path)
        try:
            metadata = parse_frontmatter(existing)
        except ValueError as error:
            raise StudioError("BRIEF.md is user-authored; reconcile it explicitly") from error
        marker = metadata.get("studio_adapter")
        body = brief_body(existing)
        if (
            not isinstance(marker, dict)
            or marker.get("version") != 1
            or marker.get("body_sha256") != hashlib.sha256(body.encode()).hexdigest()
            or marker.get("metadata_sha256") != adapter_metadata_hash(metadata)
        ):
            raise StudioError("BRIEF.md is user-authored or modified; reconcile it explicitly")
    sources = [context.production_root / "project.md"]
    if context.unit_brief:
        sources.append(context.unit_brief)
    effective = effective_brief(context)
    body = "\n# Generated Studio Brief\n\n" + "\n\n".join(
        brief_body(read_text(source)) for source in sources
    )
    metadata = {
        "workflow": effective["workflow"],
        "flow": "companion",
        "unit_id": context.unit_id,
        "context": context.identity(),
        "delivery": effective["delivery"],
        "source_sha256": {
            source.relative_to(context.production_root).as_posix(): sha256_file(source)
            for source in sources
        },
    }
    metadata["studio_adapter"] = {
        "version": 1,
        "body_sha256": hashlib.sha256(body.encode()).hexdigest(),
        "metadata_sha256": adapter_metadata_hash(metadata),
    }
    return path, "---\n" + json.dumps(metadata, indent=2) + "\n---" + body


def adapter_metadata_hash(metadata: dict[str, Any]) -> str:
    payload = {key: value for key, value in metadata.items() if key != "studio_adapter"}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def init_studio(
    project: Path | ProductionContext,
    aspect: str | None = None,
    resolution: str | None = None,
    fps: float | None = None,
    size: tuple[int, int] | None = None,
) -> Path:
    with studio_writer(project) as context:
        return _init_studio(context, aspect, resolution, fps, size)


def _init_studio(
    project: Path | ProductionContext,
    aspect: str | None = None,
    resolution: str | None = None,
    fps: float | None = None,
    size: tuple[int, int] | None = None,
) -> Path:
    project = studio_context(project)
    root = studio_root(project)
    adapter_path = studio_path(project, "BRIEF.md")
    original_adapter = (
        read_text(adapter_path) if not project.legacy and adapter_path.exists() else None
    )
    adapter = brief_adapter(project)
    delivery = effective_brief(project).get("delivery", {}) if not project.legacy else {}
    for key, requested in (("aspect", aspect), ("resolution", resolution), ("fps", fps)):
        if requested is not None and key in delivery and requested != delivery[key]:
            raise StudioError(f"Explicit {key} conflicts with the unit brief; reconcile its delivery settings")
    width, height = size or (
        (delivery["width"], delivery["height"])
        if "width" in delivery and "height" in delivery
        else dimensions(aspect or delivery.get("aspect", "16:9"),
                        resolution or delivery.get("resolution", "720p"))
    )
    fps = fps if fps is not None else delivery.get("fps", DEFAULT_FPS)
    if not isinstance(fps, int | float) or not math.isfinite(fps) or fps <= 0:
        raise StudioError("Studio fps must be positive and finite")
    if any(not isinstance(value, int) or value <= 0 or value % 2 for value in (width, height)):
        raise StudioError("Studio dimensions must be positive even integers")
    for name in ("assets", "compositions", "renders"):
        directory = studio_path(project, name)
        if directory.is_symlink():
            raise StudioError(f"{name} must be a real directory")
        directory.mkdir(parents=True, exist_ok=True)
    config = root / "hyperframes.json"
    if not config.exists():
        atomic_write(
            config,
            json.dumps(
                {
                    "$schema": "https://hyperframes.heygen.com/schema/hyperframes.json",
                    "paths": {
                        "blocks": "compositions",
                        "components": "compositions/components",
                        "assets": "assets",
                    },
                    "media": {"autoProxy": True},
                },
                indent=2,
            )
            + "\n",
            expected=None,
        )
    index = root / "index.html"
    if not index.exists():
        atomic_write(index, root_html(width, height, fps), expected=None)
    if adapter:
        atomic_write(*adapter, expected=original_adapter)
    return root


def placed_asset(project: Path | ProductionContext, shot_id: str) -> str | None:
    composition = studio_path(project, "compositions", f"{shot_id}.html")
    if not composition.is_file():
        return None
    match = VIDEO_SRC_PATTERN.search(read_text(composition))
    return match[1] if match else None


def split_storyboard(
    existing: str | None, width: int, height: int
) -> tuple[str, list[str]]:
    if not existing:
        return f"---\nformat: {width}x{height}\n---\n\n# Storyboard\n\n", []
    header, *sections = SECTION_START.split(existing)
    return header, sections


def section_shot(section: str) -> str | None:
    match = re.search(r"^- shot: (\S+)", section, re.MULTILINE)
    return match[1] if match else None


def section_narrative(section: str) -> str:
    lines = section.split("\n")[1:]
    index = 0
    while index < len(lines) and lines[index].startswith("- "):
        index += 1
    return "\n".join(lines[index:]).strip()


def frame_section(
    frame_number: int,
    shot: Shot,
    frame_status: str,
    narrative: str,
    take: tuple[str, str, float] | None = None,
) -> str:
    title = " ".join(shot.title.split())
    lines = [f"## Frame {frame_number} — {shot.shot_id}", f"- status: {frame_status}"]
    if take:
        lines.append(f"- src: compositions/{shot.shot_id}.html")
    duration = take[2] if take else shot.duration_s
    if duration:
        lines.append(f"- duration: {number(duration)}s")
    lines += ["- transition_in: cut", f"- scene: {title}", f"- shot: {shot.shot_id}"]
    if take:
        lines += [f"- take: {take[0]}", f"- sha256: {take[1]}"]
    lines.append(f"- approval: {shot.status or 'review'}")
    return "\n".join(lines) + "\n\n" + (narrative + "\n\n" if narrative else "")


def upsert_frame(
    sections: list[str], shot: Shot, take: tuple[str, str, float] | None = None
) -> bool:
    for index, section in enumerate(sections):
        if section_shot(section) != shot.shot_id:
            continue
        if take is None or "- status: outline" not in section:
            return False
        heading = re.match(r"## Frame (\d+)", section)
        frame_number = int(heading[1]) if heading else index + 1
        sections[index] = frame_section(
            frame_number, shot, "built", section_narrative(section), take
        )
        return True
    sections.append(
        frame_section(
            len(sections) + 1,
            shot,
            "built" if take else "outline",
            shot.narrative,
            take,
        )
    )
    return True


def replace_line(section: str, key: str, value: str) -> str:
    lines = section.split("\n")
    for index, text in enumerate(lines):
        if text.startswith(f"- {key}: "):
            lines[index] = f"- {key}: {value}"
            break
    return "\n".join(lines)


def refresh_section_lines(sections: list[str], shots: list[Shot]) -> bool:
    by_id = {shot.shot_id: shot for shot in shots}
    changed = False
    for index, section in enumerate(sections):
        shot = by_id.get(section_shot(section) or "")
        if shot is None:
            continue
        updated = replace_line(section, "approval", shot.status or "review")
        if updated != section:
            sections[index] = updated
            changed = True
    return changed


def set_section_take(
    sections: list[str], shot_id: str, filename: str, sha: str
) -> None:
    for index, section in enumerate(sections):
        if section_shot(section) == shot_id:
            section = replace_line(section, "take", filename)
            sections[index] = replace_line(section, "sha256", sha)


def read_storyboard(
    project: Path | ProductionContext, width: int, height: int
) -> tuple[Path, str, list[str]]:
    path = studio_path(project, "STORYBOARD.md")
    header, sections = split_storyboard(
        read_text(path) if path.exists() else None, width, height
    )
    return path, header, sections


def provenance(project: Path | ProductionContext, shots: list[Shot]) -> dict[str, Any]:
    context = studio_context(project)
    frames = []
    for shot in shots:
        asset = placed_asset(project, shot.shot_id)
        prefix, filename = split_asset(asset or "")
        if asset is None or not prefix:
            continue
        path = studio_path(project, "assets", asset)
        frames.append(
            {
                "shot_id": shot.shot_id,
                "composition": f"compositions/{shot.shot_id}.html",
                "asset": asset,
                "asset_sha256": sha256_file(path) if path.is_file() else prefix,
                "take": filename,
                "manifest": shot.manifest,
                "manifest_sha256": sha256_file(production_root(project) / shot.manifest),
            }
        )
        if not context.legacy:
            prefix_path = context.studio_root.relative_to(context.production_root).as_posix()
            frames[-1]["composition"] = f"{prefix_path}/compositions/{shot.shot_id}.html"
            frames[-1]["asset"] = f"{prefix_path}/assets/{asset}"
            frames[-1]["take"] = take_path(shot, filename)
    return {
        **scope_fields(project),
        "hyperframes_version": HYPERFRAMES_VERSION,
        "frames": frames,
    }


def write_provenance(project: Path | ProductionContext, shots: list[Shot]) -> None:
    write_checked(
        studio_path(project, "provenance.json"),
        provenance(project, shots),
        "studio-provenance.schema.json",
    )


def prepare_frame(
    project: Path | ProductionContext, shot: Shot, filename: str, probe: Probe, report: SyncReport
) -> PreparedFrame:
    source = contained_path(production_root(project), take_path(shot, filename))
    sha = sha256_file(source)
    asset = asset_name(sha, filename)
    target = studio_path(project, "assets", asset)
    if not target.exists():
        shutil.copy2(source, target)
    measured = probe(source)
    try:
        declared: float | None = duration_for(shot, filename)
    except StudioError:
        declared = None
    if measured is None and declared is None:
        raise StudioError(
            f"{shot.shot_id}: no duration recorded for {filename} and ffprobe could not measure it"
        )
    duration = measured if measured is not None else float(declared or 0)
    if (
        measured is not None
        and declared is not None
        and abs(measured - declared) > LENGTH_TOLERANCE_S
    ):
        report.warnings.append(
            f"{shot.shot_id}: {filename} is {number(measured)}s but the manifest says "
            f"{number(declared)}s; the frame uses the measured length"
        )
    return PreparedFrame(shot, filename, sha, asset, duration)


def frame_state(project: Path | ProductionContext, shot: Shot, hosted: set[str]) -> str:
    has_composition = studio_path(
        project, "compositions", f"{shot.shot_id}.html"
    ).exists()
    on_timeline = shot.shot_id in hosted
    if has_composition and on_timeline:
        return "placed"
    if has_composition:
        return "not_on_timeline"
    return "frame_missing" if on_timeline else "absent"


def canvas_size(
    project: Path | ProductionContext,
    shots: list[Shot],
    requested: dict[str, str],
    size_probe: SizeProbe,
) -> tuple[int, int]:
    for shot in shots:
        if shot.size_declared:
            return dimensions(shot.aspect, shot.resolution)
    for shot in shots:
        name = choose_take(project, shot, requested)
        if name is None:
            continue
        measured = size_probe(contained_path(production_root(project), take_path(shot, name)))
        if measured:
            return measured
    return dimensions(shots[0].aspect, shots[0].resolution)


def sync(
    project: Path | ProductionContext,
    requested: dict[str, str] | None = None,
    probe: Probe = probe_duration,
    size_probe: SizeProbe = probe_size,
) -> SyncReport:
    with studio_writer(project) as context:
        return _sync(context, requested, probe, size_probe)


def _sync(
    project: Path | ProductionContext,
    requested: dict[str, str] | None,
    probe: Probe,
    size_probe: SizeProbe,
) -> SyncReport:
    project = studio_context(project)
    requested = requested or {}
    shots = discover_shots(project)
    if not shots:
        raise StudioError(
            "No shot manifests found under scenes/scene-*/*/shot.md or scenes/*/shot.md"
        )
    unknown = sorted(set(requested) - {shot.shot_id for shot in shots})
    if unknown:
        raise StudioError(f"--take names unknown shots: {', '.join(unknown)}")
    first = shots[0]
    context = studio_context(project)
    size = (
        None
        if studio_path(project, "index.html").exists() or not context.legacy
        else canvas_size(project, shots, requested, size_probe)
    )
    if context.legacy:
        _init_studio(project, first.aspect, first.resolution, size=size)
    else:
        required_element_ids(context)
        _init_studio(project)
        with selection_service().writer_lock(context.production_root):
            _sync_elements(context)
    index_path = studio_path(project, "index.html")
    html = read_text(index_path)
    original_html = html
    width, height = root_dimensions(html) or dimensions(first.aspect, first.resolution)
    if FRAMES_MARKER not in html:
        raise StudioError(
            f"index.html lost the {FRAMES_MARKER} marker; add it back inside the root composition"
        )
    storyboard_path, header, sections = read_storyboard(project, width, height)
    original_storyboard = read_text(storyboard_path) if storyboard_path.exists() else None
    report = SyncReport()
    for shot in shots:
        declared = shot.size_declared
        if declared and dimensions(shot.aspect, shot.resolution) != (width, height):
            report.warnings.append(
                f"{shot.shot_id}: {shot.aspect} {shot.resolution} differs from the project canvas {width}x{height}"
            )
    hosted = hosted_ids(html)
    pending: list[PreparedFrame] = []
    storyboard_changed = refresh_section_lines(sections, shots)
    for shot in shots:
        state = frame_state(project, shot, hosted)
        if state != "absent":
            report.preserved.append(shot.shot_id)
            if shot.shot_id in requested:
                report.warnings.append(
                    f"{shot.shot_id}: --take ignored; the frame already exists (use place)"
                )
            if state != "placed":
                report.warnings.append(
                    f"{shot.shot_id}: {state}; fix it in Studio or remove the leftover"
                )
            continue
        filename = choose_take(project, shot, requested)
        if filename is None:
            report.skipped.append(
                {"shot_id": shot.shot_id, "reason": "no selected or active take"}
            )
            if upsert_frame(sections, shot):
                report.outlined.append(shot.shot_id)
                storyboard_changed = True
            continue
        pending.append(prepare_frame(project, shot, filename, probe, report))
    cursor = timeline_end(html)
    compositions: list[tuple[Path, str]] = []
    for ordinal, frame in enumerate(pending):
        has_audio = probe_has_audio(studio_path(project, "assets", frame.asset))
        if has_audio is None:
            report.warnings.append(
                f"{frame.shot.shot_id}: audio stream could not be verified; "
                "retained the legacy audio declaration, inspect before rendering"
            )
        compositions.append((
            studio_path(project, "compositions", f"{frame.shot.shot_id}.html"),
            frame_html(
                frame.shot.shot_id,
                frame.asset,
                frame.duration,
                len(hosted) + ordinal,
                width,
                height,
                has_audio=has_audio is not False,
            ),
        ))
        html = html.replace(
            FRAMES_MARKER,
            host_html(frame.shot.shot_id, cursor, frame.duration, width, height)
            + "\n      "
            + FRAMES_MARKER,
        )
        cursor += frame.duration
        upsert_frame(sections, frame.shot, (frame.filename, frame.sha, frame.duration))
        storyboard_changed = True
        report.added.append(frame.shot.shot_id)
    require_unchanged(index_path, original_html)
    require_unchanged(storyboard_path, original_storyboard)
    for path, _ in compositions:
        require_unchanged(path, None)
    for path, content in compositions:
        atomic_write(path, content, expected=None)
    if storyboard_changed:
        atomic_write(storyboard_path, header + "".join(sections), expected=original_storyboard)
    if pending:
        atomic_write(
            index_path, with_root_duration(html, max(root_duration(html), cursor)),
            expected=original_html,
        )
    write_provenance(project, shots)
    return report


def issue(shot_id: str, code: str, detail: str) -> dict[str, str]:
    return {"shot_id": shot_id, "code": code, "detail": detail}


def frame_issues(project: Path | ProductionContext, shot: Shot, asset: str) -> list[dict[str, str]]:
    prefix, filename = split_asset(asset)
    if not prefix:
        return [
            issue(
                shot.shot_id,
                "unmanaged_asset",
                f"{asset} was not placed by studio_project",
            )
        ]
    path = studio_path(project, "assets", asset)
    if not path.is_file():
        return [issue(shot.shot_id, "asset_missing", asset)]
    found = []
    if not sha256_file(path).startswith(prefix):
        found.append(issue(shot.shot_id, "asset_modified", asset))
    source = production_root(project) / shot.directory / filename
    if source.is_file() and not sha256_file(source).startswith(prefix):
        found.append(
            issue(
                shot.shot_id, "take_changed", f"{filename} changed after it was copied"
            )
        )
    if shot.selected_variant and shot.selected_variant != filename:
        found.append(
            issue(
                shot.shot_id,
                "placed_differs_from_selection",
                f"placed {filename}, manifest selects {shot.selected_variant}",
            )
        )
    elif not shot.selected_variant:
        found.append(
            issue(
                shot.shot_id, SELECTION_CODE, f"{filename} is placed but not selected"
            )
        )
    context = studio_context(project)
    if not context.legacy and shot.selected_variant:
        try:
            metadata = parse_frontmatter(read_text(context.production_root / shot.manifest))
            evidence = metadata.get("selection_evidence", {})
            decision_path = contained_path(context.production_root, evidence["decision_path"])
            if sha256_file(decision_path) != evidence["decision_sha256"]:
                raise StudioError("Selection decision changed")
            decision = json.loads(read_text(decision_path))
            problems = current_decision_problems(context, decision)
            if (
                decision.get("decision_type") != "variant_selection"
                or decision.get("asset_id") != shot.shot_id
                or decision.get("selected_variant") != filename
                or decision.get("subject_path") != take_path(shot, filename)
            ):
                problems.append("Selection decision does not bind the placed take")
            if problems:
                raise StudioError("; ".join(problems))
        except (ValueError, OSError, TypeError, KeyError) as error:
            found.append(issue(shot.shot_id, "selection_stale", str(error)))
    return found


def status(project: Path | ProductionContext) -> dict[str, Any]:
    project = studio_context(project)
    root = studio_root(project)
    shots = discover_shots(project)
    index = root / "index.html"
    hosted = hosted_ids(read_text(index)) if index.is_file() else set()
    issues: list[dict[str, str]] = []
    frames = []
    for shot in shots:
        state = frame_state(project, shot, hosted)
        if state == "absent":
            if shot.selected_variant or shot.active_take:
                issues.append(
                    issue(
                        shot.shot_id, "no_frame", "shot has a take but no Studio frame"
                    )
                )
            continue
        if state != "placed":
            issues.append(
                issue(shot.shot_id, state, "the frame and the timeline host disagree")
            )
        asset = placed_asset(project, shot.shot_id)
        if asset is None:
            continue
        _, filename = split_asset(asset)
        frames.append(
            {
                "shot_id": shot.shot_id,
                "asset": asset,
                "take": filename,
                "selected_variant": shot.selected_variant,
                "on_timeline": state == "placed",
            }
        )
        issues += frame_issues(project, shot, asset)
    compositions = studio_path(project, "compositions")
    known = {shot.shot_id for shot in shots}
    for composition in (
        sorted(compositions.glob("*.html")) if compositions.is_dir() else []
    ):
        if composition.stem not in known:
            issues.append(
                issue(
                    composition.stem,
                    "orphan_frame",
                    "extra composition without a shot manifest (not a shot frame)",
                )
            )
    blocking = [item for item in issues if item["code"] in BLOCKING_CODES]
    return {"ok": not blocking, "frames": frames, "issues": issues}


def blocking_issues(
    result: dict[str, Any], include_selection: bool
) -> list[dict[str, str]]:
    codes = BLOCKING_CODES | ({SELECTION_CODE} if include_selection else set())
    return [item for item in result["issues"] if item["code"] in codes]


def copy_take(project: Path | ProductionContext, shot: Shot, filename: str) -> tuple[str, str]:
    source = contained_path(production_root(project), take_path(shot, filename))
    sha = sha256_file(source)
    asset = asset_name(sha, filename)
    target = studio_path(project, "assets", asset)
    if not target.exists():
        shutil.copy2(source, target)
    return asset, sha


def find_shot(project: Path | ProductionContext, shot_id: str) -> Shot:
    for shot in discover_shots(project):
        if shot.shot_id == shot_id:
            return shot
    raise StudioError(f"Unknown shot {shot_id}")


def candidates(project: Path | ProductionContext, shot_id: str) -> dict[str, Any]:
    with studio_writer(project) as context:
        return _candidates(context, shot_id)


def _candidates(project: Path | ProductionContext, shot_id: str) -> dict[str, Any]:
    project = studio_context(project)
    shot = find_shot(project, shot_id)
    _init_studio(project, shot.aspect if project.legacy else None,
                 shot.resolution if project.legacy else None)
    names = sorted(
        path.name
        for path in (production_root(project) / shot.directory).iterdir()
        if path.suffix in MEDIA_SUFFIXES and FILENAME_PATTERN.match(path.name)
    )
    assets: list[str] = []
    skipped: list[dict[str, str]] = []
    for name in names:
        try:
            assets.append(copy_take(project, shot, name)[0])
        except (StudioError, ValueError, OSError) as error:
            skipped.append({"filename": name, "reason": str(error)})
    return {"assets": assets, "skipped": skipped}


def place_take(
    project: Path | ProductionContext, shot_id: str, filename: str, probe: Probe = probe_duration
) -> dict[str, str]:
    with studio_writer(project) as context:
        return _place_take(context, shot_id, filename, probe)


def _place_take(
    project: Path | ProductionContext, shot_id: str, filename: str, probe: Probe
) -> dict[str, str]:
    project = studio_context(project)
    shot = find_shot(project, shot_id)
    current = placed_asset(project, shot_id)
    if current is None:
        raise StudioError(f"{shot_id} has no frame yet; run sync first")
    composition = studio_path(project, "compositions", f"{shot_id}.html")
    text = read_text(composition)
    original_text = text
    storyboard_path = studio_path(project, "STORYBOARD.md")
    original_storyboard = read_text(storyboard_path) if storyboard_path.exists() else None
    _, header, sections = read_storyboard(project, *canvas_dimensions(project))
    clip = re.search(r"""<video\b[^>]*\bdata-duration=["']([^"']+)["']""", text)
    measured = probe(contained_path(production_root(project), take_path(shot, filename)))
    if measured is None:
        measured = duration_for(shot, filename)
    if clip and abs(measured - timing(clip[1], shot_id)) > LENGTH_TOLERANCE_S:
        raise StudioError(
            f"{filename} is {number(measured)}s but the frame clip is {clip[1]}s; retime it in Studio instead"
        )
    asset, sha = copy_take(project, shot, filename)
    text = text.replace(f"assets/{current}", f"assets/{asset}", 1)
    has_audio = probe_has_audio(studio_path(project, "assets", asset))
    if has_audio is not None:
        for match in re.finditer(r"<video\b[^>]*>", text):
            tag = match[0]
            if attributes(tag).get("src") != f"assets/{asset}":
                continue
            declaration = f'data-has-audio="{str(has_audio).lower()}"'
            updated = (
                re.sub(r"""data-has-audio=(?:"[^"]*"|'[^']*')""", declaration, tag)
                if "data-has-audio" in attributes(tag)
                else tag[:-1] + f" {declaration}>"
            )
            text = text[:match.start()] + updated + text[match.end():]
            break
    require_unchanged(composition, original_text)
    require_unchanged(storyboard_path, original_storyboard)
    atomic_write(composition, text, expected=original_text)
    set_section_take(sections, shot_id, filename, sha)
    atomic_write(storyboard_path, header + "".join(sections), expected=original_storyboard)
    write_provenance(project, discover_shots(project))
    result = {"shot_id": shot_id, "placed": filename, "asset": asset}
    if has_audio is None:
        result["warning"] = "Audio stream could not be verified; inspect before rendering"
    return result


def hyperframes_argv(*arguments: str) -> list[str]:
    return ["npx", "--yes", f"hyperframes@{HYPERFRAMES_VERSION}", *arguments]


def hyperframes_environment() -> dict[str, str]:
    inherited = {
        key: value
        for key, value in os.environ.items()
        if key in ENV_ALLOWED_KEYS or key.startswith(ENV_ALLOWED_PREFIXES)
    }
    return {**inherited, **HYPERFRAMES_ENV}


def run_hyperframes(
    project: Path | ProductionContext,
    arguments: list[str],
    runner: Runner = subprocess.run,
    timeout: int = CHECK_TIMEOUT_S,
) -> subprocess.CompletedProcess[str]:
    root = studio_root(project)
    if not (root / "index.html").is_file():
        raise StudioError("No Studio project; run studio_project.py sync first")
    try:
        return runner(
            hyperframes_argv(arguments[0], str(root), *arguments[1:]),
            capture_output=True,
            text=True,
            env=hyperframes_environment(),
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise StudioError(
            f"hyperframes {arguments[0]} timed out after {timeout}s"
        ) from None


def hf_command(
    project: Path | ProductionContext,
    arguments: list[str],
    runner: Runner = subprocess.run,
    timeout: int = CHECK_TIMEOUT_S,
) -> subprocess.CompletedProcess[str]:
    if not arguments or arguments[0] not in SAFE_HF_COMMANDS:
        raise StudioError(f"hf runs only {sorted(SAFE_HF_COMMANDS)}")
    root = studio_root(project)
    if not (root / "index.html").is_file():
        raise StudioError("No Studio project; run studio_project.py sync first")
    try:
        return runner(
            hyperframes_argv(*arguments),
            capture_output=True,
            text=True,
            env=hyperframes_environment(),
            cwd=root,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise StudioError(
            f"hyperframes {arguments[0]} timed out after {timeout}s"
        ) from None


def check_passed(completed: subprocess.CompletedProcess[str]) -> bool:
    if completed.returncode != 0:
        return False
    try:
        report = json.loads(completed.stdout)
    except (ValueError, TypeError):
        return False
    return report.get("ok") is True and report.get("browserSkipped") is False


def probe_media(path: Path, runner: Runner = subprocess.run) -> dict[str, Any]:
    try:
        completed = runner(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_format",
                "-show_streams",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=PROBE_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        raise StudioError("ffprobe timed out") from None
    if completed.returncode != 0:
        raise StudioError(f"ffprobe failed: {completed.stderr.strip()[:200]}")
    data = json.loads(completed.stdout)
    keys = (
        "codec_type",
        "codec_name",
        "width",
        "height",
        "pix_fmt",
        "r_frame_rate",
        "color_range",
        "color_space",
        "sample_rate",
        "channels",
    )
    return {
        "duration_s": float(data["format"]["duration"]),
        "streams": [
            {key: stream[key] for key in keys if key in stream}
            for stream in data["streams"]
        ],
    }


def tree_digest(project: Path | ProductionContext) -> str:
    root = studio_root(project)
    files = [root / "index.html", root / "hyperframes.json"]
    for name in ("compositions", "assets"):
        directory = studio_path(project, name)
        if directory.is_dir():
            files += sorted(path for path in directory.rglob("*") if path.is_file())
    digest = hashlib.sha256()
    for path in files:
        if not path.resolve().is_relative_to(root.resolve()):
            raise StudioError("Studio render inputs must remain inside the Studio tree")
        digest.update(
            f"{path.relative_to(root).as_posix()}\0{sha256_file(path)}\n".encode()
        )
    return digest.hexdigest()


def record_render(
    project: Path | ProductionContext,
    render_file: Path,
    arguments: list[str],
    runner: Runner = subprocess.run,
    produced_by: str = "manual",
    inputs_digest: str | None = None,
) -> Path:
    with studio_writer(project) as context:
        return _record_render(context, render_file, arguments, runner, produced_by, inputs_digest)


def _record_render(
    project: Path | ProductionContext,
    render_file: Path,
    arguments: list[str],
    runner: Runner,
    produced_by: str,
    inputs_digest: str | None,
) -> Path:
    project = studio_context(project)
    renders = studio_path(project, "renders").resolve()
    output = render_file.resolve()
    if not output.is_file() or not output.is_relative_to(renders):
        raise StudioError("Render must be an existing file inside studio/renders")
    sidecar = output.with_name(output.name + ".render.json")
    if not project.legacy and sidecar.exists():
        raise StudioError("A scoped render record is immutable; choose a new render name")
    record = {
        **scope_fields(project),
        "produced_by": produced_by,
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "output": {
            "path": output.relative_to(production_root(project)).as_posix(),
            "sha256": sha256_file(output),
            "bytes": output.stat().st_size,
            "probe": probe_media(output, runner),
        },
        "hyperframes": {"version": HYPERFRAMES_VERSION, "arguments": arguments},
        "inputs": {
            "index_sha256": sha256_file(studio_path(project, "index.html")),
            "config_sha256": sha256_file(studio_path(project, "hyperframes.json")),
            "studio_sha256": inputs_digest or tree_digest(project),
        },
        "frames": provenance(project, discover_shots(project))["frames"],
    }
    write_checked(sidecar, record, "studio-render-record.schema.json")
    return sidecar


def render(
    project: Path | ProductionContext,
    name: str = "final",
    quality: str = "delivery",
    runner: Runner = subprocess.run,
) -> Path:
    with studio_writer(project) as context:
        return _render(context, name, quality, runner)


def _render(
    project: Path | ProductionContext, name: str, quality: str, runner: Runner
) -> Path:
    project = studio_context(project)
    if not NAME_PATTERN.match(name):
        raise StudioError(f"Invalid render name {name!r}")
    if quality not in RENDER_QUALITIES:
        raise StudioError(f"Quality must be one of {sorted(RENDER_QUALITIES)}")
    if quality in DELIVERY_QUALITIES:
        blocking = blocking_issues(status(project), include_selection=True)
        if blocking:
            raise StudioError(
                f"{quality} renders need a clean status; first issue: "
                f"{blocking[0]['shot_id']} {blocking[0]['code']}"
            )
    output = studio_path(project, "renders", f"{name}.mp4")
    if output.exists():
        raise StudioError(
            f"{output.name} already exists; choose a new --name instead of overwriting"
        )
    before = tree_digest(project)
    try:
        completed = run_hyperframes(
            project,
            ["render", "--quality", quality, "--output", str(output)],
            runner,
            RENDER_TIMEOUT_S,
        )
        if completed.returncode != 0 or not output.is_file():
            detail = (completed.stderr or completed.stdout)[-400:].strip()
            raise StudioError(f"hyperframes render failed: {detail}")
        if tree_digest(project) != before:
            raise StudioError(
                "the Studio project changed during the render; render again"
            )
        return _record_render(
            project, output, ["render", "--quality", quality], runner, "render", before
        )
    except BaseException:
        output.unlink(missing_ok=True)
        raise


def default_stages(project: Path | ProductionContext | None = None) -> dict[str, Any]:
    return {
        **(scope_fields(project) if project is not None else {"schema_version": 1}),
        "current_stage": STAGES[0],
        "stages": [{"id": stage, "status": "pending"} for stage in STAGES],
    }


def read_stages(
    project: Path | ProductionContext, *, allow_stale: bool = False,
) -> dict[str, Any]:
    path = studio_path(project, "stages.json")
    if not path.is_file():
        return default_stages(project)
    value = json.loads(read_text(path))
    findings = schema_findings(value, "studio-stages.schema.json")
    if (
        findings
        or [item["id"] for item in value["stages"]] != list(STAGES)
        or value["current_stage"] not in STAGES
    ):
        raise StudioError("stages.json is invalid; do not edit it by hand")
    context = studio_context(project)
    same_unit = (
        not context.legacy and value.get("schema_version") == 2
        and value.get("context", {}).get("unit_id") == context.unit_id
    )
    if not scope_matches(project, value) and not (allow_stale and same_unit):
        raise StudioError("stages.json context does not match the current unit scope")
    return value  # type: ignore[no-any-return]


def write_stages(project: Path | ProductionContext, value: dict[str, Any]) -> None:
    if not scope_matches(project, value):
        raise StudioError("stages.json context does not match the current unit scope")
    root = studio_root(project)
    root.mkdir(parents=True, exist_ok=True)
    write_checked(root / "stages.json", value, "studio-stages.schema.json")


def stage_entry(value: dict[str, Any], stage_id: str) -> dict[str, Any]:
    if stage_id not in STAGES:
        raise StudioError(f"Unknown stage {stage_id!r}; expected one of {list(STAGES)}")
    return next(item for item in value["stages"] if item["id"] == stage_id)


def require_earlier_done(value: dict[str, Any], stage_id: str, action: str) -> None:
    for earlier in STAGES[: STAGES.index(stage_id)]:
        if stage_entry(value, earlier)["status"] not in DONE_STATUSES:
            raise StudioError(f"Complete {earlier} before {action} {stage_id}")


def advance(value: dict[str, Any], stage_id: str) -> None:
    following = STAGES.index(stage_id) + 1
    if following < len(STAGES) and following > STAGES.index(value["current_stage"]):
        value["current_stage"] = STAGES[following]


def start_stage(project: Path | ProductionContext, stage_id: str) -> dict[str, Any]:
    with studio_writer(project) as context:
        return _start_stage(context, stage_id)


def _start_stage(project: Path | ProductionContext, stage_id: str) -> dict[str, Any]:
    value = read_stages(project)
    entry = stage_entry(value, stage_id)
    require_earlier_done(value, stage_id, "starting")
    if entry["status"] in DONE_STATUSES:
        raise StudioError(f"{stage_id} is already {entry['status']}")
    entry["status"] = "review"
    value["current_stage"] = stage_id
    write_stages(project, value)
    return value


def skip_stage(project: Path | ProductionContext, stage_id: str, reason: str) -> dict[str, Any]:
    with studio_writer(project) as context:
        return _skip_stage(context, stage_id, reason)


def _skip_stage(
    project: Path | ProductionContext, stage_id: str, reason: str
) -> dict[str, Any]:
    value = read_stages(project)
    entry = stage_entry(value, stage_id)
    if stage_id not in OPTIONAL_STAGES:
        raise StudioError(f"Only {sorted(OPTIONAL_STAGES)} can be skipped")
    if not reason.strip():
        raise StudioError("Skipping a stage needs a reason")
    require_earlier_done(value, stage_id, "skipping")
    if entry["status"] == "complete":
        raise StudioError(f"{stage_id} is already complete")
    entry.update(
        status="skipped",
        reason=reason.strip(),
        completed_at=datetime.now(UTC).isoformat(timespec="seconds"),
    )
    entry.pop("evidence", None)
    advance(value, stage_id)
    write_stages(project, value)
    return value


def reopen_stage(project: Path | ProductionContext, stage_id: str) -> dict[str, Any]:
    with studio_writer(project) as context:
        return _reopen_stage(context, stage_id)


def _reopen_stage(project: Path | ProductionContext, stage_id: str) -> dict[str, Any]:
    value = read_stages(project, allow_stale=True)
    if not scope_matches(project, value):
        if stage_id != STAGES[0]:
            raise StudioError("Changed unit context requires reopening brief-development")
        path = studio_path(project, "stages.json")
        history = studio_path(project, "stage-history", f"{sha256_file(path)}.json")
        if not history.exists():
            atomic_write(history, read_text(path))
        value.update(scope_fields(project))
        for item in value["stages"]:
            if item["status"] == "skipped":
                item["status"] = "pending"
                item.pop("reason", None)
                item.pop("completed_at", None)
    stage_entry(value, stage_id)
    for item in value["stages"][STAGES.index(stage_id) :]:
        item.pop("locks", None)
        if item["status"] == "complete":
            item["status"] = "review"
            item.pop("completed_at", None)
            item.pop("evidence", None)
    value["current_stage"] = stage_id
    write_stages(project, value)
    return value


def read_render_records(project: Path | ProductionContext) -> list[tuple[Path, dict[str, Any]]]:
    records = []
    for path in sorted(studio_path(project, "renders").glob("*.render.json")):
        try:
            record = json.loads(read_text(path))
        except (OSError, ValueError):
            continue
        valid = isinstance(record, dict) and not schema_findings(
            record, "studio-render-record.schema.json"
        )
        if valid and scope_matches(project, record):
            records.append((path, record))
    return records


def render_quality(arguments: list[str]) -> str:
    if "--quality" not in arguments:
        return ""
    position = arguments.index("--quality") + 1
    return arguments[position] if position < len(arguments) else ""


def delivery_failures(
    project: Path | ProductionContext, shots: list[Shot],
    render_record: Path | str | None = None,
) -> tuple[list[str], str | None]:
    selected = None
    if render_record is not None:
        selected = Path(render_record)
        if not selected.is_absolute():
            selected = production_root(project) / selected
        selected = selected.resolve()
        if not selected.is_relative_to(studio_path(project, "renders").resolve()):
            return ["render record is outside the selected unit scope"], None
    candidates_ = [
        (path, record)
        for path, record in read_render_records(project)
        if record["produced_by"] == "render"
        and render_quality(record["hyperframes"]["arguments"]) in DELIVERY_QUALITIES
        and (selected is None or path.resolve() == selected)
    ]
    if not candidates_:
        return [
            "no render made by studio_project.py render at standard or higher quality; run studio_project.py render"
        ], None
    path, record = max(
        candidates_, key=lambda item: (item[1]["created_at"], item[0].name)
    )
    name = path.name
    failures = []
    try:
        output = contained_path(production_root(project), record["output"]["path"])
    except ValueError:
        return [f"{name} has an invalid output path"], None
    if not output.resolve().is_relative_to(studio_path(project, "renders").resolve()):
        failures.append(f"{name} output is outside the selected unit scope")
    if not output.is_file() or sha256_file(output) != record["output"]["sha256"]:
        failures.append(f"{name} no longer matches its recorded file")
    if record["inputs"]["studio_sha256"] != tree_digest(project):
        failures.append(
            f"the Studio project changed after {name} was rendered; render again"
        )
    rendered = {(frame["shot_id"], frame["asset_sha256"]) for frame in record["frames"]}
    current = {
        (frame["shot_id"], frame["asset_sha256"])
        for frame in provenance(project, shots)["frames"]
    }
    if rendered != current:
        failures.append(f"{name} does not match the placed takes; render again")
    return failures, path.relative_to(production_root(project)).as_posix()


def delivery_gate(
    project: Path | ProductionContext, render_record: Path | str | None = None,
) -> tuple[list[str], str | None]:
    context = studio_context(project)
    return delivery_failures(context, discover_shots(context), render_record)


def scoped_audio_required(context: ProductionContext, ledger: dict[str, Any]) -> bool:
    paths = set()
    for shot in discover_shots(context):
        asset = placed_asset(context, shot.shot_id)
        if asset:
            paths.add(studio_path(context, "assets", asset))
    digest = tree_digest(context)
    for _, record in read_render_records(context):
        if record["produced_by"] == "render" and record["inputs"]["studio_sha256"] == digest:
            paths.add(contained_path(context.production_root, record["output"]["path"]))
    for stage in ("assembly-review", "delivery"):
        for lock in stage_entry(ledger, stage).get("locks", {}).values():
            paths.add(contained_path(context.production_root, lock["artifact_path"]))
    if not paths:
        raise StudioError("No scoped media streams to verify for audio requirements")
    audio = False
    for path in sorted(paths):
        streams = selection_service().probe_media_streams(path)
        if not isinstance(streams, set) or not streams.intersection({"video", "audio"}):
            raise StudioError(f"Cannot verify media streams for {path.name}")
        audio = audio or "audio" in streams
    return audio


def required_locks(
    ledger: dict[str, Any], stage_id: str, project: Path | ProductionContext | None = None,
) -> list[str]:
    if stage_id == "assembly-review":
        audio = stage_entry(ledger, "audio-preparation")["status"] != "skipped"
        if project is not None:
            context = studio_context(project)
            if not context.legacy:
                audio = scoped_audio_required(context, ledger) or audio
        return ["picture", "audio"] if audio else ["picture"]
    return ["final_master"] if stage_id == "delivery" else []


def current_decision_problems(
    context: ProductionContext, decision: dict[str, Any],
) -> list[str]:
    service = selection_service()
    mode, _ = project_mode_snapshot(context.production_root)
    require_authorized(decision, mode)
    service.validated_decision(
        context.production_root, decision,
        decision["subject_path"], decision.get("subject_sha256", decision.get("selected_sha256")),
        mode, allow_chat=True, context=context, allow_existing=True,
    )
    return []


def lock_failures(
    project: Path | ProductionContext, ledger: dict[str, Any], stage_id: str, delivery_record: str | None
) -> list[str]:
    locks = stage_entry(ledger, stage_id).get("locks", {})
    failures = []
    try:
        required = required_locks(ledger, stage_id, project)
    except (ValueError, OSError) as error:
        return [f"Cannot determine required audio locks: {error}"]
    for kind in required:
        lock = locks.get(kind)
        if lock is None:
            failures.append(f"{kind} lock is required before stage exit")
            continue
        for key, relative in (
            ("artifact_sha256", lock["artifact_path"]),
            ("review_sha256", lock["review_path"]),
            ("decision_sha256", f"decisions/{lock['decision_id']}.json"),
        ):
            try:
                path = contained_path(production_root(project), relative)
            except ValueError:
                failures.append(f"{kind} lock is stale: {relative} is not contained")
                continue
            if not path.is_file() or sha256_file(path) != lock[key]:
                failures.append(f"{kind} lock is stale: {relative} changed")
        context = studio_context(project)
        if not context.legacy:
            try:
                decision_path = contained_path(
                    context.production_root, f"decisions/{lock['decision_id']}.json"
                )
                decision = json.loads(read_text(decision_path))
                failures.extend(current_decision_problems(context, decision))
                if any(decision.get(key) != expected for key, expected in {
                    "subject_path": lock["artifact_path"],
                    "subject_sha256": lock["artifact_sha256"],
                    "review_path": lock["review_path"],
                    "review_sha256": lock["review_sha256"],
                    "stage_id": stage_id,
                    "lock_kind": kind,
                    "actor": lock["actor"],
                    "result": lock["result"],
                }.items()):
                    failures.append(f"{kind} ledger lock does not match its decision")
                problem = lock_subject_problem(context, kind, lock["artifact_path"])
                if problem:
                    failures.append(problem)
                service = selection_service()
                review = service.validated_review(
                    context.production_root, decision["review_path"], decision["review_sha256"],
                    decision["subject_path"], decision["subject_sha256"],
                )
                audio_required = kind == "final_master" and scoped_audio_required(context, ledger)
                service.validate_stage_media(
                    context.production_root, kind, lock["artifact_path"], review,
                    audio_required=audio_required,
                )
            except (ValueError, OSError, KeyError, TypeError) as error:
                failures.append(f"{kind} lock is stale: {error}")
        if kind == "final_master" and delivery_record:
            record = json.loads(read_text(production_root(project) / delivery_record))
            if lock["artifact_path"] != record["output"]["path"]:
                failures.append("the final master lock is not for the delivery render")
    return failures


def stage_gate(
    project: Path | ProductionContext,
    stage_id: str,
    runner: Runner = subprocess.run,
    ledger: dict[str, Any] | None = None,
) -> tuple[list[str], dict[str, Any]]:
    project = studio_context(project)
    ledger = ledger or read_stages(project)
    if not scope_matches(project, ledger):
        raise StudioError("Stage gate ledger belongs to a different context")
    failures: list[str] = []
    evidence: dict[str, Any] = {
        "status_ok": True,
        "check_ran": False,
        "check_ok": False,
        "provenance_sha256": None,
        "index_sha256": None,
    }
    if stage_id == "brief-development":
        try:
            project_mode_snapshot(production_root(project))
            failures.extend(project_market_card_problems(production_root(project)))
        except (ValueError, TypeError, OSError) as error:
            failures.append(f"project.md is not a valid brief record: {error}")
        return failures, evidence
    root = studio_root(project)
    if not (root / "index.html").is_file():
        return ["No Studio project; run studio_project.py sync first"], evidence
    shots = discover_shots(project)
    if not project.legacy and STAGES.index(stage_id) >= STAGES.index("canon-elements"):
        failures += canon_failures(project)
    result = status(project)
    blocking = blocking_issues(result, stage_id in SELECTION_STAGES)
    evidence["status_ok"] = not blocking
    failures += [f"{item['shot_id']}: {item['code']}" for item in blocking]
    if stage_id in FRAME_STAGES:
        on_timeline = {
            frame["shot_id"] for frame in result["frames"] if frame["on_timeline"]
        }
        failures += [
            f"{shot.shot_id}: no placed take"
            for shot in shots
            if shot.shot_id not in on_timeline
        ]
        evidence["check_ran"] = True
        evidence["check_ok"] = check_passed(
            run_hyperframes(project, ["check", "--json"], runner)
        )
        if not evidence["check_ok"]:
            failures.append("hyperframes check failed")
    provenance_path = root / "provenance.json"
    if provenance_path.is_file():
        evidence["provenance_sha256"] = sha256_file(provenance_path)
    evidence["index_sha256"] = sha256_file(root / "index.html")
    named_delivery = None
    if stage_id == "delivery":
        if not project.legacy:
            from deliverables import primary_gate

            named_delivery = primary_gate(project)
        if named_delivery is not None:
            problems, named_evidence = named_delivery
            failures += problems
            evidence.update(named_evidence)
        else:
            problems, record = delivery_failures(project, shots)
            failures += problems
            if record:
                evidence["render_record"] = record
    if named_delivery is None:
        failures += lock_failures(project, ledger, stage_id, evidence.get("render_record"))
    if stage_id == "delivery" and not project.legacy:
        failures += lock_failures(project, ledger, "assembly-review", None)
    return failures, evidence


def complete_stage(
    project: Path | ProductionContext, stage_id: str, runner: Runner = subprocess.run
) -> dict[str, Any]:
    with studio_writer(project) as context:
        return _complete_stage(context, stage_id, runner)


def _complete_stage(
    project: Path | ProductionContext, stage_id: str, runner: Runner
) -> dict[str, Any]:
    value = read_stages(project)
    entry = stage_entry(value, stage_id)
    require_earlier_done(value, stage_id, "completing")
    failures, evidence = stage_gate(project, stage_id, runner, value)
    if failures:
        raise StudioError(f"{stage_id} cannot exit: " + "; ".join(failures))
    entry.update(
        status="complete",
        completed_at=datetime.now(UTC).isoformat(timespec="seconds"),
        evidence=evidence,
    )
    entry.pop("reason", None)
    advance(value, stage_id)
    write_stages(project, value)
    return value


def selection_service() -> Any:
    scripts = SHOWCASE_SKILL / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    return importlib.import_module("selection_service")


def selection_registry(project: Path | ProductionContext, shot: Shot) -> dict[str, Any]:
    variants = {
        path.name: path.relative_to(production_root(project)).as_posix()
        for path in sorted((production_root(project) / shot.directory).iterdir())
        if path.suffix in MEDIA_SUFFIXES
    }
    return {
        shot.shot_id: {
            "manifest": shot.manifest,
            "field": "selected_variant",
            "key": None,
            "stage": None,
            "variants": variants,
            "reviews": {},
        }
    }


def require_authorized(decision: dict[str, Any], mode: str) -> None:
    actor = decision.get("actor")
    if actor == "agent":
        if mode != "approve_for_me":
            raise StudioError(
                "An agent decision is only valid when project.md sets approval_mode: approve_for_me"
            )
        return
    if actor != "user":
        raise StudioError("A decision's actor must be agent or user")
    authorization = decision.get("authorization")
    evidence = (
        authorization.get("evidence") if isinstance(authorization, dict) else None
    )
    chat = isinstance(authorization, dict) and authorization.get("source") == "chat"
    if not chat or not isinstance(evidence, str) or len(evidence.strip()) < 3:
        raise StudioError(
            'A user decision needs authorization {"source": "chat", "evidence": '
            "<the user's own words choosing this take>}"
        )


def record_selection(
    project: Path | ProductionContext, shot_id: str, decision: dict[str, Any]
) -> dict[str, Any]:
    with studio_writer(project) as context:
        return _record_selection(context, shot_id, decision)


def _record_selection(
    project: Path | ProductionContext, shot_id: str, decision: dict[str, Any]
) -> dict[str, Any]:
    project = studio_context(project)
    if not isinstance(decision, dict):
        raise StudioError("A decision file must contain one JSON object")
    mode, _ = project_mode_snapshot(production_root(project))
    require_authorized(decision, mode)
    shot = find_shot(project, shot_id)
    asset = placed_asset(project, shot_id)
    if asset is None:
        raise StudioError(f"{shot_id} has no placed take in Studio")
    prefix, filename = split_asset(asset)
    if decision.get("selected_variant") != filename:
        raise StudioError(
            f"Decision selects {decision.get('selected_variant')!r} but Studio has {filename!r} placed"
        )
    copy = studio_path(project, "assets", asset)
    source = production_root(project) / take_path(shot, filename)
    for path in (copy, source):
        if not prefix or not path.is_file() or not sha256_file(path).startswith(prefix):
            raise StudioError(f"Placed asset no longer matches {filename}")
    registry = selection_registry(project, shot)
    service = selection_service()
    options = {} if project.legacy else {"context": project}
    result = service.apply_selection_batch(
        project.production_root,
        {"registry": registry, "selections": {shot_id: filename}},
        service.revision(project.production_root, registry, **options),
        decisions={shot_id: decision},
        allow_chat=True,
        **options,
    )
    shots = discover_shots(project)
    storyboard_path = studio_path(project, "STORYBOARD.md")
    original_storyboard = read_text(storyboard_path) if storyboard_path.exists() else None
    storyboard_path, header, sections = read_storyboard(
        project, *canvas_dimensions(project)
    )
    if refresh_section_lines(sections, shots):
        atomic_write(storyboard_path, header + "".join(sections), expected=original_storyboard)
    write_provenance(project, shots)
    return result  # type: ignore[no-any-return]


def lock_subject_problem(project: Path | ProductionContext, kind: str, subject: str) -> str | None:
    if kind == "audio":
        return None
    for _, record in read_render_records(project):
        if record["output"]["path"] != subject:
            continue
        quality = render_quality(record["hyperframes"]["arguments"])
        if record["produced_by"] != "render":
            return "the lock subject was not made by studio_project.py render"
        if kind == "final_master" and quality not in DELIVERY_QUALITIES:
            return "a final master lock needs a standard-or-higher render"
        if (
            not studio_context(project).legacy
            and record["inputs"]["studio_sha256"] != tree_digest(project)
        ):
            return "the lock subject was rendered from an older Studio edit"
        return None
    return "the lock subject is not a recorded render"


def record_lock(project: Path | ProductionContext, decision: dict[str, Any]) -> dict[str, Any]:
    with studio_writer(project) as context:
        service = selection_service()
        with service.writer_lock(context.production_root):
            service.recover_selection(context.production_root)
            return _record_lock(context, decision)


def _record_lock(project: Path | ProductionContext, decision: dict[str, Any]) -> dict[str, Any]:
    project = studio_context(project)
    if not isinstance(decision, dict) or decision.get("decision_type") != "stage_lock":
        raise StudioError("A lock needs one stage_lock decision object")
    mode, _ = project_mode_snapshot(production_root(project))
    require_authorized(decision, mode)
    kind, stage_id = decision.get("lock_kind"), decision.get("stage_id")
    if STAGE_LOCKS.get(str(kind)) != stage_id:
        raise StudioError(
            f"A {kind} lock belongs to {STAGE_LOCKS.get(str(kind))}, not {stage_id}"
        )
    ledger = read_stages(project)
    entry = stage_entry(ledger, str(stage_id))
    if ledger["current_stage"] != stage_id or entry["status"] != "review":
        raise StudioError(f"Start {stage_id} before recording its {kind} lock")
    subject = decision.get("subject_path")
    if not isinstance(subject, str):
        raise StudioError("A lock decision needs a subject_path")
    problem = lock_subject_problem(project, str(kind), subject)
    if problem:
        raise StudioError(problem)
    service = selection_service()
    artifact = service.contained_path(production_root(project), subject)
    subject_sha = service.sha256(artifact)
    if decision.get("subject_sha256") != subject_sha:
        raise StudioError("The lock decision's subject_sha256 does not match the file")
    existing = entry.get("locks", {}).get(kind)
    if decision["actor"] == "agent" and existing and existing["actor"] != "agent":
        raise StudioError("An agent cannot replace a user stage lock")
    path, content, digest = service.validated_decision(
        project.production_root, decision, subject, subject_sha, mode, None, True,
        **({} if project.legacy else {"context": project}),
    )
    review = service.validated_review(
        project.production_root,
        decision["review_path"],
        decision["review_sha256"],
        subject,
        subject_sha,
    )
    audio_required = (
        kind == "final_master"
        and stage_entry(ledger, "audio-preparation")["status"] != "skipped"
    )
    if kind == "final_master" and not project.legacy:
        audio_required = scoped_audio_required(project, ledger) or audio_required
    service.validate_stage_media(
        project.production_root, kind, subject, review, audio_required=audio_required
    )
    entry.setdefault("locks", {})[kind] = {
        "decision_id": decision["decision_id"],
        "decision_sha256": digest,
        "result": decision["result"],
        "artifact_path": subject,
        "artifact_sha256": subject_sha,
        "review_path": decision["review_path"],
        "review_sha256": decision["review_sha256"],
        "actor": decision["actor"],
        "reason": decision["reason"],
    }
    findings = schema_findings(ledger, "studio-stages.schema.json")
    if findings:
        raise StudioError(f"stages.json failed its schema: {findings[0].message}")
    service.commit_targets(
        project.production_root,
        {
            path: content,
            project.stages_path.relative_to(project.production_root).as_posix():
                json.dumps(ledger, indent=2, ensure_ascii=False) + "\n",
        },
    )
    return {"decision_id": decision["decision_id"], "decision_path": path, "lock": kind}


def parse_requested(values: list[str]) -> dict[str, str]:
    requested = {}
    for value in values:
        shot_id, separator, filename = value.partition("=")
        if (
            not separator
            or not SHOT_ID_PATTERN.match(shot_id)
            or not FILENAME_PATTERN.match(filename)
        ):
            raise StudioError(f"Expected --take SHOT=FILENAME, got {value!r}")
        requested[shot_id] = filename
    return requested


ELEMENT_ID_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
ELEMENT_VERSION_PATTERN = re.compile(r"_(v\d{2,})$")
ELEMENT_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
LOCKED_PREFIX = "LOCKED_"


def element_document(path: Path) -> dict[str, Any]:
    _, document, _ = selection_service().parse_frontmatter(read_text(path))
    return dict(document)


def element_manifest(project: Path | ProductionContext, element_id: str) -> tuple[Path, dict[str, Any]]:
    if not ELEMENT_ID_PATTERN.fullmatch(element_id):
        raise StudioError(f"Invalid element id: {element_id!r}")
    path = production_root(project) / "elements" / element_id / "element.md"
    if path.is_symlink() or not path.is_file():
        raise StudioError(f"{element_id} has no elements/{element_id}/element.md")
    return path, element_document(path)


def locked_label(element_id: str, source: Path) -> str:
    match = ELEMENT_VERSION_PATTERN.search(source.stem)
    version = match[1] if match else "v00"
    return f"{LOCKED_PREFIX}{element_id}_{version}{source.suffix.lower()}"


def required_element_ids(context: ProductionContext) -> set[str]:
    paths = [context.production_root / f"scenes/{scene}/scene.md" for scene in context.scene_ids]
    paths += [context.production_root / shot.manifest for shot in discover_shots(context)]
    if context.unit_brief:
        paths.insert(0, context.unit_brief)
    required: set[str] = set()
    for path in paths:
        text = read_text(path)
        document = parse_frontmatter(text) if text.startswith("---") else {}
        records = [document]
        if path.name == "scene.md" and re.search(r"^##\s+Shot plan\s*$", text, re.MULTILINE):
            scripts = Path(__file__).resolve().parents[1] / "skills/scene-board-sheet/scripts"
            if str(scripts) not in sys.path:
                sys.path.insert(0, str(scripts))
            board = importlib.import_module("scene_board")
            plan = board.load_shot_plan(board.shot_plan_section(text), path.parent.name)
            records.extend(plan["shots"])
        if "shot_plan" in document:
            plan = document["shot_plan"]
            if not isinstance(plan, dict) or not isinstance(plan.get("shots", []), list):
                raise StudioError(f"{path.name}: invalid shot_plan elements declarations")
            records.extend(plan.get("shots", []))
        for record in records:
            if not isinstance(record, dict):
                raise StudioError(f"{path.name}: invalid shot_plan elements entry")
            for key in ("elements", "required_elements"):
                if key not in record:
                    continue
                elements = record[key]
                if not isinstance(elements, list) or any(
                    not isinstance(item, str) or not ELEMENT_ID_PATTERN.fullmatch(item)
                    for item in elements
                ):
                    raise StudioError(f"{path.name}: {key} must be a list of element IDs")
                required.update(elements)
    return required


def approved_elements(
    project: Path | ProductionContext, required: set[str] | None = None,
) -> list[tuple[str, dict[str, Any], Path]]:
    found = []
    for manifest in sorted((production_root(project) / "elements").glob("*/element.md")):
        element_id = manifest.parent.name
        if required is not None and element_id not in required:
            continue
        if manifest.is_symlink() or not ELEMENT_ID_PATTERN.fullmatch(element_id):
            continue
        document = element_document(manifest)
        selected = document.get("selected_variant")
        if document.get("status") != "approved" or not isinstance(selected, str):
            continue
        source = manifest.parent / selected
        if (
            source.is_symlink()
            or not source.is_file()
            or source.suffix.lower() not in ELEMENT_IMAGE_SUFFIXES
        ):
            continue
        found.append((element_id, document, source))
    return found


def validate_canon_approval(
    production: ProductionContext, element_id: str, document: dict[str, Any], source: Path,
) -> None:
    try:
        evidence = document["selection_evidence"]
        decision_path = contained_path(production.production_root, evidence["decision_path"])
        if sha256_file(decision_path) != evidence["decision_sha256"]:
            raise StudioError("Canon decision changed")
        decision = json.loads(read_text(decision_path))
        current_decision_problems(production, decision)
        if (
            decision.get("decision_type") != "variant_selection"
            or decision.get("asset_id") != element_id
            or decision["subject_path"] != source.relative_to(production.production_root).as_posix()
            or decision.get("selected_variant") != document.get("selected_variant")
            or sha256_file(source) != decision["selected_sha256"]
        ):
            raise StudioError("Canon decision does not match the selected element")
    except (ValueError, OSError, TypeError, KeyError) as error:
        raise StudioError(f"{element_id}: invalid canon approval: {error}") from error


def canon_failures(context: ProductionContext) -> list[str]:
    required = required_element_ids(context)
    approved = approved_elements(context, required)
    failures = [
        f"{element_id}: required canon has no approved selected image"
        for element_id in sorted(required - {item[0] for item in approved})
    ]
    production = production_context.resolve_production_context(context.production_root)
    for element_id, document, source in approved:
        try:
            validate_canon_approval(production, element_id, document, source)
            target = studio_path(context, "assets", locked_label(element_id, source))
            if not target.is_file() or sha256_file(target) != sha256_file(source):
                failures.append(f"{element_id}: Studio canon copy is missing or stale; sync-elements")
        except (ValueError, OSError) as error:
            failures.append(str(error))
    return failures


def element_variant_note(project: Path | ProductionContext, element_id: str, variant: str) -> str:
    review = (
        production_root(project)
        / "elements"
        / element_id
        / f"review_candidate_{Path(variant).stem}.json"
    )
    if review.is_symlink() or not review.is_file():
        return ""
    try:
        document = json.loads(read_text(review))
    except ValueError:
        return ""
    notes = document.get("observations")
    return str(notes[0]) if isinstance(notes, list) and notes else ""


def write_elements_index(
    project: Path | ProductionContext, approved: list[tuple[str, dict[str, Any], Path]]
) -> None:
    lines = [
        "# Elements index",
        "",
        (
            "Studio holds locked elements only (`LOCKED_<element>_<version>.<ext>`). "
            "Other samples stay in `elements/` and appear in `review/elements.html`, "
            "a plain static page opened from disk."
        ),
        "",
        "| Studio file | Element | Source |",
        "| --- | --- | --- |",
    ]
    for element_id, document, source in approved:
        lines.append(
            f"| `{locked_label(element_id, source)}` | {element_id} ({document.get('type', 'element')}) "
            f"| `{source.relative_to(production_root(project)).as_posix()}` |"
        )
    atomic_write(production_root(project) / "elements" / "INDEX.md", "\n".join(lines) + "\n")


def review_page_css() -> str:
    if not REVIEW_PAGE_CSS.is_file():
        raise StudioError(f"Missing shared review stylesheet {REVIEW_PAGE_CSS}")
    return REVIEW_PAGE_CSS.read_text(encoding="utf-8")


def write_elements_page(
    project: Path | ProductionContext,
    approved: list[tuple[str, dict[str, Any], Path]],
    stylesheet: str,
) -> None:
    review = production_root(project) / "review"
    if review.is_symlink():
        raise StudioError("review must be a real directory")
    review.mkdir(exist_ok=True)
    body = [
        "<h1>Elements</h1>",
        '<p class="lede">Locked elements are the ones in HyperFrames Studio. Other samples are kept for reference only.</p>',
    ]
    for element_id, document, source in approved:
        label = locked_label(element_id, source)
        link = f"../{source.relative_to(production_root(project)).as_posix()}"
        body.append(
            f'<section><h2><span class="badge locked">LOCKED</span>{escape(element_id)}</h2>'
            f'<p class="sub">{escape(str(document.get("type", "element")))} · Studio file {escape(label)}</p>'
            f'<figure><img src="{escape(quote(link))}" alt="{escape(element_id)}"></figure>'
        )
        others = [
            name
            for name in document.get("variants", [])
            if isinstance(name, str)
            and name != source.name
            and (source.parent / name).is_file()
        ]
        if others:
            body.append('<div class="row">')
            for name in others:
                note = element_variant_note(project, element_id, name)
                path = f"../elements/{element_id}/{name}"
                caption = f'<span class="badge other">OTHER</span>{escape(name)}'
                if note:
                    caption += f": {escape(note)}"
                body.append(
                    f'<figure><img src="{escape(quote(path))}" alt="{escape(name)}" loading="lazy">'
                    f"<figcaption>{caption}</figcaption></figure>"
                )
            body.append("</div>")
        body.append("</section>")
    page = (
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>Elements</title><link rel="stylesheet" href="elements.css"></head><body><main>'
        + "\n".join(body)
        + "</main></body></html>\n"
    )
    atomic_write(review / "elements.css", stylesheet)
    atomic_write(review / "elements.html", page)


def sync_elements(project: Path | ProductionContext) -> dict[str, Any]:
    if not isinstance(project, ProductionContext) and (project / "production.json").exists():
        result = {
            "units": {
                context.unit_id: sync_elements(context)
                for context in unit_contexts(project) if context.studio_root.is_dir()
            }
        }
        with selection_service().writer_lock(project):
            approved = approved_elements(project)
            write_elements_index(project, approved)
            write_elements_page(project, approved, review_page_css())
        return result
    with (
        studio_writer(project) as context,
        selection_service().writer_lock(context.production_root),
    ):
        return _sync_elements(context)


def _sync_elements(project: Path | ProductionContext) -> dict[str, Any]:
    project = studio_context(project)
    if not studio_root(project).is_dir():
        raise StudioError("This project has no Studio project yet; run init first")
    stylesheet = review_page_css()
    assets = studio_path(project, "assets")
    if assets.is_symlink():
        raise StudioError("assets must be a real directory")
    assets.mkdir(exist_ok=True)
    required = None if project.legacy else required_element_ids(project)
    approved = approved_elements(project, required)
    wanted = {
        locked_label(element_id, source): source for element_id, _, source in approved
    }
    if not project.legacy:
        return sync_scoped_canon(project, approved, wanted)
    removed = []
    for existing in sorted(assets.glob(f"{LOCKED_PREFIX}*")):
        if existing.name not in wanted and (
            existing.is_file() or existing.is_symlink()
        ):
            existing.unlink()
            removed.append(existing.name)
    copied = []
    for name, source in wanted.items():
        target = assets / name
        if target.is_symlink():
            raise StudioError(f"{name} must be a real file")
        if not target.exists() or sha256_file(target) != sha256_file(source):
            shutil.copy2(source, target)
            copied.append(name)
    write_elements_index(project, approved)
    write_elements_page(project, approved, stylesheet)
    return {"copied": copied, "removed": removed, "locked": sorted(wanted)}


def sync_scoped_canon(
    context: ProductionContext,
    approved: list[tuple[str, dict[str, Any], Path]],
    wanted: dict[str, Path],
) -> dict[str, Any]:
    production = production_context.resolve_production_context(context.production_root)
    for element_id, document, source in approved:
        validate_canon_approval(production, element_id, document, source)
    assets = studio_path(context, "assets")
    path = studio_path(context, "canon.json")
    previous = json.loads(read_text(path)) if path.exists() else {"assets": {}}
    if not isinstance(previous, dict) or not isinstance(previous.get("assets"), dict):
        raise StudioError("Invalid Studio canon copy record")
    owned = previous["assets"]
    for name, digest in owned.items():
        if (
            not isinstance(name, str) or Path(name).name != name
            or not name.startswith(LOCKED_PREFIX)
            or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)
        ):
            raise StudioError("Invalid Studio canon asset record")
        target = studio_path(context, "assets", name)
        if target.exists() and (target.is_symlink() or sha256_file(target) != digest):
            raise StudioError(f"{name} has manual changes; reconcile before canon sync")
    for name, source in wanted.items():
        target = assets / name
        if target.is_symlink() or (
            target.exists() and name not in owned and sha256_file(target) != sha256_file(source)
        ):
            raise StudioError(f"{name} is not a managed canon copy; reconcile before sync")
    removed = []
    for name in owned.keys() - wanted.keys():
        (assets / name).unlink(missing_ok=True)
        removed.append(name)
    copied = []
    for name, source in wanted.items():
        target = assets / name
        if not target.exists() or sha256_file(target) != sha256_file(source):
            shutil.copy2(source, target)
            copied.append(name)
    atomic_write(path, json.dumps({
        "schema_version": 1,
        "assets": {name: sha256_file(source) for name, source in wanted.items()},
        "sources": {
            name: source.relative_to(context.production_root).as_posix()
            for name, source in wanted.items()
        },
    }, indent=2) + "\n")
    return {"copied": copied, "removed": sorted(removed), "locked": sorted(wanted)}


def element_registry(
    project: Path | ProductionContext, element_id: str, document: dict[str, Any]
) -> dict[str, Any]:
    directory = production_root(project) / "elements" / element_id
    variants = {
        name: f"elements/{element_id}/{name}"
        for name in document.get("variants", [])
        if isinstance(name, str) and (directory / name).is_file()
    }
    reviews = {
        name: f"elements/{element_id}/review_candidate_{Path(name).stem}.json"
        for name in variants
        if (directory / f"review_candidate_{Path(name).stem}.json").is_file()
    }
    return {
        element_id: {
            "manifest": f"elements/{element_id}/element.md",
            "field": "selected_variant",
            "key": None,
            "stage": None,
            "variants": variants,
            "reviews": reviews,
        }
    }


def record_element_lock(
    project: Path | ProductionContext, element_id: str, decision: dict[str, Any]
) -> dict[str, Any]:
    root = production_root(project)
    scoped = (root / "production.json").exists()
    context = (
        production_context.resolve_production_context(root)
        if scoped else studio_context(project)
    )
    if not isinstance(decision, dict):
        raise StudioError("A decision file must contain one JSON object")
    _, document = element_manifest(project, element_id)
    if not scoped:
        studio_root(project)
    mode, _ = project_mode_snapshot(production_root(project))
    require_authorized(decision, mode)
    review_page_css()
    registry = element_registry(project, element_id, document)
    selected = decision.get("selected_variant")
    if selected not in registry[element_id]["variants"]:
        raise StudioError(f"{selected!r} is not a listed variant of {element_id}")
    service = selection_service()
    options = {"context": context} if scoped else {}
    result = service.apply_selection_batch(
        root,
        {"registry": registry, "selections": {element_id: selected}},
        service.revision(root, registry, **options),
        decisions={element_id: decision},
        allow_chat=True,
        **options,
    )
    return {**result, "studio": sync_elements(root if scoped else project)}


def unit_contexts(project: Path) -> list[ProductionContext]:
    production_context.resolve_production_context(project)
    manifest = json.loads(read_text(project / "production.json"))
    return [resolve_context(project, unit["id"]) for unit in manifest["units"]]


COMMANDS = (
    "init",
    "sync",
    "candidates",
    "place",
    "status",
    "check",
    "render",
    "stage",
    "record-selection",
    "record-lock",
    "lock-element",
    "sync-elements",
    "record-render",
    "hf",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Bridge shot manifests to a HyperFrames Studio project"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    for name in COMMANDS:
        sub = commands.add_parser(name)
        sub.add_argument("project", type=Path)
        sub.add_argument("--unit")
        if name == "init":
            sub.add_argument("--aspect")
            sub.add_argument("--resolution")
            sub.add_argument("--fps", type=float)
        if name == "sync":
            sub.add_argument(
                "--take", action="append", default=[], metavar="SHOT=FILENAME"
            )
        if name in {"candidates", "place", "record-selection"}:
            sub.add_argument("shot_id")
        if name == "place":
            sub.add_argument("filename")
        if name == "lock-element":
            sub.add_argument("element_id")
        if name in {"record-selection", "record-lock", "lock-element"}:
            sub.add_argument("--decision", type=Path, required=True)
        if name == "render":
            sub.add_argument("--name", default="final")
            sub.add_argument(
                "--quality", default="delivery", choices=sorted(RENDER_QUALITIES)
            )
        if name == "stage":
            sub.add_argument(
                "action", choices=["show", "start", "complete", "reopen", "skip"]
            )
            sub.add_argument("stage_id", nargs="?")
            sub.add_argument("--reason", default="")
        if name == "record-render":
            sub.add_argument("render_file", type=Path)
            sub.add_argument("hyperframes_arguments", nargs=argparse.REMAINDER)
        if name == "hf":
            sub.add_argument("hyperframes_arguments", nargs=argparse.REMAINDER)
    return parser


def run_stage(args: argparse.Namespace) -> dict[str, Any]:
    if args.action == "show":
        return read_stages(args.project)
    if not args.stage_id:
        raise StudioError("stage start, complete, reopen and skip need a stage id")
    if args.action == "skip":
        return skip_stage(args.project, args.stage_id, args.reason)
    actions = {"start": start_stage, "complete": complete_stage, "reopen": reopen_stage}
    return actions[args.action](args.project, args.stage_id)


def run(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    command = args.command
    root = args.project.resolve()
    unit = getattr(args, "unit", None)
    if (root / "production.json").exists() and unit is None:
        if command == "status":
            results = {
                context.unit_id: status(context) for context in unit_contexts(root)
            }
            ok = all(result["ok"] for result in results.values())
            return {"ok": ok, "units": results}, 0 if ok else 3
        if command in {"lock-element", "sync-elements"}:
            production_context.resolve_production_context(root)
            if command == "sync-elements":
                return {"ok": True, **sync_elements(root)}, 0
            decision = json.loads(read_text(args.decision))
            return {"ok": True, **record_element_lock(root, args.element_id, decision)}, 0
    project = resolve_context(root, unit)
    args.project = project
    if command == "init":
        shots = discover_shots(project)
        aspect, resolution = args.aspect, args.resolution
        if project.legacy:
            aspect = aspect or (shots[0].aspect if shots else "16:9")
            resolution = resolution or (shots[0].resolution if shots else "720p")
        return {"ok": True, "studio": str(init_studio(
            project, aspect, resolution, getattr(args, "fps", None),
        ))}, 0
    if command == "sync":
        report = sync(project, parse_requested(args.take))
        return {
            "ok": True,
            "added": report.added,
            "preserved": report.preserved,
            "outlined": report.outlined,
            "skipped": report.skipped,
            "warnings": report.warnings,
        }, 0
    if command == "candidates":
        return {"ok": True, **candidates(project, args.shot_id)}, 0
    if command == "place":
        return {"ok": True, **place_take(project, args.shot_id, args.filename)}, 0
    if command == "status":
        result = status(project)
        return result, 0 if result["ok"] else 3
    if command == "check":
        completed = run_hyperframes(project, ["check", "--json"])
        passed = check_passed(completed)
        return {"ok": passed, "output": completed.stdout[-4000:]}, int(not passed)
    if command == "render":
        return {"ok": True, "record": str(render(project, args.name, args.quality))}, 0
    if command == "stage":
        return {"ok": True, **run_stage(args)}, 0
    if command == "record-selection":
        decision = json.loads(read_text(args.decision))
        return {"ok": True, **record_selection(project, args.shot_id, decision)}, 0
    if command == "record-lock":
        decision = json.loads(read_text(args.decision))
        return {"ok": True, **record_lock(project, decision)}, 0
    if command == "lock-element":
        decision = json.loads(read_text(args.decision))
        return {
            "ok": True,
            **record_element_lock(project, args.element_id, decision),
        }, 0
    if command == "sync-elements":
        return {"ok": True, **sync_elements(project)}, 0
    if command == "hf":
        completed = hf_command(project, args.hyperframes_arguments)
        return {
            "ok": completed.returncode == 0,
            "returncode": completed.returncode,
            "stdout": completed.stdout[-8000:],
            "stderr": completed.stderr[-2000:],
        }, int(completed.returncode != 0)
    sidecar = record_render(project, args.render_file, args.hyperframes_arguments)
    return {"ok": True, "record": str(sidecar)}, 0


def main(argv: list[str] | None = None) -> int:
    try:
        result, code = run(build_parser().parse_args(argv))
    except (StudioError, ValueError, OSError, KeyError, TypeError) as error:
        print(json.dumps({"ok": False, "error": str(error)}))
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
