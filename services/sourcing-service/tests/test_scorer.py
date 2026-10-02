"""Tests for the deterministic scorer."""

from sourcing_service.scoring.scorer import Scorer


def test_scorer_industry_exact() -> None:
    scorer = Scorer()
    seg = {
        "scoring_weights": {
            "industry_match": 1.0,
            "size_match": 0.0,
            "geo_match": 0.0,
            "pain_match": 0.0,
            "trigger_match": 0.0,
            "role_match": 0.0,
        },
        "firmographic": {"industries": ["производство"]},
    }
    comp = {"industry": {"value": "Производство", "confidence": 0.9, "evidence": []}}
    score, breakdown, _ = scorer.score(normalized_company=comp, contacts=[], segment=seg)
    assert score == 1.0
    assert breakdown["industry_match"] == 1.0


def test_scorer_industry_partial() -> None:
    scorer = Scorer()
    seg = {
        "scoring_weights": {
            "industry_match": 1.0,
            "size_match": 0.0,
            "geo_match": 0.0,
            "pain_match": 0.0,
            "trigger_match": 0.0,
            "role_match": 0.0,
        },
        "firmographic": {"industries": ["производство"]},
    }
    comp = {"industry": {"value": "Промышленное производство", "confidence": 0.9, "evidence": []}}
    score, _, _ = scorer.score(normalized_company=comp, contacts=[], segment=seg)
    assert score == 0.7


def test_scorer_geo_mismatch() -> None:
    scorer = Scorer()
    seg = {
        "scoring_weights": {
            "geo_match": 1.0,
            "industry_match": 0.0,
            "size_match": 0.0,
            "pain_match": 0.0,
            "trigger_match": 0.0,
            "role_match": 0.0,
        },
        "firmographic": {"geos": ["RU"]},
    }
    comp = {
        "locations": [
            {"country": {"value": "US", "confidence": 1.0, "evidence": []}, "is_hq": True}
        ]
    }
    score, _, _ = scorer.score(normalized_company=comp, contacts=[], segment=seg)
    assert score == 0.0


def test_scorer_neutral_when_no_segment_data() -> None:
    scorer = Scorer()
    seg = {
        "scoring_weights": {
            "industry_match": 1.0,
            "size_match": 0.0,
            "geo_match": 0.0,
            "pain_match": 0.0,
            "trigger_match": 0.0,
            "role_match": 0.0,
        },
        "firmographic": {},
    }
    comp = {"industry": {"value": "X", "confidence": 1.0, "evidence": []}}
    score, _, _ = scorer.score(normalized_company=comp, contacts=[], segment=seg)
    assert score == 0.5
