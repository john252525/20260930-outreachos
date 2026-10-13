"""Baseline contact scorer.

The ТЗ recommends deferring real model training until there is enough data
(≥1000 labelled contacts); for now we ship a transparent, deterministic
logistic-style scorer over a small set of weighted features. It is a drop-in
placeholder for a future LightGBM model behind the same interface.
"""

from dataclasses import dataclass
from typing import Any

# Feature weights (logistic-style, hand-tuned priors).
ROLE_WEIGHTS: dict[str, float] = {
    "decision_maker": 0.9,
    "champion": 0.7,
    "influencer": 0.5,
    "gatekeeper": 0.2,
    "unknown": 0.0,
}
SENIORITY_WEIGHTS: dict[str, float] = {
    "c_level": 0.8,
    "vp": 0.6,
    "director": 0.5,
    "manager": 0.3,
    "specialist": 0.1,
    "unknown": 0.0,
}


@dataclass
class ScoreBreakdown:
    score: float
    components: dict[str, float]
    model_version: str = "baseline-heuristic-v1"


class BaselineScorer:
    """Heuristic scorer — sigmoid over weighted features."""

    def score(self, features: dict[str, Any]) -> ScoreBreakdown:
        import math

        z = -1.0  # bias: base ~0.27 probability
        components: dict[str, float] = {}

        role = str(features.get("role_category") or "unknown")
        role_w = ROLE_WEIGHTS.get(role, 0.0)
        z += 1.5 * role_w
        components["role"] = round(1.5 * role_w, 4)

        seniority = str(features.get("seniority") or "unknown")
        sen_w = SENIORITY_WEIGHTS.get(seniority, 0.0)
        z += 1.2 * sen_w
        components["seniority"] = round(1.2 * sen_w, 4)

        signals = int(features.get("company_signals_count") or 0)
        sig_w = min(signals, 5) / 5.0
        z += 0.8 * sig_w
        components["signals"] = round(0.8 * sig_w, 4)

        if features.get("company_industry"):
            z += 0.2
            components["industry_known"] = 0.2

        if features.get("company_employee_count"):
            z += 0.2
            components["size_known"] = 0.2

        score = 1.0 / (1.0 + math.exp(-z))
        return ScoreBreakdown(score=round(score, 4), components=components)
