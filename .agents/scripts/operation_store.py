from __future__ import annotations

import fcntl
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from threading import local
from typing import Any

from budget_report import cancelled_before_submission
from ruamel.yaml.error import YAMLError
from validate_request import (
    operational_context,
    parse_frontmatter,
    prepared_evidence_findings,
    production_context_module,
    project_mode_findings,
    record_scope_findings,
    schema_findings,
    studio_project,
    validate_request,
    validate_review,
)

TRANSITIONS = {
    "prepared": {"submitting", "terminal"},
    "submitting": {"submission_unknown", "acknowledged", "terminal"},
    "submission_unknown": {"acknowledged", "terminal"},
    "acknowledged": {"acknowledged", "terminal"},
    "terminal": set(),
}
_registry_locks = local()


def registry_revision(document: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


class RegistrySnapshot(dict[str, Any]):
    def __init__(self, document: dict[str, Any]) -> None:
        super().__init__(document)
        self.revision = registry_revision(document)


def require_never_submitted(record: dict[str, Any]) -> None:
    if (
        record["submission_status"] != "prepared"
        or record["provider_task_id"] is not None
        or record["provider_status"] is not None
        or record["review_status"] != "not_started"
        or record["cost"]["confirmed"] is not None
        or record["cost"].get("usage") is not None
    ):
        raise ValueError("Cancellation requires a prepared operation with no submission evidence")


def validate_layout(root: Path) -> None:
    if production_context_module().has_production_manifest(root):
        try:
            operational_context(root, production_scope=True)
        except (OSError, RuntimeError, TypeError) as error:
            raise ValueError(f"Invalid production layout: {error}") from error


@contextmanager
def selection_lock(root: Path) -> Iterator[None]:
    validate_layout(root)
    path = root.resolve() / ".selection.lock"
    if path.is_symlink():
        raise ValueError("Selection lock must not be a symlink")
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield


@contextmanager
def registry_lock(root: Path) -> Iterator[Path]:
    validate_layout(root)
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    lock = root / ".task_ids.lock"
    if lock.is_symlink():
        raise ValueError("Registry lock must not be a symlink")
    registry = root / "task_ids.json"
    if registry.is_symlink():
        raise ValueError("Registry must not be a symlink")
    held = getattr(_registry_locks, "held", None)
    if held is None:
        held = _registry_locks.held = set()
    key = (os.getpid(), root)
    if key in held:
        yield registry
        return
    descriptor = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        if registry.is_symlink():
            raise ValueError("Registry must not be a symlink")
        held.add(key)
        try:
            yield registry
        finally:
            held.remove(key)


def read_registry(path: Path) -> RegistrySnapshot:
    if path.is_symlink():
        raise ValueError("Registry must not be a symlink")
    if not path.exists():
        return RegistrySnapshot({"schema_version": 1, "tasks": []})
    document = json.loads(path.read_text())
    findings = schema_findings(document, "task-registry.schema.json")
    if findings:
        raise ValueError(
            "Legacy or invalid registry requires an explicit migration preview; existing data was preserved"
        )
    identifiers = [record["operation_id"] for record in document["tasks"]]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("Duplicate operation identities in registry")
    return RegistrySnapshot(document)


def lifecycle_scope_findings(root: Path, record: dict[str, Any]) -> list[Any]:
    if (
        record.get("schema_version") == 3
        and record.get("submission_status") != "prepared"
        and production_context_module().has_production_manifest(root)
    ):
        validate_layout(root)
        return schema_findings(record, "generation-request.schema.json")
    return record_scope_findings(root, record, context=record.get("context"))


def replace_registry(
    path: Path, document: dict[str, Any], *, expected_revision: str | None = None,
) -> None:
    with registry_lock(path.parent) as registry_path:
        if path.resolve() != registry_path:
            raise ValueError("Registry writes must target task_ids.json")
        revision = expected_revision
        if revision is None and isinstance(document, RegistrySnapshot):
            revision = document.revision
        if revision is None or revision != read_registry(registry_path).revision:
            raise ValueError("Stale or missing registry revision; read the registry again")
        _replace_registry(registry_path, document)
        if isinstance(document, RegistrySnapshot):
            document.revision = registry_revision(document)


def _replace_registry(path: Path, document: dict[str, Any]) -> None:
    validate_layout(path.parent)
    if schema_findings(document, "task-registry.schema.json"):
        raise ValueError("Cannot write invalid task registry")
    previous = {record["operation_id"]: record for record in read_registry(path)["tasks"]}
    identifiers = [record["operation_id"] for record in document["tasks"]]
    if len(identifiers) != len(set(identifiers)) or not set(previous).issubset(identifiers):
        raise ValueError("Registry writes must preserve unique operation history")
    for record in document["tasks"]:
        existing = previous.get(record["operation_id"])
        if existing == record:
            continue
        if record["provider_status"] == "cancelled_before_submission":
            if existing is None:
                raise ValueError("Cancellation requires an existing prepared operation")
            if not cancelled_before_submission(existing):
                require_never_submitted(existing)
                expected = {
                    **existing, "submission_status": "terminal",
                    "provider_status": "cancelled_before_submission",
                }
                if record != expected:
                    raise ValueError("Cancellation must preserve the prepared operation history")
            if not cancelled_before_submission(record):
                raise ValueError("Cancelled operations cannot acquire provider task identities")
        elif existing is not None and cancelled_before_submission(existing):
            raise ValueError("A never-submitted cancellation cannot be replaced")
        if existing is not None:
            mutable = {"submission_status", "provider_task_id", "provider_status", "review_status", "cost"}
            if (
                {key: value for key, value in record.items() if key not in mutable}
                != {key: value for key, value in existing.items() if key not in mutable}
            ):
                raise ValueError("Registered request identity is immutable")
            if existing["provider_task_id"] not in (None, record["provider_task_id"]):
                raise ValueError("A provider task identity cannot be replaced")
            before, after = existing["submission_status"], record["submission_status"]
            if before != after and after not in TRANSITIONS.get(before, set()):
                raise ValueError("Invalid operation transition")
            if before == "prepared" and after == "terminal" and not cancelled_before_submission(record):
                raise ValueError("Prepared closure requires explicit never-submitted cancellation")
        if cancelled_before_submission(record) and record["review_status"] != "approved":
            scope = lifecycle_scope_findings(path.parent, record)
        elif (
            existing is not None and existing["submission_status"] != "prepared"
            and record["review_status"] != "approved"
        ):
            scope = lifecycle_scope_findings(path.parent, existing)
        else:
            scope = record_scope_findings(path.parent, record, context=record.get("context"))
        if scope:
            raise ValueError("; ".join(finding.message for finding in scope))
    descriptor, name = tempfile.mkstemp(
        prefix=".task_ids-", suffix=".tmp", dir=path.parent
    )
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w") as handle:
            json.dump(document, handle, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)


def require_current_approval_contract(
    root: Path, record: dict[str, Any], *, unit_id: str | None = None,
    production_scope: bool = False, context: Any = None,
) -> None:
    scope = record_scope_findings(
        root, record, unit_id=unit_id, production_scope=production_scope, context=context,
    )
    if scope:
        raise ValueError("; ".join(finding.message for finding in scope))
    version = record.get("schema_version")
    if version == 3:
        if not studio_project(root, record["context"]):
            raise ValueError("Scoped generation requires an initialized valid unit Studio")
        return
    project_path = root / "project.md"
    if version == 1 and project_path.exists():
        try:
            content = project_path.read_text(encoding="utf-8")
            metadata = parse_frontmatter(content) if content.startswith("---") else {}
        except (OSError, UnicodeError, ValueError, TypeError, YAMLError) as error:
            raise ValueError(f"Cannot verify legacy project mode: {error}") from error
        if "approval_mode" in metadata:
            raise ValueError(
                "Explicit approval mode requires a version-2 generation request"
            )
    path = root / "showcase.json"
    if path.is_symlink():
        raise ValueError("Production canvas must not be a symlink")
    if not path.exists():
        if version == 2 and not studio_project(root):
            raise ValueError(
                "Version-2 generation requires a Studio project (a real studio/ "
                "directory and no showcase.json) or a pre-Studio canvas "
                "(showcase.json and current index.html)"
            )
        return
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"Invalid production canvas showcase.json: {error}") from error
    if not isinstance(document, dict):
        raise TypeError("Production canvas must be a JSON object")
    canvas = document.get("canvas")
    if (
        version == 1
        and isinstance(canvas, dict)
        and "approvalContractVersion" in canvas
    ):
        raise ValueError(
            "Versioned production canvas requires a version-2 generation request"
        )
    if version != 2:
        return
    if not isinstance(canvas, dict) or canvas.get("approvalContractVersion") != 1:
        raise ValueError("Version-2 generation requires a versioned production canvas")
    stage = canvas.get("currentStage")
    if not isinstance(stage, str) or not stage:
        raise ValueError("Production canvas requires a current stage")
    index_path = root / "index.html"
    if index_path.is_symlink():
        raise ValueError("Generated production canvas must not be a symlink")
    generator = (
        Path(__file__).resolve().parents[1]
        / "skills/showcase-html/scripts/generate_showcase.py"
    )
    result = subprocess.run(
        [sys.executable, str(generator), str(root), "--check", "--stage", stage],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stdout + result.stderr).strip()
        raise ValueError(f"Production canvas checkpoint failed: {detail}")


def prepare_operation(
    root: Path,
    request: dict[str, Any],
    capabilities: dict[str, Any],
    review: dict[str, Any],
    required_rule_ids: list[str],
    allow_board_references: bool = False,
    *, unit_id: str | None = None, production_scope: bool = False,
) -> None:
    _register_operation(
        root, request, capabilities, review, required_rule_ids,
        allow_board_references, unit_id=unit_id, production_scope=production_scope,
    )


def _register_operation(
    root: Path, request: dict[str, Any], capabilities: dict[str, Any],
    review: dict[str, Any], required_rule_ids: list[str],
    allow_board_references: bool, *, unit_id: str | None,
    production_scope: bool, adoption: tuple[str, str, bool] | None = None,
) -> None:
    findings = validate_request(
        root, request, capabilities, allow_board_references,
        unit_id=unit_id, production_scope=production_scope,
    )
    findings.extend(
        validate_review(review, request.get("request_sha256", ""), required_rule_ids)
    )
    if findings:
        raise ValueError("; ".join(finding.message for finding in findings))
    with selection_lock(root), registry_lock(root) as path:
        require_current_approval_contract(
            root, request, unit_id=unit_id, production_scope=production_scope,
        )
        current = prepared_evidence_findings(
            root, request, allow_board_references, unit_id=unit_id,
            production_scope=production_scope,
        )
        if current:
            raise ValueError("; ".join(finding.message for finding in current))
        mode_findings = project_mode_findings(root, request)
        if mode_findings:
            raise ValueError("; ".join(finding.message for finding in mode_findings))
        registry = read_registry(path)
        if any(
            record["operation_id"] == request["operation_id"]
            or record["asset_id"] == request["asset_id"]
            for record in registry["tasks"]
        ):
            raise ValueError(
                "Operation or asset identity already exists; reconcile or use an explicitly authorized new take"
            )
        record = deepcopy(request)
        if adoption is not None:
            task_id, status, terminal = adoption
            record.update(
                submission_status="terminal" if terminal else "acknowledged",
                provider_task_id=task_id, provider_status=status,
            )
            if record["schema_version"] == 3 and status == "succeeded":
                record["review_status"] = "review"
        registry["tasks"].append(record)
        _replace_registry(path, registry)


def adopt_submitted_operation(
    root: Path,
    request: dict[str, Any],
    capabilities: dict[str, Any],
    review: dict[str, Any],
    required_rule_ids: list[str],
    provider_task_id: str,
    provider_status: str,
    terminal: bool,
    *, unit_id: str | None = None, production_scope: bool = False,
) -> None:
    if not provider_task_id.strip() or not provider_status.strip():
        raise ValueError(
            "Adopting a submitted job needs its provider task ID and status"
        )
    _register_operation(
        root,
        request,
        capabilities,
        review,
        required_rule_ids,
        allow_board_references=True,
        unit_id=unit_id,
        production_scope=production_scope,
        adoption=(provider_task_id, provider_status, terminal),
    )


def transition_operation(
    root: Path,
    operation_id: str,
    expected_status: str,
    new_status: str,
    provider_task_id: str | None = None,
    provider_status: str | None = None,
    allow_board_references: bool = False,
) -> None:
    validate_layout(root)
    cancelling = provider_status == "cancelled_before_submission"
    if cancelling and (
        expected_status != "prepared" or new_status != "terminal" or provider_task_id is not None
    ):
        raise ValueError("Cancellation requires a never-submitted prepared operation")
    if expected_status == "prepared" and new_status == "terminal" and not cancelling:
        raise ValueError("Prepared closure requires explicit never-submitted cancellation")
    initial = next(
        (item for item in read_registry(root / "task_ids.json")["tasks"]
         if item["operation_id"] == operation_id),
        None,
    )
    if initial is not None:
        if cancelling:
            require_never_submitted(initial)
        scope = (
            lifecycle_scope_findings(root, {**initial, "submission_status": "terminal"})
            if cancelling else lifecycle_scope_findings(root, initial)
        )
        if scope:
            raise ValueError("; ".join(finding.message for finding in scope))
    if new_status not in TRANSITIONS.get(expected_status, set()):
        raise ValueError(
            "Invalid operation transition; unknown acceptance cannot become a new submission"
        )
    with selection_lock(root), registry_lock(root) as path:
        registry = read_registry(path)
        record = next(
            (
                item
                for item in registry["tasks"]
                if item["operation_id"] == operation_id
            ),
            None,
        )
        if record is None or record["submission_status"] != expected_status:
            raise ValueError("Operation missing or stale expected state")
        if cancelling:
            require_never_submitted(record)
        scope = (
            lifecycle_scope_findings(root, {**record, "submission_status": "terminal"})
            if cancelling else lifecycle_scope_findings(root, record)
        )
        if scope:
            raise ValueError("; ".join(finding.message for finding in scope))
        if new_status == "submitting":
            evidence_findings = prepared_evidence_findings(
                root, record, allow_board_references, context=record.get("context"),
            )
            if evidence_findings:
                raise ValueError(
                    "; ".join(finding.message for finding in evidence_findings)
                )
            require_current_approval_contract(root, record, context=record.get("context"))
        if provider_task_id and record["provider_task_id"] not in (
            None,
            provider_task_id,
        ):
            raise ValueError("A provider task identity cannot be replaced")
        record["submission_status"] = new_status
        if provider_task_id is not None:
            record["provider_task_id"] = provider_task_id
        if provider_status is not None:
            record["provider_status"] = provider_status
        if record["schema_version"] == 3 and record["provider_status"] == "succeeded":
            record["review_status"] = "review"
        if schema_findings(record, "generation-request.schema.json"):
            raise ValueError("Transition requires a valid provider acknowledgment")
        _replace_registry(path, registry)
