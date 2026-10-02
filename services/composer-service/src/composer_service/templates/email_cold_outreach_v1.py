"""Cold outreach email template v1."""

from typing import Any

from composer_service.templates.base import RenderedTemplate, Template, TemplateContext

SYSTEM = """Ты — опытный B2B sales copywriter. Пишешь персонализированные холодные письма от имени конкретного человека.

ПРАВИЛА:
1. Пиши ТОЛЬКО валидным JSON: {{"subject": "...", "body": "..."}}.
2. Body — plain text, без markdown, без HTML, без списков, без заголовков.
3. Длина body: {min_words}-{max_words} слов. Короче = лучше.
4. Subject: до {max_subject_len} символов, без CAPS, без "!!!", без эмодзи.
5. Обращение на "вы" (если язык ru). По имени-отчеству, если есть отчество. Иначе — по имени.
6. Персонализация: используй КОНКРЕТНЫЕ факты о компании/человеке из контекста. Одна конкретика в первом абзаце — обязательно.
7. НЕ выдумывай факты. Если факта нет — используй нейтральную формулировку.
8. Структура: 1 предложение (кто ты и почему пишешь именно этому человеку), 2-3 предложения (что предлагаешь, с одной ценностью), 1 предложение мягкий CTA, подпись.
9. Тон: {tone_of_voice}.
10. Язык: {language}.
11. НЕ добавляй подпись сам — она будет добавлена отдельно.

ЗАПРЕЩЕНО:
- "Уважаемый(ая)!" без имени.
- "Наша компания является лидером рынка...".
- "Мы предлагаем широкий спектр услуг...".
- "Буду краток" / "Не буду отнимать время".
- "Заранее спасибо".
- Любые эмодзи.
- Восклицательные знаки в конце предложений (кроме CTA).

Обязательно упомяни:
{required_mentions}

Избегай фраз:
{forbidden_phrases}
"""


class EmailColdOutreachV1(Template):
    template_id = "email_cold_outreach"
    template_version = "v1"
    channel = "email"

    def __init__(
        self, *, min_words: int = 40, max_words: int = 250, max_subject_len: int = 80
    ) -> None:
        self._min_words = min_words
        self._max_words = max_words
        self._max_subject_len = max_subject_len

    def render(self, context: TemplateContext) -> RenderedTemplate:
        contact = context.contact
        company = context.company or {}
        brief = context.brief
        segment = context.segment
        sender = context.sender

        contact_name = self.fact_value(contact.get("full_name"))
        contact_position = self.fact_value(contact.get("position"))

        company_name = self.fact_value(company.get("name"))
        company_industry = self.fact_value(company.get("industry"))
        company_size = self.size_value(company)
        company_location = self.location_value(company)
        company_signals = company.get("signals") or []

        sender_name = sender.get("from_name") or "Менеджер"
        sender_signature = sender.get("signature") or ""

        offering = brief.get("offering", {}) or {}
        what_we_sell = offering.get("what_we_sell", "")
        differentiators = offering.get("differentiators", []) or []
        proof_points = offering.get("proof_points", []) or []

        target_pains = segment.get("pain_hypotheses", []) or []
        role_category = contact.get("role_category", "unknown")

        goals = brief.get("outreach_goals", {}) or {}
        tone = goals.get("tone_of_voice", "neutral")
        forbidden = goals.get("forbidden_topics", []) or []
        required = goals.get("required_mentions", []) or []

        system = SYSTEM.format(
            min_words=self._min_words,
            max_words=self._max_words,
            max_subject_len=self._max_subject_len,
            tone_of_voice=tone,
            language=context.language,
            required_mentions="\n".join(f"- {m}" for m in required) or "(нет)",
            forbidden_phrases="\n".join(f"- {f}" for f in forbidden) or "(нет)",
        )

        user = self._build_user_prompt(
            contact_name=contact_name,
            contact_position=contact_position,
            contact_role_category=role_category,
            company_name=company_name,
            company_industry=company_industry,
            company_size=company_size,
            company_location=company_location,
            company_signals=company_signals,
            sender_name=sender_name,
            sender_signature=sender_signature,
            what_we_sell=what_we_sell,
            differentiators=differentiators,
            proof_points=proof_points,
            target_pains=target_pains,
        )

        return RenderedTemplate(
            system_prompt=system,
            user_prompt=user,
            subject_hint=None,
            required_mentions=required,
            forbidden_phrases=forbidden,
            variables_used={
                "contact_name": contact_name,
                "contact_position": contact_position,
                "company_name": company_name,
                "company_industry": company_industry,
                "sender_name": sender_name,
            },
        )

    def _build_user_prompt(self, **kw: Any) -> str:
        parts = ["Сгенерируй холодное письмо.\n"]
        parts.append("ПОЛУЧАТЕЛЬ:")
        if kw["contact_name"]:
            parts.append(f"  Имя: {kw['contact_name']}")
        if kw["contact_position"]:
            parts.append(f"  Должность: {kw['contact_position']}")
        parts.append(f"  Категория роли: {kw['contact_role_category']}")

        if kw["company_name"]:
            parts.append("\nКОМПАНИЯ:")
            parts.append(f"  Название: {kw['company_name']}")
            if kw["company_industry"]:
                parts.append(f"  Отрасль: {kw['company_industry']}")
            if kw["company_size"]:
                parts.append(f"  Размер: {kw['company_size']}")
            if kw["company_location"]:
                parts.append(f"  Локация: {kw['company_location']}")
            if kw["company_signals"]:
                parts.append("  Сигналы (используй 1 в персонализации):")
                for s in kw["company_signals"][:3]:
                    parts.append(f"    - {s.get('summary', '')} ({s.get('source_url', '')})")

        parts.append("\nОТПРАВИТЕЛЬ:")
        parts.append(f"  Имя: {kw['sender_name']}")
        if kw["sender_signature"]:
            parts.append(f"  Подпись: {kw['sender_signature']}")

        parts.append("\nЧТО ПРОДАЁМ:")
        parts.append(f"  {kw['what_we_sell']}")
        if kw["differentiators"]:
            parts.append(f"  Отличия: {', '.join(kw['differentiators'][:3])}")
        if kw["proof_points"]:
            parts.append(f"  Доказательства: {', '.join(kw['proof_points'][:2])}")

        if kw["target_pains"]:
            parts.append("\nБОЛИ ЦЕЛЕВОГО СЕГМЕНТА (используй 1):")
            for p in kw["target_pains"][:3]:
                parts.append(f"  - {p.get('pain', '')}")

        parts.append('\nВерни JSON: {"subject": "...", "body": "..."}')
        return "\n".join(parts)

    def validate_output(self, *, subject: str | None, body: str) -> list[str]:
        warnings: list[str] = []
        if not subject:
            warnings.append("no_subject")
        elif len(subject) > self._max_subject_len:
            warnings.append(f"subject_too_long:{len(subject)}")
        if not body:
            warnings.append("empty_body")
            return warnings
        word_count = len(body.split())
        if word_count < self._min_words:
            warnings.append(f"too_short:{word_count}")
        if word_count > self._max_words:
            warnings.append(f"too_long:{word_count}")
        body_lower = body.lower()
        for phrase in [
            "лидер рынка",
            "широкий спектр",
            "буду краток",
            "заранее спасибо",
        ]:
            if phrase in body_lower:
                warnings.append(f"forbidden_phrase:{phrase}")
        if "!" in body:
            warnings.append("has_exclamation")
        return warnings
