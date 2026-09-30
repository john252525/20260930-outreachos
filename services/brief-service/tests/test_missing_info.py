"""Tests for missing-info analysis."""

from brief_service.scoring.missing_info import analyze_missing_info, get_next_priority_field


def test_missing_info_sorted_by_priority() -> None:
    missing = analyze_missing_info({})
    priorities = [m["priority"] for m in missing]
    assert priorities[0] == "high"
    order = {"high": 0, "medium": 1, "low": 2}
    assert [order[p] for p in priorities] == sorted(order[p] for p in priorities)


def test_next_priority_field() -> None:
    nxt = get_next_priority_field({})
    assert nxt is not None
    assert nxt["priority"] == "high"
    assert nxt["field"] in {
        "identity.project_name",
        "identity.industry",
        "identity.geo_primary",
        "offering.what_we_sell",
        "targeting_hints.must_have_criteria",
        "outreach_goals.primary_goal",
    }


def test_no_missing_when_all_filled() -> None:
    data = {
        "identity": {
            "project_name": "X",
            "company_name": "X",
            "company_url": "u",
            "one_liner": "o",
            "industry": "IT",
            "sub_industry": "SaaS",
            "language": "ru",
            "geo_primary": ["RU"],
        },
        "offering": {
            "what_we_sell": "x",
            "categories": ["a"],
            "differentiators": ["b"],
            "proof_points": ["c"],
            "price_range": {"model": "custom"},
            "sales_cycle_days_estimate": 1,
        },
        "targeting_hints": {
            "known_customers_examples": ["a"],
            "must_have_criteria": ["b"],
            "must_not_have_criteria": ["c"],
            "company_size_hint": "smb",
            "role_hints": ["d"],
        },
        "outreach_goals": {
            "primary_goal": "lead_gen",
            "goal_description": "x",
            "tone_of_voice": "neutral",
            "forbidden_topics": ["a"],
            "required_mentions": ["b"],
        },
    }
    assert get_next_priority_field(data) is None
