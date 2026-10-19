from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
from datetime import UTC, datetime
from fractions import Fraction
from pathlib import Path
from typing import Any

import production_context
import studio_project as studio
from production_context import ProductionContext
from validate_request import schema_findings

SPEC_FIELDS = ("id", "unit_id", "cut_id", "kind", "language", "spec")
SCHEMA = "deliverable.schema.json"


def _json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"


def _digest(value: Any) -> str:
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_pairs)
    if not isinstance(value, dict):
        raise TypeError(f"Expected an object: {path.name}")
    _json(value)
    return value


def _path(root: Path, value: str, *, exists: bool = True) -> Path:
    if (
        not isinstance(value, str) or not value or "\\" in value or ":" in value
        or any(ord(character) < 32 for character in value)
        or any(part in {"", ".", ".."} for part in value.split("/"))
        or Path(value).is_absolute()
    ):
        raise ValueError("Expected a safe production-relative path")
    path = root / value
    if not path.resolve().is_relative_to(root):
        raise ValueError("Path escapes production root")
    if any(item.is_symlink() for item in (path, *path.parents) if item != root.parent):
        raise ValueError(f"Symlink paths are not supported: {value}")
    if exists and not path.is_file():
        raise ValueError(f"Missing file: {value}")
    return path


def _relative(root: Path, value: Path | str) -> str:
    path = Path(value)
    relative = path.relative_to(root).as_posix() if path.is_absolute() else str(value)
    _path(root, relative)
    return relative


def _checked(value: dict[str, Any], record_type: str | None = None) -> None:
    findings = schema_findings(value, SCHEMA)
    if findings:
        raise ValueError(f"Invalid deliverable schema: {findings[0].message}")
    if value.get("record_type") != record_type:
        raise ValueError("Unexpected deliverable record type")


def _file(root: Path, relative: str) -> dict[str, str]:
    return {"path": relative, "sha256": studio.sha256_file(_path(root, relative))}


def _history(
    root: Path, document: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    versions: list[dict[str, Any]] = []
    locks: list[dict[str, Any]] = []
    seen: set[str] = set()
    for field, kind, records in (
        ("versions", "delivery_binding", versions), ("locks", "delivery_lock", locks),
    ):
        for index, reference in enumerate(document.get(field, []), 1):
            if reference["path"] in seen:
                raise ValueError("Duplicate immutable history path")
            seen.add(reference["path"])
            path = _path(root, reference["path"])
            if studio.sha256_file(path) != reference["sha256"]:
                raise ValueError(f"Immutable history changed: {reference['path']}")
            record = _read(path)
            _checked(record, kind)
            identifier = record["specification"]["id"] if field == "versions" else record["id"]
            if identifier != document["id"] or reference["version"] != record["version"]:
                raise ValueError("History belongs to another deliverable or version")
            if field == "versions":
                if record["version"] != index or record["specification"]["unit_id"] != document["unit_id"]:
                    raise ValueError("Invalid version order or unit ownership")
            elif (
                record["binding"] not in document.get("versions", [])
                or record["binding"]["version"] != record["version"]
            ):
                raise ValueError("Lock references an unknown or different binding")
            records.append(record)
    return versions, locks


def _load(root: Path, identifier: str) -> tuple[Path, dict[str, Any], ProductionContext]:
    manifest = _read(_path(root, "production.json"))
    entries = manifest.get("deliverables", [])
    matches = [entry for entry in entries if isinstance(entry, dict) and entry.get("id") == identifier]
    if len(matches) != 1:
        raise ValueError(f"Unknown or duplicate deliverable ID: {identifier}")
    entry = matches[0]
    context = production_context.resolve_context(root, entry["unit_id"])
    if context.legacy:
        raise ValueError("Named deliveries require an active production manifest")
    path = _path(root, entry["manifest"])
    if not path.is_relative_to(root / "deliverables"):
        raise ValueError("Deliverable manifests must live under deliverables/")
    document = _read(path)
    if document.get("cut_id") != "main":
        raise ValueError("Alternate cuts are unsupported; cut_id must be main")
    _checked(document)
    if document["id"] != identifier or document["unit_id"] != entry["unit_id"]:
        raise ValueError("Deliverable ID or unit differs from production.json")
    languages = [(item["mode"], item["language"]) for item in document["spec"]["subtitles"]]
    if len(set(languages)) != len(languages):
        raise ValueError("Duplicate subtitle language requirement")
    return path, document, context


def probe_media(path: Path, runner: studio.Runner = subprocess.run) -> dict[str, Any]:
    try:
        result = runner(
            ["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
            capture_output=True, text=True, check=False, timeout=studio.PROBE_TIMEOUT_S,
        )
        if result.returncode:
            raise ValueError("Media probe failed")
        data = json.loads(result.stdout)
        duration = float(data["format"]["duration"])
        keys = (
            "codec_type", "codec_name", "width", "height", "pix_fmt", "r_frame_rate",
            "avg_frame_rate", "color_range", "color_space", "sample_rate", "channels",
        )
        streams = []
        if not isinstance(data["streams"], list):
            raise TypeError("Media streams must be an array")
        for stream in data["streams"]:
            if not isinstance(stream, dict) or not isinstance(stream.get("tags", {}), dict):
                raise TypeError("Malformed media stream")
            if stream.get("codec_type") not in {"audio", "video", "subtitle"}:
                raise ValueError("Unsupported media stream type")
            item = {key: stream[key] for key in keys if key in stream}
            if "language" in stream.get("tags", {}):
                item["language"] = stream["tags"]["language"]
            streams.append(item)
        if not math.isfinite(duration) or duration <= 0 or not streams:
            raise ValueError("Media needs a positive duration and streams")
        return {"duration_s": duration, "streams": streams}
    except (OSError, subprocess.TimeoutExpired, KeyError, TypeError) as error:
        raise ValueError("Media inspection is unavailable or malformed") from error


def verify_decode(path: Path, runner: studio.Runner = subprocess.run) -> None:
    try:
        result = runner(
            ["ffmpeg", "-nostdin", "-v", "error", "-xerror", "-err_detect", "explode",
             "-i", str(path), "-map", "0:v", "-map", "0:a?", "-f", "null", "-"],
            capture_output=True, text=True, check=False, timeout=studio.RENDER_TIMEOUT_S,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ValueError("Full media decode is unavailable or timed out") from error
    if result.returncode != 0:
        raise ValueError("Full audio/video decode failed")


def _streams_match(spec: dict[str, Any], media: dict[str, Any]) -> None:
    streams = media["streams"]
    video = [stream for stream in streams if stream.get("codec_type") == "video"]
    audio = [stream for stream in streams if stream.get("codec_type") == "audio"]
    subtitles = [stream for stream in streams if stream.get("codec_type") == "subtitle"]
    if len(video) != 1:
        raise ValueError("Delivery requires exactly one video stream")
    if any(video[0].get(key) != spec[key] for key in ("width", "height")):
        raise ValueError("Video dimensions do not match the delivery specification")
    try:
        expected = Fraction(str(spec["fps"]))
        rates = [video[0]["r_frame_rate"]]
        if video[0].get("avg_frame_rate") not in (None, "0/0"):
            rates.append(video[0]["avg_frame_rate"])
        if any(abs(float(Fraction(str(rate)) - expected)) > 0.001 for rate in rates):
            raise ValueError("Frame rate does not match the delivery specification")
    except (KeyError, ZeroDivisionError) as error:
        raise ValueError("Missing or invalid video frame rate") from error
    requirements = spec["audio"]
    if bool(audio) != requirements["required"]:
        raise ValueError("Audio streams do not match the delivery specification")
    for stream in audio:
        for key in ("channels", "sample_rate", "language"):
            if key in requirements and str(stream.get(key)) != str(requirements[key]):
                raise ValueError(f"Audio {key} does not match the delivery specification")
    expected_languages = sorted(
        item["language"] for item in spec["subtitles"] if item["mode"] == "embedded"
    )
    if sorted(str(stream.get("language", "")) for stream in subtitles) != expected_languages:
        raise ValueError("Embedded subtitle languages do not match the specification")


def _render(root: Path, context: ProductionContext, relative: str) -> dict[str, Any]:
    path = _path(root, relative)
    failures, selected = studio.delivery_gate(context, path)
    if failures or selected != relative:
        raise ValueError("; ".join(failures) or "Delivery gate returned another render record")
    record = _read(path)
    if record.get("schema_version") != 2 or record.get("context") != context.identity():
        raise ValueError("Render requires the exact current unit context")
    if record.get("scene_ids") != list(context.scene_ids) or record.get("cut_id", "main") != "main":
        raise ValueError("Render membership or cut differs from the named delivery")
    output = _path(root, record["output"]["path"])
    if output.stat().st_size != record["output"]["bytes"]:
        raise ValueError("Rendered output size changed")
    return record


def _dependencies(root: Path, document: dict[str, Any], record: dict[str, Any]) -> dict[str, str]:
    dependencies: dict[str, str] = {}
    for frame in record["frames"]:
        manifest = _path(root, frame["manifest"])
        digest = studio.sha256_file(manifest)
        if digest != frame["manifest_sha256"]:
            raise ValueError("Rendered shot manifest changed")
        dependencies[frame["manifest"]] = digest
        take = _path(root, frame["take"])
        take_digest = studio.sha256_file(take)
        if not take_digest.startswith(frame["asset_sha256"]):
            raise ValueError("Rendered take changed")
        dependencies[frame["take"]] = take_digest
    for subtitle in document["spec"]["subtitles"]:
        if subtitle["mode"] == "sidecar":
            path = _path(root, subtitle["path"])
            if path.suffix.lower() not in {".srt", ".vtt"} or not path.read_text(encoding="utf-8").strip():
                raise ValueError("Subtitle sidecar must be a nonempty UTF-8 SRT or VTT")
            dependencies[subtitle["path"]] = studio.sha256_file(path)
    return dependencies


def _binding_problems(
    root: Path, document: dict[str, Any], context: ProductionContext, version: dict[str, Any],
) -> list[str]:
    problems = []
    if version["specification"] != {key: document[key] for key in SPEC_FIELDS}:
        problems.append("Delivery specification changed")
    if version["context"] != context.identity() or version["scene_ids"] != list(context.scene_ids):
        problems.append("Delivery source context changed")
    for reference in (version["render_record"], version["output"]):
        try:
            if _file(root, reference["path"]) != reference:
                problems.append(f"Bound artifact changed: {reference['path']}")
        except (OSError, ValueError) as error:
            problems.append(str(error))
    for relative, digest in version["dependencies"].items():
        try:
            if studio.sha256_file(_path(root, relative)) != digest:
                problems.append(f"Delivery dependency changed: {relative}")
        except (OSError, ValueError) as error:
            problems.append(str(error))
    try:
        _render(root, context, version["render_record"]["path"])
        if studio.tree_digest(context) != version["studio_sha256"]:
            problems.append("Bound Studio tree changed")
    except (OSError, ValueError, TypeError, KeyError) as error:
        problems.append(str(error))
    return problems


def _prerequisites(
    context: ProductionContext, runner: studio.Runner | None = None,
) -> tuple[str, dict[str, Any]]:
    ledger = studio.read_stages(context)
    studio.require_earlier_done(ledger, "delivery", "lock a named delivery")
    if any(
        stage["status"] == "skipped" and stage["id"] not in studio.OPTIONAL_STAGES
        for stage in ledger["stages"]
    ):
        raise ValueError("A required production stage cannot be skipped")
    delivery = studio.stage_entry(ledger, "delivery")
    if delivery["status"] not in {"review", "complete"}:
        raise ValueError("Start the delivery stage before locking a named delivery")
    if runner is not None:
        failures, evidence = studio.stage_gate(context, "assembly-review", runner, ledger)
    else:
        failures = studio.lock_failures(context, ledger, "assembly-review", None)
        failures += [f"{item['shot_id']}: {item['code']}" for item in
                     studio.blocking_issues(studio.status(context), include_selection=True)]
        evidence = {}
    brief_failures, _ = studio.stage_gate(context, "brief-development", ledger=ledger)
    failures += brief_failures
    if failures:
        raise ValueError("; ".join(failures))
    return _digest(ledger["stages"][:-1]), evidence


def _decision(
    root: Path, context: ProductionContext, reference: dict[str, Any],
    version: dict[str, Any], decision: dict[str, Any],
) -> tuple[str, str, str]:
    if (
        decision.get("schema_version") != 2 or decision.get("decision_type") != "stage_lock"
        or decision.get("lock_kind") != "final_master" or decision.get("stage_id") != "delivery"
        or decision.get("context") != context.identity()
    ):
        raise ValueError("Named delivery needs a current version-2 unit final_master decision")
    if decision.get("upstream_sha256", {}).get(reference["path"]) != reference["sha256"]:
        raise ValueError("Final decision must bind the immutable named delivery version")
    mode, _ = studio.project_mode_snapshot(root)
    studio.require_authorized(decision, mode)
    service = studio.selection_service()
    subject = version["output"]
    if decision.get("subject_sha256") != subject["sha256"]:
        raise ValueError("Final decision does not bind the output hash")
    result = service.validated_decision(
        root, decision, subject["path"], subject["sha256"], mode,
        allow_chat=True, context=context, allow_existing=True,
    )
    review = service.validated_review(
        root, decision["review_path"], decision["review_sha256"], subject["path"], subject["sha256"],
    )
    if (
        any(stream["codec_type"] == "audio" for stream in version["media"]["streams"])
        and "listen" not in review["inspection_method"].lower()
    ):
        raise ValueError("Audiovisual final delivery requires listening evidence")
    return str(result[0]), str(result[1]), str(result[2])


def status(root: Path, identifier: str) -> dict[str, Any]:
    root = root.resolve(strict=True)
    path, document, context = _load(root, identifier)
    findings: list[str] = []
    history_findings: list[str] = []
    versions: list[dict[str, Any]] = []
    locks: list[dict[str, Any]] = []
    try:
        versions, locks = _history(root, document)
    except (OSError, ValueError, TypeError, KeyError) as error:
        findings.append(str(error))
    current_versions = {len(versions)}
    if locks:
        current_versions.add(locks[-1]["version"])
    for version in versions:
        target = findings if version["version"] in current_versions else history_findings
        target.extend(
            f"{identifier} v{version['version']}: {problem}"
            for problem in _binding_problems(root, document, context, version)
        )
    if locks:
        selected = locks[-1]
        try:
            for key in ("decision", "review"):
                if _file(root, selected[key]["path"]) != selected[key]:
                    raise ValueError(f"Locked {key} changed")
            decision = _read(_path(root, selected["decision"]["path"]))
            reference = selected["binding"]
            version = versions[reference["version"] - 1]
            _decision(root, context, reference, version, decision)
            if decision["actor"] != selected["actor"]:
                raise ValueError("Locked actor differs from the decision")
            prerequisite_hash, _ = _prerequisites(context)
            if prerequisite_hash != selected["prerequisites_sha256"]:
                raise ValueError("Delivery stage prerequisites changed")
        except (OSError, ValueError, TypeError, KeyError, IndexError) as error:
            findings.append(f"{identifier} lock: {error}")
    if (root / ".selection-journal.json").exists():
        findings.append("Pending selection transaction; recover before relying on delivery status")
    return {
        "ok": not findings, "id": identifier, "unit_id": document["unit_id"],
        "revision": studio.sha256_file(path), "findings": findings,
        "history_findings": history_findings,
        "binding": document.get("versions", [None])[-1] if document.get("versions") else None,
        "lock": document.get("locks", [None])[-1] if document.get("locks") else None,
        "versions": document.get("versions", []), "locks": document.get("locks", []),
    }


def validate(root: Path, identifier: str) -> list[str]:
    try:
        return list(status(root, identifier)["findings"])
    except (OSError, ValueError, TypeError, KeyError) as error:
        return [str(error)]


def primary_gate(context: ProductionContext) -> tuple[list[str], dict[str, Any]] | None:
    if context.legacy:
        return None
    evidence: dict[str, Any] = {}
    try:
        context = studio.studio_context(context)
        root = context.production_root
        manifest = _read(_path(root, "production.json"))
        entries = [entry for entry in manifest.get("deliverables", [])
                   if entry["unit_id"] == context.unit_id]
        if not entries:
            return None
        selected = [entry for entry in entries if entry.get("primary") is True]
        if len(selected) != 1:
            raise ValueError("Named deliveries require exactly one explicit primary per unit")
        identifier = selected[0]["id"]
        evidence["primary_deliverable_id"] = identifier
        state = status(root, identifier)
        if state["findings"]:
            return list(state["findings"]), evidence
        if state["binding"] is None:
            raise ValueError("The primary delivery requires a current binding")
        if state["lock"] is None:
            raise ValueError("The primary delivery requires a named lock")
        lock_record = _read(_path(root, state["lock"]["path"]))
        if lock_record["binding"] != state["binding"]:
            raise ValueError("The primary delivery lock must approve the current binding")
        binding = _read(_path(root, state["binding"]["path"]))
        evidence.update(
            render_record=binding["render_record"]["path"],
            delivery_binding=state["binding"],
            delivery_lock=state["lock"],
        )
        return [], evidence
    except (OSError, ValueError, TypeError, KeyError) as error:
        return [f"Primary delivery: {error}"], evidence


def _expected(path: Path, expected_revision: str) -> None:
    if not expected_revision or studio.sha256_file(path) != expected_revision:
        raise ValueError("Deliverable revision changed; read status and retry")


def _commit(
    root: Path, path: Path, document: dict[str, Any], record: dict[str, Any],
    filename: str, field: str, expected_revision: str, extra: dict[str, str] | None = None,
) -> None:
    relative = (path.parent / filename).relative_to(root).as_posix()
    target = _path(root, relative, exists=False)
    if target.exists():
        raise ValueError(f"Immutable delivery artifact already exists: {relative}")
    content = _json(record)
    _checked(record, "delivery_binding" if field == "versions" else "delivery_lock")
    document.setdefault(field, []).append({
        "path": relative, "sha256": hashlib.sha256(content.encode()).hexdigest(),
        "version": record["version"],
    })
    _checked(document)
    _expected(path, expected_revision)
    targets = {
        relative: content, path.relative_to(root).as_posix(): _json(document), **(extra or {}),
    }
    studio.selection_service().commit_targets(root, targets)


def bind(
    root: Path, identifier: str, render_record: Path | str, *,
    expected_revision: str, runner: studio.Runner = subprocess.run,
) -> dict[str, Any]:
    root = root.resolve(strict=True)
    _, _, context = _load(root, identifier)
    _path(root, ".selection.lock", exists=False)
    _path(root, ".selection-journal.json", exists=False)
    service = studio.selection_service()
    with studio.studio_writer(context), service.writer_lock(root):
        service.recover_selection(root)
        path, document, context = _load(root, identifier)
        _expected(path, expected_revision)
        versions, _ = _history(root, document)
        relative = _relative(root, render_record)
        render_reference = _file(root, relative)
        record = _render(root, context, relative)
        output = _file(root, record["output"]["path"])
        for previous in versions:
            for key, reference in (("output", output), ("render_record", render_reference)):
                if (
                    previous[key]["path"] == reference["path"]
                    and previous[key]["sha256"] != reference["sha256"]
                ):
                    raise ValueError("A previously bound artifact was overwritten; use a new render name")
        dependencies = _dependencies(root, document, record)
        media = probe_media(_path(root, output["path"]), runner)
        if not math.isfinite(media["duration_s"]) or media["duration_s"] <= 0:
            raise ValueError("Invalid probed duration")
        _streams_match(document["spec"], media)
        recorded_media = record["output"]["probe"]
        if (
            abs(recorded_media["duration_s"] - media["duration_s"]) > 0.01
            or len(recorded_media["streams"]) != len(media["streams"])
            or any(any(actual.get(key) != value for key, value in expected.items())
                   for expected, actual in zip(recorded_media["streams"], media["streams"], strict=True))
        ):
            raise ValueError("Fresh probe differs from the selected render record")
        verify_decode(_path(root, output["path"]), runner)
        version = {
            "schema_version": 1, "record_type": "delivery_binding",
            "version": len(versions) + 1, "created_at": datetime.now(UTC).isoformat(),
            "specification": {key: document[key] for key in SPEC_FIELDS},
            "context": context.identity(), "scene_ids": list(context.scene_ids),
            "render_record": render_reference, "output": output,
            "studio_sha256": record["inputs"]["studio_sha256"],
            "media": media, "dependencies": dependencies,
            "decode": {"method": "ffmpeg-full-audio-video-decode", "status": "pass"},
        }
        current = production_context.resolve_context(root, context.unit_id)
        problems = _binding_problems(root, document, current, version)
        if problems:
            raise ValueError("; ".join(problems))
        _commit(root, path, document, version, f"{identifier}.v{version['version']:06}.json",
                "versions", expected_revision)
    return status(root, identifier)


def lock(
    root: Path, identifier: str, decision: dict[str, Any], *,
    expected_revision: str, runner: studio.Runner = subprocess.run,
) -> dict[str, Any]:
    root = root.resolve(strict=True)
    _, _, context = _load(root, identifier)
    _path(root, ".selection.lock", exists=False)
    _path(root, ".selection-journal.json", exists=False)
    service = studio.selection_service()
    with studio.studio_writer(context), service.writer_lock(root):
        service.recover_selection(root)
        path, document, context = _load(root, identifier)
        _expected(path, expected_revision)
        versions, locks = _history(root, document)
        if not versions:
            raise ValueError("Bind a render before locking a named delivery")
        if locks and locks[-1]["actor"] == "user" and decision.get("actor") != "user":
            raise ValueError("An agent cannot replace a user delivery lock")
        version, reference = versions[-1], document["versions"][-1]
        problems = _binding_problems(root, document, context, version)
        if problems:
            raise ValueError("; ".join(problems))
        prerequisite_hash, gate = _prerequisites(context, runner)
        decision_path, content, digest = _decision(root, context, reference, version, decision)
        record = {
            "schema_version": 1, "record_type": "delivery_lock", "id": identifier,
            "version": version["version"], "created_at": datetime.now(UTC).isoformat(),
            "binding": reference, "decision": {"path": decision_path, "sha256": digest},
            "review": {"path": decision["review_path"], "sha256": decision["review_sha256"]},
            "actor": decision["actor"], "prerequisites_sha256": prerequisite_hash, "gate": gate,
        }
        current = production_context.resolve_context(root, context.unit_id)
        problems = _binding_problems(root, document, current, version)
        if problems or _prerequisites(current)[0] != prerequisite_hash:
            raise ValueError("; ".join(problems) or "Delivery prerequisites changed during locking")
        _decision(root, current, reference, version, decision)
        extra = {} if _path(root, decision_path, exists=False).exists() else {decision_path: content}
        _commit(root, path, document, record, f"{identifier}.lock{len(locks) + 1:06}.json",
                "locks", expected_revision, extra)
    return status(root, identifier)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate, bind and lock explicit named deliveries")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "status", "bind", "lock"):
        command = commands.add_parser(name)
        command.add_argument("project", type=Path)
        command.add_argument("deliverable_id")
        if name in {"bind", "lock"}:
            command.add_argument("--expected-revision", required=True)
        if name == "bind":
            command.add_argument("--render-record", required=True)
        if name == "lock":
            command.add_argument("--decision", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "bind":
            result = bind(args.project, args.deliverable_id, args.render_record,
                          expected_revision=args.expected_revision)
        elif args.command == "lock":
            root = args.project.resolve(strict=True)
            decision = _read(_path(root, _relative(root, args.decision)))
            result = lock(root, args.deliverable_id, decision, expected_revision=args.expected_revision)
        else:
            result = status(args.project, args.deliverable_id)
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as error:
        result = {"ok": False, "findings": [str(error)]}
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
