"""Tests for the completeness scorer."""

from brief_service.scoring.completeness import compute_completeness


def test_empty_brief_scores_zero() -> None:
    assert compute_completeness({}) == 0.0


def test_full_brief_scores_one() -> None:
    data = {
        "identity": {
            "project_name": "X",
            "company_name": "X LLC",
            "company_url": "https://x.com",
            "one_liner": "X делает Y",
            "industry": "IT",
            "sub_industry": "SaaS",
            "language": "ru",
            "geo_primary": ["RU"],
        },
        "offering": {
            "what_we_sell": "SaaS",
            "categories": ["crm"],
            "differentiators": ["fast"],
            "proof_points": ["1000 клиентов"],
            "price_range": {"model": "subscription", "currency": "RUB"},
            "sales_cycle_days_estimate": 30,
        },
        "targeting_hints": {
            "known_customers_examples": ["A", "B"],
            "must_have_criteria": ["РФ"],
            "must_not_have_criteria": ["госсектор"],
            "company_size_hint": "smb",
            "role_hints": ["CTO"],
        },
        "outreach_goals": {
            "primary_goal": "lead_gen",
            "goal_description": "Ищем 20 лидов в месяц",
            "tone_of_voice": "technical",
            "forbidden_topics": ["политика"],
            "required_mentions": ["гарантия"],
        },
    }
    assert compute_completeness(data) == 1.0


def test_partial_brief() -> None:
    data = {
        "identity": {"project_name": "X", "industry": "IT"},
        "offering": {"what_we_sell": "SaaS"},
        "targeting_hints": {},
        "outreach_goals": {"primary_goal": "lead_gen"},
    }
    score = compute_completeness(data)
    assert 0.0 < score < 1.0
    assert 0.25 < score < 0.45


def test_price_range_model_counts() -> None:
    data = {"offering": {"price_range": {"model": "custom"}}}
    assert compute_completeness(data) > 0.0
