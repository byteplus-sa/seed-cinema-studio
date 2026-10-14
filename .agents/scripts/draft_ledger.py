from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

DRAFT_LIFETIME_DAYS = 7
EXPIRY_WARNING_DAYS = 2
LEDGER_FILE = "drafts.json"
REGISTRY_FILE = "task_ids.json"
STATUSES = ("drafted", "approved", "promoted", "expired")


def today() -> date:
    return datetime.now(UTC).date()


def read_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text())


def read_ledger(project: Path) -> dict[str, Any]:
    ledger = read_json(project / LEDGER_FILE, {"schema_version": 1, "drafts": []})
    if ledger.get("schema_version") != 1 or not isinstance(ledger.get("drafts"), list):
        raise ValueError(f"{LEDGER_FILE} is not a version 1 draft ledger")
    return ledger


def write_ledger(project: Path, ledger: dict[str, Any]) -> None:
    path = project / LEDGER_FILE
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(ledger, indent=2) + "\n")
    temporary.replace(path)


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
    if not draft_task_id.strip():
        raise ValueError("A draft needs its provider task ID")
    if status is not None and status not in STATUSES:
        raise ValueError(f"Status must be one of {', '.join(STATUSES)}")
    task = registry_task(project, operation_id)
    if task is None:
        raise ValueError(f"{operation_id} is not in {REGISTRY_FILE}")
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
        ledger["drafts"].append(entry)
    if take is not None:
        entry["take"] = take
    if final_operation_id is not None:
        final = registry_task(project, final_operation_id)
        if final is None or final["params"].get("draft_task_id") != draft_task_id:
            raise ValueError(
                f"{final_operation_id} is not a final prepared with this draft_task_id"
            )
        entry["final_operation_id"] = final_operation_id
        status = status or "promoted"
    if status is not None:
        entry["status"] = status
    write_ledger(project, ledger)
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
