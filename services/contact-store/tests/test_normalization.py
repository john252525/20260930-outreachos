"""Tests for normalization helpers."""

import pytest
from contact_store.normalization import (
    normalize_company_name,
    normalize_domain,
    normalize_email,
    normalize_inn,
    normalize_person_name,
    normalize_phone,
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("ООО «Ромашка»", "ромашка"),
        ("Ромашка LLC", "ромашка"),
        ("  ЗАО   Ромашка  ", "ромашка"),
        ('ООО "Ромашка-М"', "ромашка-м"),
        ("Romashka Inc.", "romashka"),
        ("", ""),
        ("ООО", ""),
    ],
)
def test_normalize_company_name(raw: str, expected: str) -> None:
    assert normalize_company_name(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("https://www.example.com/path", "example.com"),
        ("http://example.com", "example.com"),
        ("Example.COM", "example.com"),
        ("example.com:8080", "example.com"),
        ("", None),
        (None, None),
        ("not-a-domain", None),
    ],
)
def test_normalize_domain(raw: str | None, expected: str | None) -> None:
    assert normalize_domain(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("John@Example.COM", "john@example.com"),
        ("  x@y.z  ", "x@y.z"),
        ("invalid", None),
        ("", None),
    ],
)
def test_normalize_email(raw: str, expected: str | None) -> None:
    assert normalize_email(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("+7 900 123-45-67", "+79001234567"),
        ("8 (900) 123-45-67", "+79001234567"),
        ("9001234567", "+79001234567"),
        ("+7-900-123-45-67", "+79001234567"),
        ("", None),
    ],
)
def test_normalize_phone_ru(raw: str, expected: str | None) -> None:
    assert normalize_phone(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Иван Петров", "иван петров"),
        ("И. Петров", "и петров"),
        ("  Иван   Петров  ", "иван петров"),
    ],
)
def test_normalize_person_name(raw: str, expected: str) -> None:
    assert normalize_person_name(raw) == expected


def test_normalize_inn_valid() -> None:
    assert normalize_inn("7707083893") == "7707083893"


def test_normalize_inn_invalid() -> None:
    assert normalize_inn("1234567890") is None
    assert normalize_inn("abc") is None
    assert normalize_inn("") is None


def test_company_name_idempotent() -> None:
    once = normalize_company_name("ООО «Ромашка-М»")
    assert normalize_company_name(once) == once
