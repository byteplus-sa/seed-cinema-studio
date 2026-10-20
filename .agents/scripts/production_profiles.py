from __future__ import annotations

import json
import math
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

_CATALOG = json.loads(
    (Path(__file__).resolve().parents[1] / "catalog/production-profiles.json").read_text()
)
_PROFILES: list[dict[str, Any]] = _CATALOG["profiles"]
_EPISODE_FIELDS = {
    "duration_s": ("production", "target_duration_s"),
    "count": ("production", "unit_count"),
    "aspect": ("delivery", "aspect"),
    "scenes": ("production", "scenes"),
    "max_recurring_cast": ("production", "max_recurring_cast"),
}
_AUTHORITY_FIELDS = (
    "approval_mode", "approval", "authorization", "rights", "budget", "locked", "locks",
)
_BUDGET_RUNTIME_FIELDS = frozenset({
    "estimated", "confirmed", "unknown", "spent", "estimated_spend",
    "confirmed_spend", "unknown_spend", "reserved", "reservations",
})
_MISSING = object()


def review_mode(metadata: dict[str, Any]) -> str:
    value = metadata.get("review_mode", "default")
    if not isinstance(value, str) or value not in ("default", "strict"):
        raise ValueError("review_mode must be default or strict")
    return value


def load_profile(format_id: str | None = None) -> dict[str, Any]:
    if format_id is not None and not isinstance(format_id, str):
        raise ValueError("format must be a supported profile id or None")
    for profile in _PROFILES:
        if profile["id"] == format_id:
            return deepcopy(profile)
    raise ValueError(f"Unsupported format profile: {format_id!r}")


def _mapping(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{path} must be a mapping with string keys")
    return value


def _number(value: Any, path: str, *, zero: bool = False, integer: bool = False) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, int | float)
        or (isinstance(value, float) and not math.isfinite(value))
        or (value < 0 if zero else value <= 0)
        or (integer and not isinstance(value, int))
    ):
        kind = "nonnegative" if zero else "positive"
        raise ValueError(f"{path} must be a finite {kind} {'integer' if integer else 'number'}")


def _merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def _validate_market(market: dict[str, Any]) -> None:
    languages = market.get("dialogue_languages")
    if languages is not None and (
        not isinstance(languages, list)
        or not all(isinstance(entry, dict) and entry.get("language") for entry in languages)
    ):
        raise ValueError("market.dialogue_languages must list entries with a language")
    for field in ("subtitle_languages", "cultural_constraints", "content_limits", "unverified"):
        if market.get(field) is not None and not isinstance(market[field], list):
            raise ValueError(f"market.{field} must be a list")


def _normalize(metadata: dict[str, Any], label: str) -> dict[str, Any]:
    result = deepcopy(_mapping(metadata, label))
    review_mode(result)
    if "locks" in result:
        raise ValueError(f"{label}.locks is unsupported; use shared.locked")
    for group in (
        "production", "delivery", "market", "episode", "locked", "directorial_axes",
    ):
        if group in result:
            if group in ("market", "episode") and result[group] is None:
                continue
            _mapping(result[group], f"{label}.{group}")
    if result.get("market") is not None:
        _validate_market(result["market"])
    production = result.setdefault("production", {})
    delivery = result.setdefault("delivery", {})
    for legacy, (group, modern) in _EPISODE_FIELDS.items():
        value = (result.get("episode") or {}).get(legacy)
        if value is None:
            continue
        if modern in result[group] and result[group][modern] != value:
            raise ValueError(f"{label}.episode.{legacy} conflicts with {label}.{group}.{modern}")
        result[group][modern] = deepcopy(value)
    for field in ("target_duration_s", "unit_count", "max_recurring_cast"):
        if field in production:
            _number(production[field], f"{label}.production.{field}", integer=field != "target_duration_s")
    for field in ("genre", "medium"):
        if field in production and (
            not isinstance(production[field], str) or not production[field].strip()
        ):
            raise ValueError(f"{label}.production.{field} must be nonempty text")
    for group, field in ((production, "beats"), (production, "scenes"), (delivery, "cards")):
        if field in group and not isinstance(group[field], list):
            raise ValueError(f"{label}.{field} must be a list")
    if "duration_range_s" in production:
        duration_range = production["duration_range_s"]
        if not isinstance(duration_range, list) or len(duration_range) != 2:
            raise ValueError(f"{label}.production.duration_range_s must contain two numbers")
        for value in duration_range:
            _number(value, f"{label}.production.duration_range_s")
        if duration_range[0] > duration_range[1]:
            raise ValueError(f"{label}.production.duration_range_s must be ordered")
        if (
            "target_duration_s" in production
            and not duration_range[0] <= production["target_duration_s"] <= duration_range[1]
        ):
            raise ValueError(
                f"{label}.production.target_duration_s conflicts with "
                f"{label}.production.duration_range_s"
            )
    if "aspect" in delivery:
        aspect = delivery["aspect"]
        if not isinstance(aspect, str) or not re.fullmatch(r"[1-9]\d*:[1-9]\d*", aspect):
            raise ValueError(f"{label}.delivery.aspect must be a positive integer ratio like 9:16")
    for field in ("fps", "width", "height"):
        if field in delivery:
            _number(delivery[field], f"{label}.delivery.{field}", integer=field != "fps")
            if field != "fps" and delivery[field] % 2:
                raise ValueError(f"{label}.delivery.{field} must be even")
    if "approval_mode" in result and result["approval_mode"] not in (
        "approve_for_me", "ask_for_approval",
    ):
        raise ValueError(f"{label}.approval_mode must be approve_for_me or ask_for_approval")
    for axis, record in result.get("directorial_axes", {}).items():
        _mapping(record, f"{label}.directorial_axes.{axis}")
    return result


def _format_mirrors(metadata: dict[str, Any]) -> list[str]:
    mirrors = []
    for group, field in ((metadata, "format"), (metadata["production"], "format")):
        if field in group:
            value = group[field]
            if value is None:
                raise ValueError("Explicit format must be a supported profile id")
            load_profile(value)
            mirrors.append(value)
    return mirrors


def _select_format(
    shared: dict[str, Any], unit: dict[str, Any], format_id: str | None, workflow: str | None,
) -> str | None:
    if workflow not in (None, "film-production", "micro-drama"):
        raise ValueError(f"Unsupported workflow: {workflow!r}")
    load_profile(format_id)
    mirrors = _format_mirrors(shared) + _format_mirrors(unit)
    selected = format_id if format_id is not None else (mirrors[0] if mirrors else None)
    if any(mirror != selected for mirror in mirrors):
        raise ValueError("format conflict: brief mirrors must agree with the production format")
    if selected is None and workflow == "micro-drama":
        selected = "micro-drama"
    return selected


def _check_authority(shared: dict[str, Any], unit: dict[str, Any]) -> None:
    for field in _AUTHORITY_FIELDS:
        if field not in unit:
            continue
        if field not in shared:
            raise ValueError(f"unit.{field} cannot replace production-wide {field}")
        shared_value, unit_value = shared[field], unit[field]
        if field == "budget":
            shared_value = {
                key: value for key, value in _mapping(shared_value, "shared.budget").items()
                if key not in _BUDGET_RUNTIME_FIELDS
            }
            unit_value = {
                key: value for key, value in _mapping(unit_value, "unit.budget").items()
                if key not in _BUDGET_RUNTIME_FIELDS
            }
        if unit_value != shared_value:
            raise ValueError(f"unit.{field} cannot replace production-wide {field}")
    for axis, record in shared.get("directorial_axes", {}).items():
        if record.get("source") not in ("user_confirmed", "agent_confirmed"):
            continue
        for source in (shared, unit):
            if axis in source and source[axis] != record.get("value"):
                raise ValueError(f"{axis} conflicts with confirmed directorial_axes.{axis}")
        override = unit.get("directorial_axes", {}).get(axis, _MISSING)
        if override is not _MISSING and override != record:
            raise ValueError(f"unit.directorial_axes.{axis} conflicts with a confirmed lock")


def _validate_unit_budget(budget: Any, allocation: Any) -> None:
    allocation = _mapping(allocation, "unit_budget")
    if set(allocation) - {"cap", "currency"} or "cap" not in allocation:
        raise ValueError("unit_budget accepts only cap and optional currency, not spending totals")
    _number(allocation["cap"], "unit_budget.cap", zero=True)
    budget = _mapping(budget, "budget")
    _number(budget.get("cap"), "budget.cap", zero=True)
    if allocation["cap"] > budget["cap"]:
        raise ValueError("unit_budget.cap cannot exceed production budget.cap")
    if allocation.get("currency", budget.get("currency")) != budget.get("currency"):
        raise ValueError("unit_budget.currency must match production budget.currency")


def _check_allocation(shared: dict[str, Any], unit: dict[str, Any]) -> None:
    for settings in (shared, unit):
        if "unit_budget" in settings:
            _validate_unit_budget(shared.get("budget", {}), settings["unit_budget"])
    if (
        "unit_budget" in shared and "unit_budget" in unit
        and unit["unit_budget"]["cap"] > shared["unit_budget"]["cap"]
    ):
        raise ValueError("unit_budget.cap cannot increase the shared unit allocation")


def _lock_items(locked: dict[str, Any], prefix: str = "") -> list[tuple[str, Any]]:
    items = []
    for key, value in locked.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict) and value:
            items.extend(_lock_items(value, path))
        else:
            items.append((path, value))
    return items


def _lookup(metadata: dict[str, Any], path: str) -> Any:
    value: Any = metadata
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return _MISSING
        value = value[part]
    return value


def _apply_locks(
    shared: dict[str, Any], explicit: dict[str, Any], effective: dict[str, Any],
) -> None:
    applied: dict[str, Any] = {}
    for path, value in _lock_items(shared.get("locked", {})):
        parts = path.split(".")
        if (
            not all(parts)
            or parts[0] in (*_AUTHORITY_FIELDS, "review_mode", "format", "profile", "workflow")
            or parts[:2] == ["production", "format"]
        ):
            raise ValueError(f"Unsupported locked path: {path}")
        if parts[0] == "episode" and len(parts) == 2 and parts[1] in _EPISODE_FIELDS:
            path = ".".join(_EPISODE_FIELDS[parts[1]])
            parts = path.split(".")
        if path in applied and applied[path] != value:
            raise ValueError(f"Conflicting locked declarations for {path}")
        applied[path] = value
        for source in (shared, explicit):
            current = _lookup(source, path)
            if current is not _MISSING and current != value:
                raise ValueError(f"locked.{path} conflicts with explicit {path}")
            if len(parts) == 1:
                axis_value = _lookup(source, f"directorial_axes.{path}.value")
                if axis_value is not _MISSING and axis_value != value:
                    raise ValueError(f"locked.{path} conflicts with directorial_axes.{path}")
        target = effective
        for part in parts[:-1]:
            target = _mapping(target.setdefault(part, {}), f"locked.{path}")
        target[parts[-1]] = deepcopy(value)


def resolve_brief(
    shared: dict[str, Any],
    unit: dict[str, Any] | None = None,
    format_id: str | None = None,
    workflow: str | None = None,
) -> dict[str, Any]:
    shared_settings = _normalize(shared, "shared")
    unit_settings = _normalize({} if unit is None else unit, "unit")
    selected = _select_format(shared_settings, unit_settings, format_id, workflow)
    profile = load_profile(selected)
    _check_authority(shared_settings, unit_settings)
    _check_allocation(shared_settings, unit_settings)
    explicit = _merge(shared_settings, unit_settings)
    if "budget" in shared_settings:
        explicit["budget"] = deepcopy(shared_settings["budget"])
    _apply_locks(shared_settings, explicit, explicit)
    effective = _merge(profile["defaults"], explicit)
    _check_allocation(shared_settings, effective)
    if (
        "target_duration_s" in explicit["production"]
        and "duration_range_s" not in explicit["production"]
    ):
        effective["production"].pop("duration_range_s", None)
    if (
        {"target_duration_s", "duration_range_s"} & explicit["production"].keys()
        and "scenes" not in explicit["production"]
    ):
        effective["production"].pop("scenes", None)
    if "scenes" in explicit["production"] and "beats" not in explicit["production"]:
        effective["production"].pop("beats", None)
    _normalize(
        {"production": effective["production"], "delivery": effective["delivery"]},
        "effective",
    )
    effective["production"].pop("format", None)
    effective["format"] = selected
    effective["workflow"] = profile["workflow"]
    effective["profile"] = profile
    if "review_mode" in explicit:
        effective["review_mode"] = review_mode(explicit)
    return effective
