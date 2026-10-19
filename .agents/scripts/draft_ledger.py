from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from operation_store import (
    lifecycle_scope_findings,
    registry_lock,
    selection_lock,
    validate_layout,
)
from validate_request import (
    SEEDANCE_25_MODEL,
    contained_path,
    draft_selected,
    record_scope_findings,
    schema_findings,
)

DRAFT_LIFETIME_DAYS = 7
EXPIRY_WARNING_DAYS = 2
LEDGER_FILE = "drafts.json"
REGISTRY_FILE = "task_ids.json"
STATUSES = ("drafted", "approved", "promoted", "expired")


def today() -> date:
    return datetime.now(UTC).date()


def read_json(path: Path, default: Any) -> Any:
    if path.is_symlink():
        raise ValueError("Ledger and registry must not be symlinks")
    if not path.is_file():
        return default
    return json.loads(path.read_text())


def read_ledger(project: Path) -> dict[str, Any]:
    ledger = read_json(project / LEDGER_FILE, {"schema_version": 1, "drafts": []})
    if not isinstance(ledger, dict) or ledger.get("schema_version") != 1 or not isinstance(ledger.get("drafts"), list):
        raise ValueError(f"{LEDGER_FILE} is not a version 1 draft ledger")
    return ledger


def require_promotable_draft(
    project: Path, task: dict[str, Any], final_operation_id: str,
) -> None:
    entries = [
        entry for entry in read_ledger(project)["drafts"]
        if isinstance(entry, dict) and entry.get("draft_task_id") == task["provider_task_id"]
    ]
    if len(entries) != 1:
        raise ValueError("Promotion requires one registered draft ledger entry")
    entry = entries[0]
    expected = {
        "operation_id": task["operation_id"], "draft_task_id": task["provider_task_id"],
        "prompt_sha256": task["prompt_sha256"], "request_sha256": task["request_sha256"],
        "context": task["context"],
    }
    if any(entry.get(key) != value for key, value in expected.items()):
        raise ValueError("Draft ledger identity differs from the registered draft")
    if entry.get("status") != "approved" and not (
        entry.get("status") == "promoted" and entry.get("final_operation_id") == final_operation_id
    ):
        raise ValueError("Promotion requires an approved draft ledger entry")
    try:
        submitted = date.fromisoformat(entry["submitted"])
        expires = date.fromisoformat(entry["expires"])
    except (KeyError, ValueError, TypeError) as error:
        raise ValueError("Draft ledger dates are invalid") from error
    if expires != expiry_for(submitted) or not submitted <= today() <= expires:
        raise ValueError("Draft is outside its seven-day promotion window")


def write_ledger(project: Path, ledger: dict[str, Any]) -> None:
    validate_layout(project)
    with selection_lock(project), registry_lock(project):
        _write_ledger(project, ledger)


def validate_ledger_update(project: Path, ledger: dict[str, Any]) -> None:
    previous = {entry["draft_task_id"]: entry for entry in read_ledger(project)["drafts"]}
    identifiers = [entry["draft_task_id"] for entry in ledger["drafts"]]
    if len(identifiers) != len(set(identifiers)) or not set(previous).issubset(identifiers):
        raise ValueError("Draft ledger writes must preserve unique draft history")
    for entry in ledger["drafts"]:
        existing = previous.get(entry["draft_task_id"])
        if entry == existing:
            continue
        if existing is not None and any(
            entry.get(key) != existing.get(key) for key in (
                "asset", "operation_id", "draft_task_id", "prompt_sha256",
                "request_sha256", "context", "submitted", "expires",
            )
        ):
            raise ValueError("Draft identity is immutable")
        if existing is not None and existing.get("final_operation_id") not in (
            None, entry.get("final_operation_id"),
        ):
            raise ValueError("A recorded final operation cannot be replaced")
        task = registry_task(project, entry["operation_id"])
        scope = (
            lifecycle_scope_findings(project, task)
            if task is not None and entry.get("status") in ("drafted", "expired")
            else record_scope_findings(project, task or {}, context=entry.get("context"))
        )
        if scope:
            raise ValueError("; ".join(finding.message for finding in scope))
        if "context" not in entry and not (task and task.get("schema_version") == 3):
            continue
        if task is None or entry.get("context") != task.get("context"):
            raise ValueError("Draft ledger must match its registered scoped operation")
        if schema_findings(task, "generation-request.schema.json") or (
            not SEEDANCE_25_MODEL.search(task["model"].lower())
            or task["params"].get("draft") is not True
            or task["params"].get("resolution") != "480p"
            or task["provider_task_id"] != entry["draft_task_id"]
            or task["prompt_sha256"] != entry["prompt_sha256"]
            or task["request_sha256"] != entry["request_sha256"]
            or entry["status"] not in STATUSES
            or entry["expires"] != expiry_for(date.fromisoformat(entry["submitted"])).isoformat()
        ):
            raise ValueError("Invalid registered scoped draft identity")
        if entry["take"] is not None:
            contained_path(project, entry["take"])
            if entry["take"] != task.get("extensions", {}).get("expected_output"):
                raise ValueError("Draft take must match its registered output")
        if entry["status"] in ("approved", "promoted") and (
            task["submission_status"] != "terminal"
            or task["provider_status"] != "succeeded"
            or not draft_selected(project, task, require_decision=True)
        ):
            raise ValueError("Draft approval requires successful output and a current selection")
        if entry["status"] == "approved" and today() > date.fromisoformat(entry["expires"]):
            raise ValueError("Expired draft cannot be approved for promotion")
        final_id = entry["final_operation_id"]
        if (entry["status"] == "promoted") != (final_id is not None):
            raise ValueError("Promoted draft requires its final operation")
        if final_id is not None:
            final = registry_task(project, final_id)
            if final is None or (
                final.get("context") != task["context"]
                or final["params"].get("draft_task_id") != entry["draft_task_id"]
                or final["model"] != task["model"]
                or final["transport"] != task["transport"]
                or final["prompt_sha256"] != task["prompt_sha256"]
                or final["submission_status"] not in ("acknowledged", "terminal")
                or not final["provider_task_id"]
            ):
                raise ValueError("Promotion requires an acknowledged same-context final")


def _write_ledger(project: Path, ledger: dict[str, Any]) -> None:
    if ledger.get("schema_version") != 1 or not isinstance(ledger.get("drafts"), list):
        raise ValueError("Invalid draft ledger")
    for entry in ledger.get("drafts", []):
        if "context" in entry and schema_findings(entry["context"], "production-context.schema.json"):
            raise ValueError("Invalid draft ledger context")
    validate_ledger_update(project, ledger)
    path = project / LEDGER_FILE
    if path.is_symlink():
        raise ValueError("Draft ledger must not be a symlink")
    descriptor, name = tempfile.mkstemp(prefix=".drafts-", suffix=".tmp", dir=project)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w") as stream:
            json.dump(ledger, stream, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
        directory = os.open(project, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)


def expiry_for(submitted: date) -> date:
    return submitted + timedelta(days=DRAFT_LIFETIME_DAYS)


def effective_status(entry: dict[str, Any], on: date) -> str:
    if entry["status"] == "promoted":
        return "promoted"
    if on > date.fromisoformat(entry["expires"]):
        return "expired"
    return entry["status"]


def days_left(entry: dict[str, Any], on: date) -> int:
    return (date.fromisoformat(entry["expires"]) - on).days


def registry_task(project: Path, operation_id: str) -> dict[str, Any] | None:
    registry = read_json(project / REGISTRY_FILE, {"tasks": []})
    return next(
        (task for task in registry["tasks"] if task["operation_id"] == operation_id),
        None,
    )


def record_draft(
    project: Path,
    asset: str,
    operation_id: str,
    draft_task_id: str,
    submitted: date,
    take: str | None = None,
    status: str | None = None,
    final_operation_id: str | None = None,
) -> dict[str, Any]:
    validate_layout(project)
    task = registry_task(project, operation_id)
    if task is not None:
        scope = (
            record_scope_findings(project, task, context=task.get("context"))
            if status in ("approved", "promoted") or final_operation_id is not None
            else lifecycle_scope_findings(project, task)
        )
        if scope:
            raise ValueError("; ".join(finding.message for finding in scope))
    with selection_lock(project), registry_lock(project):
        return _record_draft(
            project, asset, operation_id, draft_task_id, submitted,
            take, status, final_operation_id,
        )


def _record_draft(
    project: Path, asset: str, operation_id: str, draft_task_id: str,
    submitted: date, take: str | None, status: str | None,
    final_operation_id: str | None,
) -> dict[str, Any]:
    if not draft_task_id.strip():
        raise ValueError("A draft needs its provider task ID")
    if status is not None and status not in STATUSES:
        raise ValueError(f"Status must be one of {', '.join(STATUSES)}")
    task = registry_task(project, operation_id)
    if task is None:
        raise ValueError(f"{operation_id} is not in {REGISTRY_FILE}")
    scope = (
        record_scope_findings(project, task, context=task.get("context"))
        if status in ("approved", "promoted") or final_operation_id is not None
        else lifecycle_scope_findings(project, task)
    )
    if scope:
        raise ValueError("; ".join(finding.message for finding in scope))
    if task.get("schema_version") == 3 and schema_findings(task, "generation-request.schema.json"):
        raise ValueError("Invalid scoped draft registry record")
    if task.get("schema_version") == 3 and (
        not SEEDANCE_25_MODEL.search(task["model"].lower())
        or task["params"].get("resolution") != "480p"
        or task["provider_task_id"] != draft_task_id
    ):
        raise ValueError("Scoped drafts require a registered native 480p Seedance task")
    if task["params"].get("draft") is not True:
        raise ValueError(f"{operation_id} was not prepared with draft=true")
    if task["provider_task_id"] not in (None, draft_task_id):
        raise ValueError(
            f"{operation_id} is registered with provider task {task['provider_task_id']}"
        )
    ledger = read_ledger(project)
    entry = next(
        (item for item in ledger["drafts"] if item["draft_task_id"] == draft_task_id),
        None,
    )
    if entry is not None and (
        entry["operation_id"] != operation_id or entry["asset"] != asset
        or entry["request_sha256"] != task["request_sha256"]
        or entry.get("context") != task.get("context")
    ):
        raise ValueError("Draft identity is immutable")
    if entry is None:
        entry = {
            "asset": asset,
            "operation_id": operation_id,
            "draft_task_id": draft_task_id,
            "prompt_sha256": task["prompt_sha256"],
            "request_sha256": task["request_sha256"],
            "take": take,
            "submitted": submitted.isoformat(),
            "expires": expiry_for(submitted).isoformat(),
            "status": "drafted",
            "final_operation_id": None,
        }
        if "context" in task:
            entry["context"] = dict(task["context"])
        ledger["drafts"].append(entry)
    if take is not None:
        if task.get("schema_version") == 3:
            contained_path(project, take)
            if take != task.get("extensions", {}).get("expected_output"):
                raise ValueError("Draft take must match its registered output")
        entry["take"] = take
    if final_operation_id is not None:
        final = registry_task(project, final_operation_id)
        if final is not None:
            scope = record_scope_findings(project, final, context=task.get("context"))
            if scope or final.get("context") != task.get("context"):
                raise ValueError("Final and draft must share the same current context")
        if final is None or final["params"].get("draft_task_id") != draft_task_id:
            raise ValueError(
                f"{final_operation_id} is not a final prepared with this draft_task_id"
            )
        entry["final_operation_id"] = final_operation_id
        status = status or "promoted"
    if status is not None:
        entry["status"] = status
    _write_ledger(project, ledger)
    return entry


def report(project: Path, on: date) -> list[dict[str, Any]]:
    rows = []
    for entry in read_ledger(project)["drafts"]:
        status = effective_status(entry, on)
        remaining = days_left(entry, on)
        rows.append(
            {
                "asset": entry["asset"],
                "draft_task_id": entry["draft_task_id"],
                "status": status,
                "days_left": remaining,
                "expiring_soon": status in ("drafted", "approved")
                and remaining <= EXPIRY_WARNING_DAYS,
                "final_operation_id": entry["final_operation_id"],
            }
        )
    return rows


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Track Seedance drafts for later promotion")
    commands = root.add_subparsers(dest="command", required=True)
    record = commands.add_parser("record", help="Add or update a draft entry")
    record.add_argument("project", type=Path)
    record.add_argument("--asset", required=True)
    record.add_argument("--operation-id", required=True)
    record.add_argument("--draft-task-id", required=True)
    record.add_argument("--submitted", type=date.fromisoformat, default=None)
    record.add_argument("--take")
    record.add_argument("--status", choices=STATUSES)
    record.add_argument("--final-operation-id")
    listing = commands.add_parser("list", help="Report drafts, days left and promotion state")
    listing.add_argument("project", type=Path)
    listing.add_argument("--today", type=date.fromisoformat, default=None)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "record":
            entry = record_draft(
                args.project,
                args.asset,
                args.operation_id,
                args.draft_task_id,
                args.submitted or today(),
                args.take,
                args.status,
                args.final_operation_id,
            )
            print(json.dumps(entry, indent=2))
            return 0
        rows = report(args.project, args.today or today())
    except (ValueError, KeyError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(rows, indent=2))
    return 2 if any(row["expiring_soon"] for row in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
