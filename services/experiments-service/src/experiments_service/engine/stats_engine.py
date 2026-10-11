"""Statistical engine for A/B experiments.

Two-proportion z-test with Wilson confidence intervals. For more than two
variants, the best arm is compared pairwise against the rest with a Bonferroni
correction.
"""

import math
from dataclasses import dataclass, field
from typing import Any


@dataclass
class VariantStats:
    variant_id: str
    sent: int
    positive_replied: int
    replied: int
    meetings_booked: int
    primary_metric_value: float
    confidence_interval: tuple[float, float]


@dataclass
class ExperimentResult:
    variants: list[VariantStats] = field(default_factory=list)
    winner_variant_id: str | None = None
    is_significant: bool = False
    p_value: float | None = None
    reason: str = ""


class StatsEngine:
    def __init__(self, *, confidence_level: float = 0.95) -> None:
        self._confidence_level = confidence_level

    def compute(
        self,
        *,
        variants_data: list[dict[str, Any]],
        primary_metric: str,
        sample_size_per_variant: int,
        minimum_detectable_effect: float,
    ) -> ExperimentResult:
        stats: list[VariantStats] = []
        for v in variants_data:
            sent = int(v.get("sent", 0) or 0)
            metric_value = self._metric_value(v, primary_metric)
            ci = self._wilson_ci(successes=self._metric_successes(v, primary_metric), total=sent)
            stats.append(
                VariantStats(
                    variant_id=str(v["variant_id"]),
                    sent=sent,
                    positive_replied=int(v.get("positive_replied", 0) or 0),
                    replied=int(v.get("replied", 0) or 0),
                    meetings_booked=int(v.get("meetings_booked", 0) or 0),
                    primary_metric_value=metric_value,
                    confidence_interval=ci,
                )
            )

        if not stats:
            return ExperimentResult(variants=stats, reason="Нет вариантов для сравнения")

        if all(s.sent < sample_size_per_variant for s in stats):
            return ExperimentResult(
                variants=stats,
                winner_variant_id=None,
                is_significant=False,
                p_value=None,
                reason=f"Недостаточно данных: нужно по {sample_size_per_variant} на вариант",
            )

        stats.sort(key=lambda s: s.primary_metric_value, reverse=True)
        best = stats[0]

        if len(stats) == 1:
            return ExperimentResult(
                variants=stats,
                winner_variant_id=best.variant_id,
                is_significant=False,
                p_value=None,
                reason="Один вариант — нечего сравнивать",
            )

        n_comparisons = len(stats) - 1
        corrected_alpha = (1 - self._confidence_level) / n_comparisons

        all_significant = True
        min_p_value = 1.0
        for other in stats[1:]:
            p = self._two_proportion_z_test(
                successes1=self._metric_successes_by_stats(best, primary_metric),
                total1=best.sent,
                successes2=self._metric_successes_by_stats(other, primary_metric),
                total2=other.sent,
            )
            min_p_value = min(min_p_value, p)
            if p >= corrected_alpha:
                all_significant = False

        if all_significant and stats[1].sent > 0:
            base = stats[1].primary_metric_value
            relative_lift = (best.primary_metric_value - base) / base if base > 0 else 0.0
            if abs(relative_lift) < minimum_detectable_effect:
                all_significant = False

        return ExperimentResult(
            variants=stats,
            winner_variant_id=best.variant_id if all_significant else None,
            is_significant=all_significant,
            p_value=min_p_value,
            reason=(
                f"Значимо (p={min_p_value:.4f})"
                if all_significant
                else f"Не значимо (p={min_p_value:.4f} >= {corrected_alpha:.4f})"
            ),
        )

    def _metric_value(self, v: dict[str, Any], metric: str) -> float:
        sent = int(v.get("sent", 0) or 0)
        if not sent:
            return 0.0
        if metric == "reply_rate":
            return int(v.get("replied", 0) or 0) / sent
        if metric == "positive_reply_rate":
            return int(v.get("positive_replied", 0) or 0) / sent
        if metric == "meetings_booked":
            return int(v.get("meetings_booked", 0) or 0) / sent
        if metric == "open_rate":
            return int(v.get("opened", 0) or 0) / sent
        return 0.0

    def _metric_successes(self, v: dict[str, Any], metric: str) -> int:
        if metric == "reply_rate":
            return int(v.get("replied", 0) or 0)
        if metric == "positive_reply_rate":
            return int(v.get("positive_replied", 0) or 0)
        if metric == "meetings_booked":
            return int(v.get("meetings_booked", 0) or 0)
        return int(v.get("opened", 0) or 0)

    def _metric_successes_by_stats(self, s: VariantStats, metric: str) -> int:
        if metric == "reply_rate":
            return s.replied
        if metric == "positive_reply_rate":
            return s.positive_replied
        return s.meetings_booked

    def _wilson_ci(self, *, successes: int, total: int) -> tuple[float, float]:
        if total == 0:
            return (0.0, 1.0)
        z = 1.96
        p = successes / total
        n = total
        denom = 1 + z * z / n
        center = (p + z * z / (2 * n)) / denom
        margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
        return (max(0.0, center - margin), min(1.0, center + margin))

    def _two_proportion_z_test(
        self, *, successes1: int, total1: int, successes2: int, total2: int
    ) -> float:
        if total1 == 0 or total2 == 0:
            return 1.0
        p1 = successes1 / total1
        p2 = successes2 / total2
        pooled = (successes1 + successes2) / (total1 + total2)
        se = math.sqrt(pooled * (1 - pooled) * (1 / total1 + 1 / total2))
        if se == 0:
            return 1.0
        z = abs(p1 - p2) / se
        return max(0.0, min(1.0, 2 * (1 - self._normal_cdf(z))))

    @staticmethod
    def _normal_cdf(z: float) -> float:
        return 0.5 * (1 + math.erf(z / math.sqrt(2)))
