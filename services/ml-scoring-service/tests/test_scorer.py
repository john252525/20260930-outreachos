"""Unit tests for the baseline contact scorer."""

from ml_scoring.features.scorer import BaselineScorer


def test_score_bounds() -> None:
    s = BaselineScorer()
    r = s.score({})
    assert 0.0 <= r.score <= 1.0


def test_decision_maker_scores_higher() -> None:
    s = BaselineScorer()
    high = s.score({"role_category": "decision_maker", "seniority": "c_level"})
    low = s.score({"role_category": "gatekeeper", "seniority": "specialist"})
    assert high.score > low.score


def test_signals_increase_score() -> None:
    s = BaselineScorer()
    base = s.score({"role_category": "influencer"})
    with_signals = s.score({"role_category": "influencer", "company_signals_count": 5})
    assert with_signals.score > base.score


def test_model_version() -> None:
    s = BaselineScorer()
    assert s.score({}).model_version == "baseline-heuristic-v1"
