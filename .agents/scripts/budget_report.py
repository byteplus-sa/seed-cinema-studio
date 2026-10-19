from __future__ import annotations

import argparse
import json
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from pathlib import Path
from typing import Any

from validate_request import (
    contained_path,
    parse_frontmatter,
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


def brief_metadata(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    return parse_frontmatter(text) if text.startswith("---") else {}


def budget_scopes(project: Path) -> dict[str, dict[str, Any]]:
    shared_path = project / "project.md"
    shared = brief_metadata(contained_path(project, "project.md")) if shared_path.exists() else {}
    budget = shared.get("budget", {})
    if not isinstance(budget, dict):
        raise TypeError("budget must be a mapping")
    if "cap" in budget and "spending_cap" in budget and budget["cap"] != budget["spending_cap"]:
        raise ValueError("Conflicting budget.cap and budget.spending_cap")
    cap = amount(budget.get("cap", budget.get("spending_cap")), "budget.cap")
    currency = budget.get("currency")
    scopes = {"production": {"cap": cap, "currency": currency}}
    context_module = production_context_module()
    if context_module.has_production_manifest(project):
        context_module.resolve_production_context(project)
        manifest = json.loads(contained_path(project, "production.json").read_text())
        for unit in manifest["units"]:
            context = context_module.resolve_context(project, unit["id"])
            effective = context_module.context_fingerprint_payload(context)["effective_settings"]
            allocation = effective.get("unit_budget", {})
            scopes[f"unit:{unit['id']}"] = {
                "cap": amount(allocation.get("cap"), "unit_budget.cap"),
                "currency": allocation.get("currency", currency),
            }
    return scopes


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


def scope_report(config: dict[str, Any], tasks: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "cap": None if config["cap"] is None else json_number(config["cap"]),
        "currency": config["currency"],
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
    configs = budget_scopes(project)
    return {
        "source": "task_ids.json",
        "production": scope_report(configs["production"], tasks),
        "units": {
            unit.removeprefix("unit:"): scope_report(config, [
                task for task in tasks
                if task.get("context", {}).get("unit_id") == unit.removeprefix("unit:")
            ])
            for unit, config in configs.items() if unit != "production"
        },
    }


def check_budget(
    project: Path, tasks: list[dict[str, Any]] | None, request: dict[str, Any],
) -> None:
    configs = budget_scopes(project)
    unit = request.get("context", {}).get("unit_id")
    unit_scope = f"unit:{unit}"
    applicable = ["production"] + ([unit_scope] if unit_scope in configs else [])
    capped = [name for name in applicable if configs[name]["cap"] is not None]
    if not capped:
        return
    if tasks is None:
        from operation_store import read_registry

        tasks = read_registry(project / "task_ids.json")["tasks"]
    estimate = amount(request["cost"]["estimated"], "Request estimate")
    if estimate is None:
        raise ValueError("Capped scope requires an explicit request cost estimate")
    records = [task for task in tasks if task["operation_id"] != request["operation_id"]]
    records.append(request)
    for name in capped:
        config = configs[name]
        currency = config["currency"]
        if not isinstance(currency, str) or not currency.strip():
            raise ValueError(f"{name} budget cap requires an explicit currency")
        relevant = records if name == "production" else [
            task for task in records
            if task.get("context", {}).get("unit_id") == name.removeprefix("unit:")
        ]
        totals = currency_totals(relevant)
        if set(totals) - {currency}:
            raise ValueError(f"{name} cap cannot combine different cost currencies")
        current = totals.get(currency)
        if current is None:
            continue
        if current["unknown_operations"]:
            raise ValueError(f"{name} cap has unknown exposure; reconcile missing estimates or billing")
        if current["known_exposure"] > config["cap"]:
            raise ValueError(f"{name} budget cap exceeded by reserved and confirmed costs")


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only registry budget accounting; never calls a provider")
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
