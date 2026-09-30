"""Single source of truth for LLM pricing.

All cost calculations go through this module so that we have one number
that feeds both our database (quotas/analytics) and Langfuse (dashboards).

Prices are per 1,000,000 tokens in USD, and vary by time of day for
DeepSeek: off-peak is exactly half of peak.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import structlog

logger = structlog.get_logger()


@dataclass(frozen=True)
class ModelPrice:
    """Price per 1M tokens (USD) for a model at a given tier."""

    input_cache_hit: float
    input_cache_miss: float
    output: float


# DeepSeek peak rates (off-peak = half of these).
# Source: docs/reference/pricing.md (actual as of September 2026).
_PEAK_PRICES: dict[str, ModelPrice] = {
    "deepseek-flash": ModelPrice(
        input_cache_hit=0.006,
        input_cache_miss=0.30,
        output=1.20,
    ),
}

# Peak hours: 01:00-04:00 and 06:00-10:00 UTC, Monday-Friday,
# excluding Chinese public holidays (not modelled here - we only do
# weekday+hour check; holidays are treated as off-peak to be conservative).
_PEAK_HOUR_RANGES: tuple[tuple[int, int], ...] = ((1, 4), (6, 10))

_TOKENS_PER_UNIT = 1_000_000


def is_peak(at: datetime | None = None) -> bool:
    """Whether the given moment falls into DeepSeek peak pricing."""
    now = at or datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    now = now.astimezone(UTC)
    if now.weekday() >= 5:  # Sat/Sun are off-peak
        return False
    return any(start <= now.hour < end for start, end in _PEAK_HOUR_RANGES)


def price_for(model: str, *, at: datetime | None = None) -> ModelPrice | None:
    """Return the effective price for a model, or None if unknown."""
    peak_price = _PEAK_PRICES.get(model)
    if peak_price is None:
        return None
    if is_peak(at):
        return peak_price
    return ModelPrice(
        input_cache_hit=peak_price.input_cache_hit / 2,
        input_cache_miss=peak_price.input_cache_miss / 2,
        output=peak_price.output / 2,
    )


def compute_cost(
    *,
    model: str,
    tokens_in_cache_hit: int,
    tokens_in_cache_miss: int,
    tokens_out: int,
    at: datetime | None = None,
) -> float:
    """Compute the USD cost of a call. Returns 0.0 for unknown models."""
    price = price_for(model, at=at)
    if price is None:
        logger.warning("unknown_model_pricing", model=model)
        return 0.0

    cost = (
        tokens_in_cache_hit * price.input_cache_hit
        + tokens_in_cache_miss * price.input_cache_miss
        + tokens_out * price.output
    ) / _TOKENS_PER_UNIT
    return round(cost, 8)
