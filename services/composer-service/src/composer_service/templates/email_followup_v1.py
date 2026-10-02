"""Follow-up email template v1 (short reminder, no repetition)."""

from composer_service.templates.base import RenderedTemplate, Template, TemplateContext

SYSTEM = """Ты — опытный B2B sales copywriter. Пишешь КОРОТКОЕ письмо-напоминание (follow-up).

ПРАВИЛА:
1. Пиши ТОЛЬКО валидным JSON: {{"subject": "...", "body": "..."}}.
2. Body — plain text, без markdown, без HTML, без списков.
3. Длина body: {min_words}-{max_words} слов. Очень коротко.
4. Subject: до {max_subject_len} символов, без CAPS, без "!!!", без эмодзи.
5. НЕ повторяй предыдущее письмо. Добавь новую ценность ИЛИ задай короткий вопрос.
6. Не дави. Тон вежливый и ненавязчивый.
7. Язык: {language}.

ЗАПРЕЩЕНО:
- "Напоминаю о себе".
- "Вы не ответили".
- Эмодзи, CAPS, "!!!".

Обязательно упомяни:
{required_mentions}

Избегай фраз:
{forbidden_phrases}
"""


class EmailFollowupV1(Template):
    template_id = "email_followup"
    template_version = "v1"
    channel = "email"

    def __init__(
        self, *, min_words: int = 15, max_words: int = 120, max_subject_len: int = 80
    ) -> None:
        self._min_words = min_words
        self._max_words = max_words
        self._max_subject_len = max_subject_len

    def render(self, context: TemplateContext) -> RenderedTemplate:
        contact = context.contact
        company = context.company or {}
        brief = context.brief
        sender = context.sender

        contact_name = self.fact_value(contact.get("full_name"))
        company_name = self.fact_value(company.get("name"))
        offering = brief.get("offering", {}) or {}
        what_we_sell = offering.get("what_we_sell", "")
        differentiators = offering.get("differentiators", []) or []

        goals = brief.get("outreach_goals", {}) or {}
        required = goals.get("required_mentions", []) or []
        forbidden = goals.get("forbidden_topics", []) or []

        parent = context.extra.get("parent_message") or {}

        system = SYSTEM.format(
            min_words=self._min_words,
            max_words=self._max_words,
            max_subject_len=self._max_subject_len,
            language=context.language,
            required_mentions="\n".join(f"- {m}" for m in required) or "(нет)",
            forbidden_phrases="\n".join(f"- {f}" for f in forbidden) or "(нет)",
        )

        parts = ["Сгенерируй короткое письмо-напоминание (follow-up).\n"]
        if contact_name:
            parts.append(f"ПОЛУЧАТЕЛЬ: {contact_name}")
        if company_name:
            parts.append(f"КОМПАНИЯ: {company_name}")
        if what_we_sell:
            parts.append(f"ЧТО ПРОДАЁМ: {what_we_sell}")
        if differentiators:
            parts.append(f"ОТЛИЧИЯ: {', '.join(differentiators[:2])}")
        if parent.get("subject"):
            parts.append(f"\nПРЕДЫДУЩЕЕ ПИСЬМО (не повторяй):\nТема: {parent['subject']}")
        if parent.get("body_text"):
            parts.append(f"Текст: {str(parent['body_text'])[:500]}")
        parts.append('\nВерни JSON: {"subject": "...", "body": "..."}')

        return RenderedTemplate(
            system_prompt=system,
            user_prompt="\n".join(parts),
            subject_hint=None,
            required_mentions=required,
            forbidden_phrases=forbidden,
            variables_used={
                "contact_name": contact_name,
                "company_name": company_name,
                "sender_name": sender.get("from_name"),
            },
        )

    def validate_output(self, *, subject: str | None, body: str) -> list[str]:
        warnings: list[str] = []
        if not subject:
            warnings.append("no_subject")
        if not body:
            warnings.append("empty_body")
            return warnings
        word_count = len(body.split())
        if word_count > self._max_words:
            warnings.append(f"too_long:{word_count}")
        body_lower = body.lower()
        for phrase in ["напоминаю о себе", "вы не ответили"]:
            if phrase in body_lower:
                warnings.append(f"forbidden_phrase:{phrase}")
        return warnings
