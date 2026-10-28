from __future__ import annotations

import argparse
import json
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from pathlib import Path
from typing import Any

from validate_request import (
    contained_path,
    production_context_module,
)


def amount(value: Any, label: str) -> Fraction | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float | Decimal):
        raise TypeError(f"{label} must be a finite nonnegative number")
    try:
        result = Decimal(str(value))
    except InvalidOperation as error:
        raise ValueError(f"{label} must be a finite nonnegative number") from error
    if not result.is_finite() or result < 0:
        raise ValueError(f"{label} must be a finite nonnegative number")
    return Fraction(result)


def json_number(value: Fraction) -> int | float:
    return int(value) if value.denominator == 1 else float(value)


def report_units(project: Path) -> list[str]:
    context_module = production_context_module()
    if context_module.has_production_manifest(project):
        context_module.resolve_production_context(project)
        manifest = json.loads(contained_path(project, "production.json").read_text())
        for unit in manifest["units"]:
            context_module.resolve_context(project, unit["id"])
        return [unit["id"] for unit in manifest["units"]]
    return []


def cancelled_before_submission(record: dict[str, Any]) -> bool:
    return (
        record["submission_status"] == "terminal"
        and record["provider_status"] == "cancelled_before_submission"
        and record["provider_task_id"] is None
    )


def currency_totals(tasks: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for task in tasks:
        currency = task["cost"]["currency"]
        if not isinstance(currency, str) or not currency.strip():
            raise ValueError("Operation cost requires a currency")
        groups.setdefault(currency, []).append(task)
    result = {}
    for currency, records in groups.items():
        estimated = confirmed = reserved = Fraction(0)
        unknown = []
        unconfirmed = []
        missing_estimates = []
        for record in records:
            identifier = record["operation_id"]
            estimate = amount(record["cost"]["estimated"], f"{identifier} estimate")
            actual = amount(record["cost"]["confirmed"], f"{identifier} confirmed cost")
            if estimate is None:
                missing_estimates.append(identifier)
            else:
                estimated += estimate
            if actual is None:
                unconfirmed.append(identifier)
            else:
                confirmed += actual
            if cancelled_before_submission(record) or (
                actual is not None and record["submission_status"] == "terminal"
            ):
                continue
            if estimate is None:
                unknown.append(identifier)
            else:
                reserved += max(Fraction(0), estimate - (actual or Fraction(0)))
        result[currency] = {
            "estimated": estimated,
            "confirmed": confirmed,
            "reserved": reserved,
            "known_exposure": confirmed + reserved,
            "exposure": None if unknown else confirmed + reserved,
            "unknown_operations": sorted(unknown),
            "unconfirmed_operations": sorted(unconfirmed),
            "missing_estimates": sorted(missing_estimates),
        }
    return result


def scope_report(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "currencies": {
            currency: {
                key: json_number(value) if isinstance(value, Fraction) else value
                for key, value in totals.items()
            }
            for currency, totals in currency_totals(tasks).items()
        },
    }


def budget_report(
    project: Path, tasks: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    project = project.resolve()
    if tasks is None:
        from operation_store import read_registry

        tasks = read_registry(project / "task_ids.json")["tasks"]
    units = report_units(project)
    return {
        "source": "task_ids.json",
        "production": scope_report(tasks),
        "units": {
            unit: scope_report([
                task for task in tasks
                if task.get("context", {}).get("unit_id") == unit
            ])
            for unit in units
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only registry cost reporting; never calls a provider")
    parser.add_argument("project", type=Path)
    args = parser.parse_args()
    try:
        report = budget_report(args.project)
    except (OSError, ValueError, TypeError, KeyError) as error:
        print(json.dumps({"ok": False, "error": str(error)}))
        return 1
    print(json.dumps({"ok": True, **report}, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
