"""Deterministic missing-field analysis for a Brief."""

from typing import Any

from brief_service.scoring.completeness import _field_score
from brief_service.scoring.constants import FIELD_PRIORITY, FIELD_WEIGHTS, FIELD_WHY_NEEDED

_PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def analyze_missing_info(brief_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Return missing fields sorted by priority."""
    missing: list[dict[str, Any]] = []
    for group_name, field_weights in FIELD_WEIGHTS.items():
        group_data = brief_data.get(group_name) or {}
        if not isinstance(group_data, dict):
            group_data = {}
        for field_name in field_weights:
            if _field_score(group_name, field_name, group_data) < 1.0:
                full_path = f"{group_name}.{field_name}"
                missing.append(
                    {
                        "field": full_path,
                        "why_needed": FIELD_WHY_NEEDED.get(full_path, ""),
                        "priority": FIELD_PRIORITY.get(full_path, "medium"),
                    }
                )
    missing.sort(key=lambda m: _PRIORITY_ORDER.get(m["priority"], 1))
    return missing


def get_next_priority_field(brief_data: dict[str, Any]) -> dict[str, Any] | None:
    """Return the single highest-priority missing field, or None if all filled."""
    missing = analyze_missing_info(brief_data)
    return missing[0] if missing else None
