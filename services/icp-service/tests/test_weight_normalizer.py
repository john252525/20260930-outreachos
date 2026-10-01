"""Tests for the weight normalizer."""

import pytest
from icp_service.weight_normalizer import REQUIRED_KEYS, is_valid, normalize_weights


def test_normalize_full_valid() -> None:
    w = {
        "industry_match": 0.25,
        "size_match": 0.15,
        "geo_match": 0.10,
        "pain_match": 0.20,
        "trigger_match": 0.20,
        "role_match": 0.10,
    }
    result, warnings = normalize_weights(w)
    assert warnings == []
    assert is_valid(result)


def test_normalize_all_zero() -> None:
    result, warnings = normalize_weights(dict.fromkeys(REQUIRED_KEYS, 0.0))
    assert "all weights zero" in " ".join(warnings)
    assert is_valid(result)
    assert all(v == pytest.approx(1 / 6, abs=1e-6) for v in result.values())


def test_normalize_empty() -> None:
    result, warnings = normalize_weights(None)
    assert is_valid(result)
    assert "all weights zero" in " ".join(warnings)


def test_normalize_negative() -> None:
    w = {
        "industry_match": -0.5,
        "size_match": 0.5,
        "geo_match": 0.5,
        "pain_match": 0.5,
        "trigger_match": 0.5,
        "role_match": 0.5,
    }
    result, warnings = normalize_weights(w)
    assert any("negative" in x for x in warnings)
    assert is_valid(result)


def test_normalize_extra_keys() -> None:
    w = {
        "industry_match": 0.5,
        "size_match": 0.5,
        "geo_match": 0.5,
        "pain_match": 0.5,
        "trigger_match": 0.5,
        "role_match": 0.5,
        "junk": 1.0,
    }
    result, warnings = normalize_weights(w)
    assert any("extra keys" in x for x in warnings)
    assert "junk" not in result
    assert is_valid(result)


def test_normalize_missing_keys() -> None:
    w = {"industry_match": 0.5, "size_match": 0.5}
    result, warnings = normalize_weights(w)
    assert any("missing keys" in x for x in warnings)
    assert is_valid(result)


def test_normalize_rounding() -> None:
    w = dict.fromkeys(REQUIRED_KEYS, 1.0)
    result, _ = normalize_weights(w)
    assert abs(sum(result.values()) - 1.0) < 1e-6
