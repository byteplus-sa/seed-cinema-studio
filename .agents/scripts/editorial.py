from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import asdict, dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import studio_project as studio
from production_context import ProductionContext, resolve_context
from production_post import Finding, confined_file, validate_editorial


class EditorialError(ValueError):
    pass


@dataclass
class Node:
    tag: str
    attributes: dict[str, str]
    parent: Node | None = field(default=None, repr=False)
    children: list[Node] = field(default_factory=list)
    text: str = ""


class EditParser(HTMLParser):
    def __init__(self, text: str):
        super().__init__(convert_charrefs=True)
        self.document = Node("document", {})
        self.stack = [self.document]
        self.nodes: list[Node] = []
        self.feed(text)
        self.close()
        if len(self.stack) != 1:
            raise EditorialError("Unsupported unbalanced HTML")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in {"html", "head", "body", "meta", "title", "template",
                       "style", "script", "div", "video"}:
            raise EditorialError(f"Unsupported edit element: {tag}")
        if len(dict(attrs)) != len(attrs):
            raise EditorialError("Unsupported duplicate HTML attributes")
        node = Node(tag, {key: value or "" for key, value in attrs}, self.stack[-1])
        self.stack[-1].children.append(node)
        self.nodes.append(node)
        if tag != "meta":
            self.stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag != "meta":
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if len(self.stack) == 1 or self.stack[-1].tag != tag:
            raise EditorialError("Unsupported unbalanced HTML")
        self.stack.pop()

    def handle_data(self, data: str) -> None:
        self.stack[-1].text += data


def _number(attributes: dict[str, str], key: str, default: float | None = None) -> float:
    raw = attributes.get(key)
    try:
        result = float(raw) if raw is not None else default
    except ValueError:
        result = None
    if result is None or not math.isfinite(result) or result < 0:
        raise EditorialError(f"Unsupported or invalid {key}; numeric nonnegative timing required")
    return result


def _positive(attributes: dict[str, str], key: str) -> float:
    result = _number(attributes, key)
    if result <= 0:
        raise EditorialError(f"{key} must be positive")
    return result


def _normalized(text: str) -> str:
    return re.sub(r"\s+", "", text)


def _parse(text: str, template: str) -> tuple[Node, list[Node]]:
    parsed, expected = EditParser(text), EditParser(template)
    allowed_attributes = {
        tag: set().union(*(set(node.attributes) for node in expected.nodes if node.tag == tag))
        for tag in {node.tag for node in expected.nodes}
    }
    allowed_code = {
        tag: {_normalized(node.text) for node in expected.nodes if node.tag == tag}
        for tag in ("script", "style")
    }
    ids: set[str] = set()
    for node in parsed.nodes:
        allowed = allowed_attributes.get(node.tag, set()) | {"data-hf-id", "data-label"}
        if node.tag == "div":
            allowed |= {"id", "class", "data-composition-id", "data-composition-src",
                        "data-start", "data-duration", "data-track-index", "data-track-kind",
                        "data-width", "data-height"}
        if node.tag == "video":
            allowed |= {"class", "data-media-start", "data-playback-rate"}
        if set(node.attributes) - allowed:
            raise EditorialError(f"Unsupported {node.tag} attributes: "
                                 f"{', '.join(sorted(set(node.attributes) - allowed))}")
        identifier = node.attributes.get("id")
        if identifier:
            if identifier in ids:
                raise EditorialError("Unsupported duplicate element IDs")
            ids.add(identifier)
        if node.attributes.get("class", "") not in ("", "clip"):
            raise EditorialError("Unsupported styled clip class")
        if node.tag in ("script", "style"):
            if _normalized(node.text) not in allowed_code[node.tag]:
                raise EditorialError(f"Unsupported custom {node.tag}; preserve the Studio edit")
            if node.tag == "script" and node.attributes.get("src") not in (None, studio.GSAP_URL):
                raise EditorialError("Unsupported external script")
        elif node.text.strip() and node.tag != "title":
            raise EditorialError("Unsupported visible content outside the selected video")
        if node.tag == "meta" and set(node.attributes) - {"charset", "name", "content"}:
            raise EditorialError("Unsupported metadata")
    roots = [node for node in parsed.nodes
             if node.tag == "div" and "data-composition-src" not in node.attributes]
    if len(roots) != 1:
        raise EditorialError("Unsupported nested edit; expected one composition root")
    root = roots[0]
    parents = {"html": {"document"}, "head": {"html"}, "body": {"html"},
               "meta": {"head"}, "title": {"head"}, "template": {"body"},
               "style": {"head", "template"}, "script": {"head", "body", "template"}}
    for node in parsed.nodes:
        if node.tag in parents and (node.parent is None or node.parent.tag not in parents[node.tag]):
            raise EditorialError("Unsupported composition structure")
        if node.tag in ("div", "video") and node is not root and node.parent is not root:
            raise EditorialError("Unsupported nested or detached clip")
    if root.parent is None or root.parent.tag not in ("body", "template"):
        raise EditorialError("Unsupported composition root")
    return root, root.children


def _reference(root: Path, relative: str) -> dict[str, str]:
    if not isinstance(relative, str):
        raise EditorialError("Expected a project-relative reference path")
    return {"path": relative, "sha256": studio.sha256_file(confined_file(root, relative))}


def _identity(context: ProductionContext) -> dict[str, Any]:
    if not context.legacy:
        return context.identity()
    return {
        "context_version": 1, "kind": "legacy",
        "effective_sha256": _reference(context.production_root, "project.md")["sha256"],
    }


def _selection(context: ProductionContext, shot: studio.Shot) -> dict[str, Any]:
    root = context.production_root
    if not shot.selected_variant:
        raise EditorialError(f"{shot.shot_id}: no selected take")
    take = _reference(root, studio.take_path(shot, shot.selected_variant))
    manifest = _reference(root, shot.manifest)
    metadata = studio.parse_frontmatter(confined_file(root, shot.manifest).read_text())
    evidence = metadata.get("selection_evidence")
    if not isinstance(evidence, dict):
        raise EditorialError(f"{shot.shot_id}: a hash-bound selection decision is required")
    decision_ref = _reference(root, evidence.get("decision_path", ""))
    if decision_ref["sha256"] != evidence.get("decision_sha256"):
        raise EditorialError("Selection decision hash changed")
    decision = json.loads(confined_file(root, decision_ref["path"]).read_text())
    problems = studio.current_decision_problems(context, decision)
    if problems:
        raise EditorialError("; ".join(problems))
    if (
        decision.get("decision_type") != "variant_selection"
        or decision.get("subject_path") != take["path"]
        or decision.get("selected_variant") != shot.selected_variant
        or decision.get("selected_sha256") != take["sha256"]
        or decision_ref["path"] != f"decisions/{decision.get('decision_id')}.json"
        or metadata.get("status") != "approved"
    ):
        raise EditorialError("Selection decision does not bind the selected take")
    service = studio.selection_service()
    expected = service.decision_evidence(
        decision, decision_ref["path"], decision_ref["sha256"], take["sha256"],
    )
    if evidence != expected:
        raise EditorialError("Manifest selection evidence differs from its decision")
    return {"take": take, "shot_manifest": manifest, "selection_decision": decision_ref}


def _studio_file(context: ProductionContext, relative: str, prefix: str) -> Path:
    if not relative.startswith(prefix):
        raise EditorialError(f"Unsupported source path; expected {prefix}")
    path = confined_file(context.studio_root, relative)
    return path


def _entry(
    context: ProductionContext, host: Node, shots: dict[str, studio.Shot],
    selections: dict[str, dict[str, Any]], probes: dict[str, float],
) -> dict[str, Any]:
    attrs = host.attributes
    if host.tag != "div" or host.children or not attrs.get("id"):
        raise EditorialError("Unsupported host; expected an empty named straight-cut host")
    shot_id = attrs.get("data-composition-id", "")
    if shot_id not in shots:
        raise EditorialError("Host refers to a foreign or unknown shot")
    start, duration = _number(attrs, "data-start"), _positive(attrs, "data-duration")
    frame_path = _studio_file(context, attrs.get("data-composition-src", ""), "compositions/")
    frame_text = frame_path.read_text()
    frame_parser = EditParser(frame_text)
    frame_roots = [node for node in frame_parser.nodes if "data-composition-id" in node.attributes]
    if len(frame_roots) != 1:
        raise EditorialError("Unsupported nested composition")
    dimensions = frame_roots[0].attributes
    width, height = _positive(dimensions, "data-width"), _positive(dimensions, "data-height")
    frame, videos = _parse(frame_text, studio.frame_html(
        shot_id, "unused.mp4", 1, 1, int(width), int(height), False,
    ))
    if frame.attributes.get("data-composition-id") != shot_id:
        raise EditorialError("Host and source composition identities differ")
    if set(frame.attributes) - {"id", "data-composition-id", "data-width", "data-height", "data-hf-id"}:
        raise EditorialError("Unsupported timed composition root")
    if len(videos) != 1 or videos[0].tag != "video" or videos[0].children:
        raise EditorialError("Unsupported composition; expected exactly one video")
    video = videos[0].attributes
    if _number(video, "data-playback-rate", 1) != 1:
        raise EditorialError("Unsupported playback rate")
    local_start = _number(video, "data-start")
    video_duration = _positive(video, "data-duration")
    source_in = _number(video, "data-media-start", 0)
    length = min(duration - local_start, video_duration)
    if length <= 0:
        raise EditorialError("Video has no visible range inside its host")
    if shot_id not in selections:
        selections[shot_id] = _selection(context, shots[shot_id])
    selection = selections[shot_id]
    source = confined_file(context.production_root, selection["take"]["path"])
    asset = _studio_file(context, video.get("src", ""), "assets/")
    if studio.sha256_file(asset) != selection["take"]["sha256"]:
        raise EditorialError("Placed video differs from the selected take")
    if shot_id not in probes:
        media = studio.probe_media(source)
        measured = media.get("duration_s")
        if (
            not isinstance(measured, int | float) or isinstance(measured, bool)
            or not math.isfinite(measured) or measured <= 0
            or not any(stream.get("codec_type") == "video" for stream in media.get("streams", []))
        ):
            raise EditorialError("Selected take requires a measured video duration")
        probes[shot_id] = float(measured)
    if source_in + video_duration > probes[shot_id] + 0.000001:
        raise EditorialError("Video trim exceeds measured source duration")
    return {
        "id": "", "host_id": attrs["id"], "shot_id": shot_id, **selection,
        "timeline_start_s": start + local_start, "source_in_s": source_in,
        "source_out_s": source_in + length, "source_duration_s": probes[shot_id],
    }


def _capture(context: ProductionContext) -> dict[str, Any]:
    context = studio.studio_context(context)
    tree = studio.tree_digest(context)
    identity = _identity(context)
    index = context.studio_root / "index.html"
    source = _reference(context.production_root, index.relative_to(context.production_root).as_posix())
    text = index.read_text()
    dimensions = studio.root_dimensions(text)
    if dimensions is None:
        raise EditorialError("Unsupported Studio entrypoint; expected main composition")
    root, hosts = _parse(text, studio.root_html(*dimensions, studio.DEFAULT_FPS))
    if root.attributes.get("data-composition-id") != "main" or _number(root.attributes, "data-start", 0) != 0:
        raise EditorialError("Unsupported root composition timing")
    if root.parent is None or root.parent.tag != "body":
        raise EditorialError("Unsupported templated entrypoint")
    if not hosts:
        raise EditorialError("Cannot export an empty edit")
    duration = _positive(root.attributes, "data-duration")
    previous_end = 0.0
    for host in sorted(hosts, key=lambda item: _number(item.attributes, "data-start")):
        start = _number(host.attributes, "data-start")
        end = start + _positive(host.attributes, "data-duration")
        if start < previous_end - 0.000001:
            raise EditorialError("Unsupported overlapping hosts")
        if end > duration + 0.000001:
            raise EditorialError("Host placement exceeds root duration")
        previous_end = end
    shots = {shot.shot_id: shot for shot in studio.discover_shots(context)}
    selections: dict[str, dict[str, Any]] = {}
    probes: dict[str, float] = {}
    entries = [_entry(context, host, shots, selections, probes) for host in hosts]
    entries.sort(key=lambda entry: entry["timeline_start_s"])
    for index_, entry in enumerate(entries):
        entry["id"] = f"clip-{index_ + 1:03}"
    document: dict[str, Any] = {
        "schema_version": 1, "unit_id": context.unit_id or "main", "cut_id": "main",
        "duration_s": duration, "source_edit": source, "entries": entries,
        "runtime": {
            "export_version": 1, "context": identity, "scene_ids": list(context.scene_ids),
            "tree_sha256": tree,
        },
    }
    findings = validate_editorial(context.production_root, document, unit_id=document["unit_id"],
                                  selected_takes={key: value["take"]["path"]
                                                  for key, value in selections.items()})
    if findings:
        raise EditorialError("; ".join(f"{item.code}: {item.message}" for item in findings))
    for shot_id, selection in selections.items():
        if _selection(context, shots[shot_id]) != selection:
            raise EditorialError("Selection changed during export")
    if tree != studio.tree_digest(context) or identity != _identity(context):
        raise EditorialError("Studio tree or context changed during export")
    studio.studio_context(context)
    return document


def _output_path(context: ProductionContext, output: str, *, main: bool = False) -> Path:
    scope = f"editorial/{context.unit_id or 'main'}/"
    if (
        not isinstance(output, str) or not output.startswith(scope)
        or "\\" in output or ":" in output or any(ord(char) < 32 for char in output)
        or any(part in ("", ".", "..") for part in output.split("/"))
        or not output.endswith(".json")
    ):
        raise EditorialError(f"Output must be a confined {scope} JSON path")
    canonical = f"{scope}main.json"
    if output == canonical and not main:
        raise EditorialError("main.json requires explicit reconcile_edit with an expected revision")
    path = context.production_root
    for part in output.split("/"):
        path /= part
        if path.is_symlink():
            raise EditorialError("Editorial output paths cannot contain symlinks")
    if path.exists() and (not path.is_file() or path.stat().st_nlink != 1):
        raise EditorialError("Editorial output must be an unaliased regular file")
    return path


def _require_tree(document: dict[str, Any], expected: str | None) -> None:
    if expected is not None and document["runtime"]["tree_sha256"] != expected:
        raise EditorialError("Studio tree revision differs from expected_tree_sha256")


def _json(document: dict[str, Any]) -> str:
    return json.dumps(document, indent=2, ensure_ascii=False, allow_nan=False) + "\n"


def _text(path: Path) -> str:
    return path.read_bytes().decode("utf-8")


def _pending_transaction(context: ProductionContext) -> None:
    journal = context.production_root / ".selection-journal.json"
    if journal.exists() or journal.is_symlink():
        raise EditorialError("Pending selection transaction; recover it explicitly before editorial export")


def export_edit(
    project: Path | ProductionContext, output: str, expected_tree_sha256: str | None = None,
) -> Path:
    context = studio.studio_context(project)
    path = _output_path(context, output)
    _pending_transaction(context)
    document = _capture(context)
    _require_tree(document, expected_tree_sha256)
    content = _json(document)
    if path.exists() and _text(path) != content:
        raise EditorialError("Immutable snapshot already exists; choose a new output path")
    with studio.studio_writer(context):
        service = studio.selection_service()
        with service.writer_lock(context.production_root):
            _pending_transaction(context)
            if _capture(context) != document:
                raise EditorialError("Edit or selection changed during export")
            path = _output_path(context, output)
            if path.exists():
                if _text(path) != content:
                    raise EditorialError("Immutable snapshot already exists")
                return path
            path.parent.mkdir(parents=True, exist_ok=True)
            service.commit_targets(context.production_root, {output: content})
    return path


def check_edit(project: Path | ProductionContext, record: str) -> list[Finding]:
    try:
        context = studio.studio_context(project)
        content = _text(confined_file(context.production_root, record))
        document = json.loads(content)
        findings = validate_editorial(context.production_root, document,
                                      unit_id=context.unit_id or "main")
        if findings:
            return findings
        if "runtime" not in document:
            return [Finding("runtime", record, "Record has no runtime export binding")]
        current = _capture(context)
        findings = []
        for key in ("runtime", "source_edit", "duration_s", "entries"):
            if document.get(key) != current[key]:
                findings.append(Finding("edit", key, "Snapshot differs from the current Studio edit"))
        if _text(confined_file(context.production_root, record)) != content:
            findings.append(Finding("edit", record, "Snapshot changed during check"))
        return findings
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as error:
        return [Finding("edit", record, str(error))]


def reconcile_edit(
    project: Path | ProductionContext, record: str, *, expected_revision: str | None,
    expected_tree_sha256: str | None = None,
) -> Path:
    context = studio.studio_context(project)
    snapshot = _output_path(context, record)
    content = _text(confined_file(context.production_root, record))
    document = json.loads(content)
    findings = check_edit(context, record)
    if findings:
        raise EditorialError("; ".join(item.message for item in findings))
    _require_tree(document, expected_tree_sha256)
    main_relative = f"editorial/{context.unit_id or 'main'}/main.json"
    main = _output_path(context, main_relative, main=True)
    _pending_transaction(context)
    with studio.studio_writer(context):
        service = studio.selection_service()
        with service.writer_lock(context.production_root):
            _pending_transaction(context)
            main = _output_path(context, main_relative, main=True)
            revision = studio.sha256_file(main) if main.exists() else None
            if revision != expected_revision:
                raise EditorialError("main.json revision changed; supply its current SHA256")
            snapshot = _output_path(context, record)
            if _text(snapshot) != content:
                raise EditorialError("Snapshot changed during reconciliation")
            findings = check_edit(context, record)
            if findings:
                raise EditorialError("; ".join(item.message for item in findings))
            main = _output_path(context, main_relative, main=True)
            current_revision = studio.sha256_file(main) if main.exists() else None
            if current_revision != expected_revision:
                raise EditorialError("main.json revision changed during reconciliation")
            if _text(_output_path(context, record)) != content:
                raise EditorialError("Snapshot changed during reconciliation")
            targets = {}
            if main.exists():
                prior = _text(main)
                archive_relative = f"editorial/{context.unit_id or 'main'}/snapshots/{revision}.json"
                archive = _output_path(context, archive_relative)
                if archive.exists() and _text(archive) != prior:
                    raise EditorialError("Immutable prior snapshot has changed")
                if not archive.exists():
                    archive.parent.mkdir(parents=True, exist_ok=True)
                    targets[archive_relative] = prior
            main.parent.mkdir(parents=True, exist_ok=True)
            targets[main_relative] = content
            service.commit_targets(context.production_root, targets)
    return main


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Explicit read-only Studio snapshots (Phase 4, PLAN_SEED_CINEMA_STUDIO.md)",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("export", "check", "reconcile"):
        subparser = commands.add_parser(command)
        subparser.add_argument("project", type=Path)
        subparser.add_argument("--unit")
        subparser.add_argument("--output" if command == "export" else "--record", required=True)
        if command != "check":
            subparser.add_argument("--expected-tree-sha256")
        if command == "reconcile":
            subparser.add_argument("--expected-revision", required=True,
                                   help="Current main.json SHA256, or 'absent' for first reconciliation")
    args = parser.parse_args(argv)
    result: dict[str, Any] = {"valid": True, "review_status": "not_evaluated", "findings": []}
    try:
        context = resolve_context(args.project, args.unit)
        if args.command == "check":
            findings = check_edit(context, args.record)
            result.update(valid=not findings, findings=[asdict(item) for item in findings])
        elif args.command == "export":
            path = export_edit(context, args.output, args.expected_tree_sha256)
            result["snapshot"] = path.relative_to(context.production_root).as_posix()
        else:
            path = reconcile_edit(
                context, args.record,
                expected_revision=None if args.expected_revision == "absent" else args.expected_revision,
                expected_tree_sha256=args.expected_tree_sha256,
            )
            result["record"] = path.relative_to(context.production_root).as_posix()
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as error:
        result.update(valid=False, findings=[asdict(Finding("edit", "", str(error)))])
    print(json.dumps(result, indent=2))
    return 0 if result["valid"] else 2


if __name__ == "__main__":
    sys.exit(main())
