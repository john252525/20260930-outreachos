"""Tests for merge logic."""

from typing import Any

from contact_store.merger import (
    _merge_fact,
    _merge_list_of_strings,
    merge_company_payload,
    merge_contact_payload,
)


def test_merge_fact_incoming_wins_with_higher_confidence() -> None:
    existing = {"value": "old", "confidence": 0.5, "evidence": []}
    incoming = {"value": "new", "confidence": 0.9, "evidence": []}
    r = _merge_fact(existing, incoming)
    assert r is not None and r["value"] == "new"


def test_merge_fact_existing_wins_on_tie() -> None:
    existing = {"value": "old", "confidence": 0.5, "evidence": []}
    incoming = {"value": "new", "confidence": 0.5, "evidence": []}
    r = _merge_fact(existing, incoming)
    assert r is not None and r["value"] == "old"


def test_merge_fact_combines_evidence() -> None:
    existing = {"value": "x", "confidence": 0.5, "evidence": [{"source_url": "a"}]}
    incoming = {"value": "x", "confidence": 0.5, "evidence": [{"source_url": "b"}]}
    result = _merge_fact(existing, incoming)
    assert result is not None
    assert {e["source_url"] for e in result["evidence"]} == {"a", "b"}


def test_merge_list_of_strings() -> None:
    assert list(_merge_list_of_strings(["a", "b"], ["b", "c"])) == ["a", "b", "c"]


def test_merge_company_payload_basic() -> None:
    existing = {
        "name": {"value": "X", "confidence": 0.8, "evidence": []},
        "tags": ["a", "b"],
        "signals": [],
    }
    incoming = {
        "name": {"value": "X Corp", "confidence": 0.9, "evidence": []},
        "tags": ["b", "c"],
        "signals": [{"type": "news", "source_url": "u1", "summary": "..."}],
    }
    result = merge_company_payload(existing, incoming)
    assert result["name"]["value"] == "X Corp"
    assert result["tags"] == ["a", "b", "c"]
    assert len(result["signals"]) == 1


def test_merge_company_payload_no_mutation() -> None:
    existing: dict[str, Any] = {
        "name": {"value": "X", "confidence": 0.5, "evidence": []},
        "tags": [],
    }
    incoming: dict[str, Any] = {
        "name": {"value": "Y", "confidence": 0.9, "evidence": []},
        "tags": ["a"],
    }
    _ = merge_company_payload(existing, incoming)
    assert existing["name"]["value"] == "X"
    assert existing["tags"] == []


def test_merge_contact_payload_emails() -> None:
    existing = {
        "emails": [{"value": "a@x.com", "confidence": 0.9, "is_primary": True, "type": "work"}],
        "full_name": {"value": "Иван", "confidence": 0.7, "evidence": []},
    }
    incoming = {
        "emails": [
            {"value": "a@x.com", "confidence": 0.5, "is_primary": False, "type": "unknown"},
            {"value": "b@x.com", "confidence": 0.8, "is_primary": False, "type": "work"},
        ],
        "full_name": {"value": "Иван Петров", "confidence": 0.9, "evidence": []},
    }
    result = merge_contact_payload(existing, incoming)
    primary = next(e for e in result["emails"] if e["is_primary"])
    assert primary["value"] == "a@x.com"
    assert len(result["emails"]) == 2
