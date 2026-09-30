"""Tests for the LLM JSON parser."""

import pytest
from brief_service.llm.json_utils import LLMJSONError, parse_json_strict


def test_parse_plain_json() -> None:
    assert parse_json_strict('{"a": 1}') == {"a": 1}


def test_parse_markdown_fenced() -> None:
    assert parse_json_strict('```json\n{"a": 1}\n```') == {"a": 1}


def test_parse_with_explanation() -> None:
    raw = 'Вот результат:\n{"a": 1}\nНадеюсь, поможет.'
    assert parse_json_strict(raw) == {"a": 1}


def test_parse_invalid_raises() -> None:
    with pytest.raises(LLMJSONError):
        parse_json_strict("not json at all")


def test_parse_non_object_raises() -> None:
    with pytest.raises(LLMJSONError):
        parse_json_strict("[1, 2, 3]")
