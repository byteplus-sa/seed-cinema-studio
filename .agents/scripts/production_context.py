from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

SCHEMA_ROOT = Path(__file__).resolve().parents[1] / "contracts/schemas"
SCENE_ID = re.compile(r"scene-[0-9]{2,}\Z")
SHOT_ID = re.compile(r"[A-Za-z][A-Za-z0-9_-]*\Z")
SHARED_FIELDS = (
    "production", "market", "episode", "delivery", "creative", "creative_intent", "story",
    "directorial_axes", "locked", "locks", "approval_mode", "approval", "authorization",
    "rights", "budget", "unit_budget",
)
OPERATIONAL_PATHS = frozenset(("effective_settings", name) for name in (
    "timestamp", "timestamps", "created_at", "updated_at", "decided_at",
    "billing", "runtime", "usage", "spent", "confirmed_spend", "estimated_spend",
    "unknown_spend", "reserved", "path", "paths", "manifest", "brief",
    "project_root", "production_root", "studio_root", "stages_path", "source_path", "source_paths",
    "credentials", "api_key", "token", "secret", "signed_url", "units",
    "deliverables", "progress", "render", "renders", "task_ids", "drafts",
))
BUDGET_PATHS = frozenset({("shared_inputs", "budget"), ("effective_settings", "budget")})


@dataclass(frozen=True)
class Finding:
    rule_id: str
    message: str
    path: str = ""
    severity: str = "error"


@dataclass(frozen=True)
class Shot:
    shot_id: str
    manifest: str
    directory: str
    scene_id: str | None


@dataclass(frozen=True)
class ProductionContext:
    production_root: Path
    unit_id: str | None
    unit_brief: Path | None
    scene_ids: tuple[str, ...]
    studio_root: Path
    stages_path: Path
    legacy: bool
    effective_sha256: str | None = None
    _canonical_json: str = field(default="", repr=False)
    _candidate_manifest: str | None = field(default=None, repr=False)

    def identity(self) -> dict[str, Any]:
        if self.legacy or self.effective_sha256 is None:
            raise ValueError("Legacy context has no integrity-bound unit identity")
        identity = {
            "context_version": 1,
            "kind": "unit" if self.unit_id is not None else "production",
            "effective_sha256": self.effective_sha256,
        }
        if self.unit_id is not None:
            identity["unit_id"] = self.unit_id
        return identity


def _root(project: Path) -> Path:
    root = Path(project).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Production root must be an existing directory")
    return root


def _present(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def has_production_manifest(project: Path) -> bool:
    return _present(Path(project) / "production.json")


def reject_active_manifest(project: Path) -> None:
    if _present(Path(project) / "production.json"):
        raise ValueError(
            "unsupported production layout: this legacy or candidate-only entry "
            "cannot use active production.json; resolve an active context instead"
        )


def _path(root: Path, value: str, kind: str | None = None) -> Path:
    if (
        not isinstance(value, str) or not value or "\\" in value or ":" in value
        or any(ord(character) < 32 for character in value)
        or value.startswith("/") or any(part in {"", ".", ".."} for part in value.split("/"))
    ):
        raise ValueError("Expected a safe project-relative path without traversal")
    lexical = root / value
    path = lexical.resolve()
    if not path.is_relative_to(root):
        raise ValueError(f"Path escapes production root: {value}")
    if lexical.is_symlink() and not path.exists():
        raise ValueError(f"Dangling symlink: {value}")
    if kind == "file" and not path.is_file():
        raise ValueError(f"Missing file: {value}")
    if kind == "directory" and not path.is_dir():
        raise ValueError(f"Missing directory: {value}")
    return path


def _candidate_path(root: Path, manifest: str | Path) -> Path:
    value = str(manifest)
    path = _path(root, value, "file")
    if path == root / "production.json" or Path(value).name == "production.json":
        raise ValueError("Active production.json is not a candidate manifest")
    return path


def _json_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _invalid_constant(value: str) -> None:
    raise ValueError(f"Invalid JSON constant: {value}")


def _read_manifest(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_json_pairs,
                      parse_constant=_invalid_constant)
    schema = json.loads((SCHEMA_ROOT / "production.schema.json").read_text())
    errors = list(Draft202012Validator(schema).iter_errors(data))
    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.absolute_path)
        raise ValueError(f"Invalid production manifest at {location or '<root>'}: {error.validator}")
    if not isinstance(data, dict):
        raise TypeError("Expected production manifest object")
    return data


def _brief(path: Path, *, text: str | None = None) -> tuple[dict[str, Any], str]:
    if text is None:
        text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}, text
    match = re.match(r"\A---[ \t]*\r?\n(.*?)\r?\n---(?:\r?\n|$)", text, re.DOTALL)
    if not match:
        raise ValueError("Malformed brief frontmatter")
    try:
        metadata = YAML(typ="safe").load(match.group(1))
    except YAMLError:
        raise ValueError("Malformed YAML brief frontmatter") from None
    if not isinstance(metadata, dict):
        raise TypeError("Brief frontmatter must be a mapping")
    return metadata, text[match.end():]


def _unique(values: list[str], label: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"Duplicate {label} membership")


def _scene_directories(root: Path) -> dict[str, Path]:
    scenes_path = _path(root, "scenes")
    if not scenes_path.exists():
        return {}
    _path(root, "scenes", "directory")
    scenes: dict[str, Path] = {}
    numeric: set[int] = set()
    for entry in sorted(scenes_path.iterdir()):
        if not SCENE_ID.fullmatch(entry.name):
            continue
        resolved = _path(root, f"scenes/{entry.name}", "directory")
        number = int(entry.name.removeprefix("scene-"))
        if number in numeric or resolved in scenes.values():
            raise ValueError("Ambiguous scene aliases")
        numeric.add(number)
        scenes[entry.name] = resolved
    return scenes


def _shots(root: Path, scenes: tuple[str, ...] | None) -> list[Shot]:
    manifests: list[tuple[str | None, Path]] = []
    scenes_path = _path(root, "scenes")
    if not scenes_path.exists():
        return []
    _path(root, "scenes", "directory")
    directories = (
        [(name, _path(root, f"scenes/{name}", "directory")) for name in scenes]
        if scenes is not None else [(entry.name, entry) for entry in sorted(scenes_path.iterdir())]
    )
    for scene_id, directory in directories:
        directory = _path(root, directory.relative_to(root).as_posix())
        if not directory.is_dir():
            continue
        direct = directory / "shot.md"
        if _present(direct):
            if scenes is not None:
                raise ValueError("Ambiguous legacy and unit shot ownership")
            manifests.append((None, direct))
        if scene_id.startswith("scene-"):
            for child in sorted(directory.iterdir()):
                resolved = _path(root, child.relative_to(root).as_posix())
                if resolved.is_dir() and _present(resolved / "shot.md"):
                    manifests.append((scene_id, child / "shot.md"))
    if scenes is None:
        manifests.sort(key=lambda item: item[1])
    shots: list[Shot] = []
    real_paths: set[Path] = set()
    for owning_scene, manifest in manifests:
        relative = manifest.relative_to(root).as_posix()
        resolved = _path(root, relative, "file")
        if resolved in real_paths:
            raise ValueError("Duplicate shot path membership")
        real_paths.add(resolved)
        metadata, _ = _brief(resolved)
        identifier = metadata.get("shot_id") or metadata.get("shot") or metadata.get("id")
        shot_id = str(identifier or manifest.parent.name)
        if not SHOT_ID.fullmatch(shot_id) or shot_id.lower() in {"main", "root"}:
            raise ValueError(f"Invalid shot id in {relative}")
        declared_scene = metadata.get("scene_id")
        if scenes is not None and declared_scene is not None and declared_scene != owning_scene:
            raise ValueError(f"Ambiguous shot scene membership in {relative}")
        shots.append(Shot(shot_id, relative, manifest.parent.relative_to(root).as_posix(), owning_scene))
    _unique([shot.shot_id.lower() for shot in shots], "shot")
    return shots


def _semantic_validation(root: Path, data: dict[str, Any]) -> None:
    units = data["units"]
    _unique([unit["id"] for unit in units], "unit")
    scene_ids = [scene for unit in units for scene in unit["scene_ids"]]
    _unique(scene_ids, "scene")
    scenes = _scene_directories(root)
    if set(scene_ids) != set(scenes):
        raise ValueError("Missing referenced scenes or unowned scene directories")
    if _present(root / "showcase.json") or _present(root / "studio"):
        raise ValueError("Ambiguous legacy and unit Studio ownership")
    briefs: set[Path] = set()
    unit_roots: set[Path] = set()
    studios: set[Path] = set()
    shared_brief = _path(root, "project.md", "file")
    if (root / "units").is_symlink():
        raise ValueError("Unit ownership requires a real units directory")
    for unit in units:
        brief = _path(root, unit["brief"], "file")
        if brief in briefs or brief == shared_brief:
            raise ValueError("Ambiguous shared unit brief ownership")
        briefs.add(brief)
        unit_root = _path(root, f"units/{unit['id']}")
        if (root / f"units/{unit['id']}").is_symlink() or (
            unit_root.exists() and not unit_root.is_dir()
        ):
            raise ValueError("Unit ownership requires a real unit directory")
        if unit_root in unit_roots:
            raise ValueError("Ambiguous unit directory aliases")
        unit_roots.add(unit_root)
        studio = _path(root, f"units/{unit['id']}/studio")
        if studio in studios or (root / f"units/{unit['id']}/studio").is_symlink():
            raise ValueError("Ambiguous unit Studio aliases")
        studios.add(studio)
        if studio.exists() and not studio.is_dir():
            raise ValueError("Unit Studio root must be a directory")
        _path(root, f"units/{unit['id']}/studio/stages.json")
    owners = {scene: unit["id"] for unit in units for scene in unit["scene_ids"]}
    for scene in scene_ids:
        metadata, _ = _brief(_path(root, f"scenes/{scene}/scene.md", "file"))
        if metadata.get("scene_id", scene) != scene or metadata.get("unit_id", owners[scene]) != owners[scene]:
            raise ValueError("Ambiguous declared scene ownership")
    all_shots = _shots(root, None)
    unit_shots = _shots(root, tuple(scene_ids))
    if {shot.manifest for shot in all_shots} != {shot.manifest for shot in unit_shots}:
        raise ValueError("Ambiguous legacy and unit shot ownership")
    for shot in unit_shots:
        metadata, _ = _brief(_path(root, shot.manifest, "file"))
        if metadata.get("unit_id", owners[shot.scene_id or ""]) != owners[shot.scene_id or ""]:
            raise ValueError("Ambiguous declared shot unit ownership")
    deliverables = data.get("deliverables", [])
    _unique([item["id"] for item in deliverables], "deliverable")
    deliverable_paths = []
    for item in deliverables:
        if item["unit_id"] not in {unit["id"] for unit in units}:
            raise ValueError("Deliverable references unknown unit")
        deliverable_paths.append(str(_path(root, item["manifest"], "file")))
    _unique(deliverable_paths, "deliverable path")


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def _creative_data(value: Any, path: tuple[str, ...] = ()) -> Any:
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("Creative metadata keys must be strings")
            field_path = (*path, key)
            if field_path in OPERATIONAL_PATHS:
                continue
            if field_path in BUDGET_PATHS:
                if not isinstance(item, dict):
                    raise ValueError("Budget must be a mapping")
                item = {name: item[name] for name in
                        ("cap", "spending_cap", "currency")
                        if name in item}
                if not item:
                    continue
            result[key] = _creative_data(item, field_path)
        return result
    if isinstance(value, list):
        return [_creative_data(item, (*path, str(index))) for index, item in enumerate(value)]
    if value is None or isinstance(value, str | bool | int | float):
        return value
    raise ValueError("Creative metadata must contain JSON-compatible values")


def _fingerprint(root: Path, data: dict[str, Any], unit: dict[str, Any]) -> str:
    from production_profiles import load_profile, resolve_brief

    shared, body = _brief(_path(root, "project.md", "file"))
    unit_path = _path(root, unit["brief"], "file")
    unit_bytes = unit_path.read_bytes()
    unit_metadata, _ = _brief(unit_path, text=unit_bytes.decode("utf-8"))
    effective = resolve_brief(shared, unit_metadata, format_id=data["format"])
    inputs = {key: shared[key] for key in SHARED_FIELDS if key in shared}
    inputs = _creative_data(inputs, ("shared_inputs",))
    inputs["body_sha256"] = hashlib.sha256(body.encode()).hexdigest()
    return _canonical({
        "context_version": 1,
        "kind": "unit",
        "unit_id": unit["id"],
        "format": data["format"],
        "unit_brief_sha256": hashlib.sha256(unit_bytes).hexdigest(),
        "scene_ids": unit["scene_ids"],
        "profile": _creative_data(load_profile(data["format"]), ("profile",)),
        "effective_settings": _creative_data(effective, ("effective_settings",)),
        "shared_inputs": inputs,
    })


def _validated_candidate(root: Path, manifest: str | Path) -> dict[str, Any]:
    reject_active_manifest(root)
    data = _read_manifest(_candidate_path(root, manifest))
    _semantic_validation(root, data)
    for unit in data["units"]:
        _fingerprint(root, data, unit)
    return data


def _validated_active(root: Path) -> dict[str, Any]:
    try:
        manifest = root / "production.json"
        if manifest.is_symlink() or not manifest.is_file():
            raise ValueError("Active manifest must be a real file")
        data = _read_manifest(manifest)
        _semantic_validation(root, data)
        for unit in data["units"]:
            _fingerprint(root, data, unit)
        _shared_payload(root, data)
        return data
    except (ValueError, TypeError, OSError) as error:
        raise ValueError(f"unsupported production layout: {error}") from error


def _unit_context(
    root: Path, data: dict[str, Any], unit_id: str | None, candidate: str | None = None,
) -> ProductionContext:
    units = data["units"]
    if unit_id is None and len(units) != 1:
        raise ValueError("Multiple units require explicit unit selection")
    selected = next((unit for unit in units if unit_id is None or unit["id"] == unit_id), None)
    if selected is None:
        raise ValueError("Unknown unit")
    canonical = _fingerprint(root, data, selected)
    studio = _path(root, f"units/{selected['id']}/studio")
    return ProductionContext(
        root, selected["id"], _path(root, selected["brief"], "file"),
        tuple(selected["scene_ids"]), studio, studio / "stages.json", False,
        hashlib.sha256(canonical.encode()).hexdigest(), canonical, candidate,
    )


def _shared_payload(root: Path, data: dict[str, Any]) -> dict[str, Any]:
    from production_profiles import load_profile, resolve_brief

    shared, body = _brief(_path(root, "project.md", "file"))
    inputs = _creative_data(
        {key: shared[key] for key in SHARED_FIELDS if key in shared}, ("shared_inputs",),
    )
    inputs["body_sha256"] = hashlib.sha256(body.encode()).hexdigest()
    return {
        "context_version": 1,
        "kind": "production",
        "format": data["format"],
        "profile": _creative_data(load_profile(data["format"]), ("profile",)),
        "effective_settings": _creative_data(
            resolve_brief(shared, format_id=data["format"]), ("effective_settings",),
        ),
        "shared_inputs": inputs,
    }


def context_project_sha256(project: Path) -> str:
    root = _root(project)
    data = _validated_active(root)
    return hashlib.sha256(_canonical(_shared_payload(root, data)).encode()).hexdigest()


def resolve_production_context(project: Path) -> ProductionContext:
    root = _root(project)
    data = _validated_active(root)
    canonical = _canonical(_shared_payload(root, data))
    return ProductionContext(
        root, None, None, (), root, root / "production-stages.json", False,
        hashlib.sha256(canonical.encode()).hexdigest(), canonical,
    )


def context_identity(
    project: Path, kind: str = "unit", unit_id: str | None = None,
) -> dict[str, Any]:
    if kind == "production":
        if unit_id is not None:
            raise ValueError("Production scope cannot select a unit")
        return resolve_production_context(project).identity()
    if kind != "unit":
        raise ValueError("Unknown context kind")
    return resolve_context(project, unit_id).identity()


def validate_record_context(
    project: Path, identity: Any, unit_id: str | None = None, kind: str | None = None,
) -> None:
    schema = json.loads((SCHEMA_ROOT / "production-context.schema.json").read_text())
    if list(Draft202012Validator(schema).iter_errors(identity)):
        raise ValueError("Invalid typed production context")
    expected = context_identity(project, kind or "unit", unit_id)
    if identity != expected:
        raise ValueError("Stale or foreign production context")


def resolve_context(project: Path, unit_id: str | None = None) -> ProductionContext:
    root = _root(project)
    if has_production_manifest(root):
        return _unit_context(root, _validated_active(root), unit_id)
    if unit_id is not None:
        raise ValueError("Cannot select a unit without production.json; validate candidates separately")
    studio = _path(root, "studio")
    stages = _path(root, "studio/stages.json")
    scenes = _path(root, "scenes")
    scene_ids = tuple(
        path.name for path in sorted(scenes.glob("scene-*"))
        if _path(root, f"scenes/{path.name}").is_dir()
    )
    return ProductionContext(root, None, None, scene_ids, studio, stages, True)


def resolve_candidate_context(
    project: Path, manifest: str | Path, unit_id: str | None = None,
) -> ProductionContext:
    root = _root(project)
    data = _validated_candidate(root, manifest)
    return _unit_context(root, data, unit_id, str(manifest))


def context_fingerprint_payload(context: ProductionContext) -> dict[str, Any]:
    if context.legacy:
        raise ValueError("Legacy context has no versioned fingerprint")
    result: dict[str, Any] = json.loads(context._canonical_json)
    return result


def discover_unit_shots(context: ProductionContext) -> list[Shot]:
    if context._candidate_manifest is not None:
        current = resolve_candidate_context(
            context.production_root, context._candidate_manifest, context.unit_id,
        )
        if current != context:
            raise ValueError("Stale production context; resolve the candidate again")
    elif context.legacy:
        reject_active_manifest(context.production_root)
    else:
        if context.unit_id is None:
            raise ValueError("Production canon scope cannot discover unit shots")
        current = resolve_context(context.production_root, context.unit_id)
        if current != context:
            raise ValueError("Stale production context; resolve the unit again")
    return _shots(context.production_root, None if context.legacy else context.scene_ids)


def validate_production(
    project: Path, *, manifest: str | Path | None = None,
) -> list[Finding]:
    try:
        root = _root(project)
        if manifest is None:
            if has_production_manifest(root):
                _validated_active(root)
            else:
                discover_unit_shots(resolve_context(root))
        else:
            _validated_candidate(root, manifest)
    except (ValueError, TypeError, OSError, RuntimeError, YAMLError, ImportError) as error:
        return [Finding("production.context", str(error), str(manifest or "production.json"))]
    return []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only production and candidate validation")
    parser.add_argument("project", type=Path)
    parser.add_argument("--manifest", help="Project-relative production.plan.json candidate")
    parser.add_argument("--unit")
    args = parser.parse_args(argv)
    findings = validate_production(args.project, manifest=args.manifest)
    result: dict[str, Any] = {"ok": not findings, "findings": [asdict(item) for item in findings]}
    if not findings and args.unit is not None:
        try:
            context = (
                resolve_candidate_context(args.project, args.manifest, args.unit)
                if args.manifest is not None else resolve_context(args.project, args.unit)
            )
            result["context"] = context.identity()
            result["scene_ids"] = list(context.scene_ids)
        except ValueError as error:
            result = {"ok": False, "findings": [asdict(Finding("production.context", str(error)))]}
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
