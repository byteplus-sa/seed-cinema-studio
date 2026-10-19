from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

SCHEMAS = Path(__file__).resolve().parents[1] / "contracts/schemas"
SCHEMA_NAMES = {
    "editorial": "editorial",
    "sound": "sound-cues",
    "localization": "localization",
}


@dataclass(frozen=True)
class Finding:
    code: str
    path: str
    message: str


def confined_file(project: Path, relative: str) -> Path:
    path = PurePosixPath(relative)
    if (
        not relative or path.is_absolute() or "\\" in relative or "\x00" in relative
        or any(part in ("", ".", "..") for part in relative.split("/"))
    ):
        raise ValueError("Expected a confined project-relative file path")
    root = project.resolve(strict=True)
    resolved = (root / relative).resolve(strict=True)
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise ValueError("Expected a regular file inside the production")
    return resolved


def _finite(value: Any) -> bool:
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, dict):
        return all(_finite(item) for item in value.values())
    if isinstance(value, list):
        return all(_finite(item) for item in value)
    return True


def _schema_findings(kind: str, document: Any) -> list[Finding]:
    if not _finite(document):
        return [Finding("schema", "", "Numbers must be finite")]
    common = json.loads((SCHEMAS / "post-common.schema.json").read_text())
    schema = json.loads((SCHEMAS / f"{SCHEMA_NAMES[kind]}.schema.json").read_text())
    registry: Registry[Any] = Registry().with_resource(
        common["$id"], Resource.from_contents(common),
    )
    validator = Draft202012Validator(schema, registry=registry)
    return [
        Finding("schema", "/".join(map(str, error.absolute_path)), error.message)
        for error in validator.iter_errors(document)
    ]


def _references(value: Any, location: str = "") -> list[tuple[str, dict[str, str]]]:
    if isinstance(value, dict):
        if set(value) == {"path", "sha256"}:
            return [(location, value)]
        return [
            reference
            for key, item in value.items()
            for reference in _references(item, f"{location}/{key}")
        ]
    if isinstance(value, list):
        return [
            reference
            for index, item in enumerate(value)
            for reference in _references(item, f"{location}/{index}")
        ]
    return []


def _asset_findings(project: Path, document: Any) -> list[Finding]:
    findings = []
    for location, reference in _references(document):
        try:
            path = confined_file(project, reference["path"])
            with path.open("rb") as handle:
                digest = hashlib.file_digest(handle, "sha256").hexdigest()
            if digest != reference["sha256"]:
                findings.append(Finding("stale", location, "Referenced file hash changed"))
        except (OSError, ValueError, RuntimeError) as error:
            findings.append(Finding("path", location, str(error)))
    return findings


def _scope(document: dict[str, Any], unit_id: str | None) -> list[Finding]:
    if unit_id is not None and document["unit_id"] != unit_id:
        return [Finding("scope", "unit_id", "Record belongs to another unit")]
    return []


def _duplicates(entries: list[dict[str, Any]], path: str) -> list[Finding]:
    ids = [entry["id"] for entry in entries]
    if len(set(ids)) != len(ids):
        return [Finding("duplicate", path, "Entry IDs must be unique")]
    return []


def validate_editorial(
    project: Path,
    document: Any,
    *,
    unit_id: str | None = None,
    selected_takes: Mapping[str, str] | None = None,
) -> list[Finding]:
    findings = _schema_findings("editorial", document)
    if findings:
        return findings
    findings = _scope(document, unit_id) + _asset_findings(project, document)
    findings.extend(_duplicates(document["entries"], "entries"))
    previous_start = -1.0
    previous_end = -1.0
    for index, entry in enumerate(document["entries"]):
        location = f"entries/{index}"
        start = entry["timeline_start_s"]
        duration = entry["source_out_s"] - entry["source_in_s"]
        end = start + duration
        if (
            duration <= 0 or entry["source_out_s"] > entry["source_duration_s"]
            or end > document["duration_s"] + 0.000001
        ):
            findings.append(Finding("range", location, "Trim or placement exceeds its duration"))
        if start < previous_start:
            findings.append(Finding("order", location, "Entries must follow timeline order"))
        if start < previous_end - 0.000001:
            findings.append(Finding("overlap", location, "Version 1 supports nonoverlapping cuts only"))
        if selected_takes is not None and selected_takes.get(entry["shot_id"]) != entry["take"]["path"]:
            findings.append(Finding("selection", location, "Take is not in the caller's selected unit map"))
        previous_start, previous_end = start, end
    return findings


def _sound_edit(project: Path, document: dict[str, Any]) -> list[Finding]:
    try:
        edit = json.loads(confined_file(project, document["edit"]["path"]).read_text())
    except (OSError, ValueError, RuntimeError) as error:
        return [Finding("edit", "edit", str(error))]
    findings = validate_editorial(project, edit, unit_id=document["unit_id"])
    if findings:
        return findings
    if edit["cut_id"] != document["cut_id"]:
        return [Finding("scope", "edit", "Sound belongs to another cut")]
    if abs(edit["duration_s"] - document["duration_s"]) > 0.000001:
        return [Finding("duration", "duration_s", "Sound duration differs from the referenced edit")]
    return []


def validate_sound(
    project: Path, document: Any, *, unit_id: str | None = None,
) -> list[Finding]:
    findings = _schema_findings("sound", document)
    if findings:
        return findings
    findings = _scope(document, unit_id) + _asset_findings(project, document)
    findings.extend(_sound_edit(project, document))
    findings.extend(_duplicates(document["cues"], "cues"))
    for index, cue in enumerate(document["cues"]):
        if not cue["start_s"] < cue["end_s"] <= document["duration_s"]:
            findings.append(Finding("range", f"cues/{index}", "Cue must fit inside the edit"))
        if cue["kind"] == "silence" and "source" in cue:
            findings.append(Finding("source", f"cues/{index}", "Silence must not bind an audio source"))
    if (
        document["listening"]["status"] == "not_applicable"
        and any(cue["kind"] != "silence" for cue in document["cues"])
    ):
        findings.append(Finding("evidence", "listening", "Audible cues require listening, even without dialogue"))
    return findings


def _preservation(project: Path, document: dict[str, Any]) -> list[Finding]:
    findings = []
    originals = [document["source_master"], *document["source_inputs"]]
    paths: list[Path] = []
    for reference in originals:
        try:
            paths.append(confined_file(project, reference["path"]))
        except (OSError, ValueError, RuntimeError) as error:
            findings.append(Finding("path", reference["path"], str(error)))
    outputs: list[Path] = []
    for index, reference in enumerate(document["outputs"]):
        try:
            path = confined_file(project, reference["path"])
            if any(path.samefile(original) for original in paths):
                findings.append(Finding("preservation", f"outputs/{index}", "Output aliases a preserved source"))
            if any(path.samefile(output) for output in outputs):
                findings.append(Finding("duplicate", f"outputs/{index}", "Outputs alias the same file"))
            outputs.append(path)
        except (OSError, ValueError, RuntimeError) as error:
            findings.append(Finding("path", f"outputs/{index}", str(error)))
    return findings


def validate_localization(
    project: Path, document: Any, *, unit_id: str | None = None,
) -> list[Finding]:
    findings = _schema_findings("localization", document)
    if findings:
        return findings
    findings = _scope(document, unit_id) + _asset_findings(project, document)
    findings.extend(_preservation(project, document))
    verdict = document["lip_sync"]["verdict"]
    allowed = {
        "subtitles": {"not_applicable"},
        "revoice": {"unverified", "approximate"},
        "regenerate": {"unverified", "native"},
    }
    if verdict not in allowed[document["route"]]:
        findings.append(Finding("lip_sync", "lip_sync/verdict", "Verdict conflicts with the selected route"))
    if verdict in {"native", "approximate"} and not document["lip_sync"]["evidence"]:
        findings.append(Finding("evidence", "lip_sync/evidence", "Inspected lip sync requires actual playback evidence"))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate post records without editing or approving production")
    parser.add_argument("kind", choices=SCHEMA_NAMES)
    parser.add_argument("project", type=Path)
    parser.add_argument("--record", required=True, help="Project-relative JSON record")
    parser.add_argument("--unit")
    args = parser.parse_args(argv)
    validators = {
        "editorial": validate_editorial,
        "sound": validate_sound,
        "localization": validate_localization,
    }
    try:
        path = confined_file(args.project, args.record)
        document = json.loads(path.read_text())
        findings = validators[args.kind](args.project, document, unit_id=args.unit)
    except (OSError, ValueError, RuntimeError) as error:
        findings = [Finding("record", args.record, str(error))]
    print(json.dumps({
        "valid": not findings,
        "review_status": "not_evaluated",
        "findings": [asdict(finding) for finding in findings],
    }, indent=2))
    return 2 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
