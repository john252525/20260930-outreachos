"""Deterministic normalization of segment scoring weights."""

from typing import Final

REQUIRED_KEYS: Final[frozenset[str]] = frozenset(
    {
        "industry_match",
        "size_match",
        "geo_match",
        "pain_match",
        "trigger_match",
        "role_match",
    }
)


def normalize_weights(weights: dict[str, float] | None) -> tuple[dict[str, float], list[str]]:
    """Normalize weights to sum 1.0. Returns (weights, warnings)."""
    warnings: list[str] = []
    incoming = dict(weights or {})

    extra = set(incoming) - REQUIRED_KEYS
    if extra:
        warnings.append(f"extra keys dropped: {sorted(extra)}")
    incoming = {k: v for k, v in incoming.items() if k in REQUIRED_KEYS}

    negatives = [k for k, v in incoming.items() if v is not None and v < 0]
    if negatives:
        warnings.append(f"negative weights clamped to 0: {sorted(negatives)}")
    incoming = {k: max(0.0, float(v)) if v is not None else 0.0 for k, v in incoming.items()}

    missing = REQUIRED_KEYS - set(incoming)
    if missing:
        warnings.append(f"missing keys filled with 0: {sorted(missing)}")
        for k in missing:
            incoming[k] = 0.0

    total = sum(incoming.values())
    if total <= 0:
        warnings.append("all weights zero, using uniform distribution")
        n = len(REQUIRED_KEYS)
        # Keep full precision so the sum stays numerically 1.0 and all values equal.
        return dict.fromkeys(sorted(REQUIRED_KEYS), 1.0 / n), warnings

    normalized = {k: round(v / total, 6) for k, v in incoming.items()}

    # Rounding compensation: guarantee the sum is exactly 1.0
    diff = round(1.0 - sum(normalized.values()), 6)
    if abs(diff) > 0:
        max_key = max(normalized, key=lambda k: normalized[k])
        normalized[max_key] = round(normalized[max_key] + diff, 6)

    return normalized, warnings


def is_valid(weights: dict[str, float]) -> bool:
    """Whether weights are valid: all keys present, non-negative, sum to 1.0."""
    if set(weights.keys()) != REQUIRED_KEYS:
        return False
    if any(v < 0 for v in weights.values()):
        return False
    return abs(sum(weights.values()) - 1.0) < 1e-6
