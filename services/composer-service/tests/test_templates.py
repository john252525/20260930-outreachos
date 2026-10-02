"""Tests for the template registry and email templates."""

import pytest
from composer_service.templates.base import TemplateContext
from composer_service.templates.email_cold_outreach_v1 import EmailColdOutreachV1
from composer_service.templates.email_followup_v1 import EmailFollowupV1
from composer_service.templates.registry import TemplateRegistry


def _context(**overrides):
    base = {
        "contact": {
            "full_name": {"value": "Иван Петров"},
            "position": {"value": "Директор по закупкам"},
            "role_category": "decision_maker",
            "emails": [{"value": "ivan@example.com", "is_primary": True}],
        },
        "company": {
            "name": {"value": "ООО Ромашка"},
            "industry": {"value": "Логистика"},
            "locations": [{"city": {"value": "Москва"}, "is_hq": True}],
        },
        "sender": {"from_name": "Сергей", "signature": "Сергей, Sales"},
        "brief": {
            "offering": {"what_we_sell": "Гидроборты", "differentiators": ["Своё производство"]},
            "outreach_goals": {"tone_of_voice": "technical"},
        },
        "icp": {},
        "segment": {"pain_hypotheses": [{"pain": "Долгие поставки"}]},
        "channel": "email",
    }
    base.update(overrides)
    return TemplateContext(**base)


def test_registry_register_and_get():
    reg = TemplateRegistry()
    t = EmailColdOutreachV1()
    reg.register(t)
    assert reg.get("email_cold_outreach") is t
    assert reg.get("email_cold_outreach", "v1") is t


def test_registry_duplicate_raises():
    reg = TemplateRegistry()
    reg.register(EmailColdOutreachV1())
    with pytest.raises(ValueError):
        reg.register(EmailColdOutreachV1())


def test_registry_default_for_channel():
    reg = TemplateRegistry()
    reg.register(EmailColdOutreachV1())
    assert reg.default_for_channel("email").template_id == "email_cold_outreach"


def test_cold_outreach_render():
    t = EmailColdOutreachV1()
    rendered = t.render(_context())
    assert "Иван Петров" in rendered.user_prompt or "Иван" in rendered.user_prompt
    assert "ООО Ромашка" in rendered.user_prompt
    assert rendered.variables_used["company_name"] == "ООО Ромашка"
    assert rendered.variables_used["contact_name"] == "Иван Петров"


def test_cold_outreach_validate_output():
    t = EmailColdOutreachV1(min_words=3, max_words=100)
    warnings = t.validate_output(subject="Привет", body="короткое письмо тут")
    assert warnings == []
    warnings2 = t.validate_output(
        subject="Очень длинная тема " * 10,
        body="Мы предлагаем широкий спектр услуг!!!",
    )
    assert any("subject_too_long" in w for w in warnings2)
    assert any("forbidden_phrase" in w for w in warnings2)
    assert "has_exclamation" in warnings2


def test_followup_render_with_parent():
    t = EmailFollowupV1()
    rendered = t.render(
        _context(extra={"parent_message": {"subject": "Про гидроборты", "body_text": "..."}})
    )
    assert "Про гидроборты" in rendered.user_prompt
    assert t.template_id == "email_followup"
