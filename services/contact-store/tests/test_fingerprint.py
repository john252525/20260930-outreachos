"""Tests for fingerprint computation."""

import pytest
from contact_store.fingerprint import company_fingerprint, contact_fingerprint


def test_company_fingerprint_priorities() -> None:
    fp_inn = company_fingerprint(name_normalized="x", domain_normalized="x.com", inn="7707083893")
    fp_domain = company_fingerprint(name_normalized="x", domain_normalized="x.com")
    fp_name = company_fingerprint(name_normalized="x", domain_normalized=None)
    assert fp_inn != fp_domain != fp_name


def test_company_fingerprint_deterministic() -> None:
    fp1 = company_fingerprint(name_normalized="x", domain_normalized="x.com")
    fp2 = company_fingerprint(name_normalized="x", domain_normalized="x.com")
    assert fp1 == fp2


def test_company_fingerprint_requires_something() -> None:
    with pytest.raises(ValueError):
        company_fingerprint(name_normalized="", domain_normalized=None)


def test_contact_fingerprint_priorities() -> None:
    fp_email = contact_fingerprint(
        email="a@b.com", phone=None, full_name_normalized="x", company_domain="x.com"
    )
    fp_phone = contact_fingerprint(
        email=None, phone="+79001234567", full_name_normalized="x", company_domain="x.com"
    )
    fp_name = contact_fingerprint(
        email=None, phone=None, full_name_normalized="x", company_domain="x.com"
    )
    assert fp_email != fp_phone != fp_name


def test_contact_fingerprint_name_without_domain_raises() -> None:
    with pytest.raises(ValueError):
        contact_fingerprint(email=None, phone=None, full_name_normalized="x", company_domain=None)
