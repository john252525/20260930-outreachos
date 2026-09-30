"""Deterministic completeness scoring for a Brief."""

from typing import Any

from brief_service.scoring.constants import FIELD_WEIGHTS, GROUP_WEIGHTS


def _is_filled(value: Any) -> bool:
    """Whether a value counts as filled."""
    if value is None:
        return False
    if isinstance(value, str):
        return len(value.strip()) > 0
    if isinstance(value, (list, dict)):
        return len(value) > 0
    if isinstance(value, (int, float)):
        return True
    return True


def _field_score(group_name: str, field_name: str, data: dict[str, Any]) -> float:
    """Score of a single field: 1.0 if filled, else 0.0."""
    if group_name == "offering" and field_name == "price_range":
        pr = data.get("price_range") or {}
        if not isinstance(pr, dict):
            return 0.0
        model = pr.get("model")
        has_numbers = pr.get("min") is not None or pr.get("max") is not None
        if model and model != "unknown":
            return 1.0
        if has_numbers:
            return 1.0
        return 0.0

    value = data.get(field_name)
    return 1.0 if _is_filled(value) else 0.0


def compute_completeness(brief_data: dict[str, Any]) -> float:
    """Compute the overall completeness score (0.0-1.0)."""
    total = 0.0
    for group_name, group_weight in GROUP_WEIGHTS.items():
        group_data = brief_data.get(group_name) or {}
        if not isinstance(group_data, dict):
            group_data = {}
        group_score = 0.0
        for field_name, field_weight in FIELD_WEIGHTS.get(group_name, {}).items():
            group_score += field_weight * _field_score(group_name, field_name, group_data)
        total += group_weight * group_score
    return round(min(max(total, 0.0), 1.0), 4)
