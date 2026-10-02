"""Tests for the deterministic fact checker."""

from composer_service.personalization.fact_checker import FactChecker


def test_name_is_verified():
    fc = FactChecker(strict=True)
    result = fc.check(
        body="Здравствуйте, Иван! ...",
        subject="Привет",
        contact={"full_name": {"value": "Иван Петров"}},
        company=None,
    )
    assert any(c.source_field == "contact.full_name" for c in result.claims)
    assert not any(c.is_hypothesis for c in result.claims)


def test_company_name_is_verified():
    fc = FactChecker()
    result = fc.check(
        body="Вижу, что Ромашка активно растёт.",
        subject=None,
        contact={},
        company={"name": {"value": "ООО Ромашка"}},
    )
    assert any(c.source_field == "company.name" for c in result.claims)


def test_unverified_number_is_hypothesis():
    fc = FactChecker(strict=True)
    result = fc.check(
        body="Мы работаем с 2005 года и обслужили 500 клиентов.",
        subject=None,
        contact={},
        company=None,
    )
    hypotheses = [c for c in result.claims if c.is_hypothesis]
    assert hypotheses
    assert any("unverified_number" in w for w in result.warnings)
    assert any("hypotheses_present" in w for w in result.warnings)


def test_no_strict_no_hypotheses_warning():
    fc = FactChecker(strict=False)
    result = fc.check(body="500 клиентов", subject=None, contact={}, company=None)
    assert not any("hypotheses_present" in w for w in result.warnings)
