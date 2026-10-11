"""Prompt builder for reply classification."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Prompt:
    system: str
    user: str
    task_type: str


SYSTEM = """Ты — эксперт по классификации B2B-ответов на холодные письма.

ПРАВИЛА:
1. Отвечай ТОЛЬКО валидным JSON.
2. Категория — одна из: positive, negative, not_interested, wrong_person, auto_reply, question, unsubscribe, out_of_office, unknown.
3. Confidence: 0.9+ если явно; 0.7-0.9 если очевидно из контекста; 0.5-0.7 если вывод; <0.5 если не уверен (тогда category=unknown).
4. Sentiment: positive | neutral | negative.
5. Extracted questions — реальные вопросы из письма, если есть.
6. Extracted actions — что человек просит сделать (например, "прислать прайс", "позвонить в среду").
7. Suggested action:
   - reply — если человек ждёт ответа
   - schedule_meeting — если явно предлагает встречу
   - forward_to_human — если нужно участие человека (например, "передайте директору")
   - add_to_nurture — если "не сейчас, но может позже"
   - unsubscribe — если просит отписать
   - close — если окончательно отказал или автоответ
8. Language — язык письма (ru / en / ...).

КАТЕГОРИИ:
- positive: явный интерес, "расскажите подробнее", "давайте обсудим"
- negative: отказ без агрессии, "спасибо, не надо"
- not_interested: явный отказ, "не интересно", "не нужно"
- wrong_person: "я не отвечаю за это", "обратитесь к X"
- auto_reply: технический автоответ ("письмо получено")
- question: конкретный вопрос от человека
- unsubscribe: просьба удалить из рассылки
- out_of_office: "в отпуске до X", "вернусь Y"
- unknown: не удаётся классифицировать

Будь консервативен: если сомневаешься — category=unknown, confidence < 0.5.
"""


USER_TEMPLATE = """Классифицируй ответ на холодное письмо.

Исходное письмо (что мы отправили):
<original>
От: {original_from}
Тема: {original_subject}
{original_body}
</original>

Ответ:
<reply>
От: {from_email}
Имя: {from_name}
Тема: {subject}
{body}
</reply>

Верни JSON:
{{
  "category": "...",
  "confidence": 0.0,
  "sentiment": "...",
  "intent": "string | null",
  "extracted_questions": ["string"],
  "extracted_actions": ["string"],
  "suggested_action": "...",
  "suggested_action_reason": "string",
  "language": "ru | en | ...",
  "reasoning": "string (1-2 предложения, почему такая классификация)"
}}
"""


def build_classify_prompt(
    *,
    original_from: str,
    original_subject: str,
    original_body: str,
    from_email: str,
    from_name: str | None,
    subject: str | None,
    body: str,
    max_body_length: int = 10_000,
) -> Prompt:
    return Prompt(
        system=SYSTEM,
        user=USER_TEMPLATE.format(
            original_from=original_from,
            original_subject=original_subject or "(нет темы)",
            original_body=original_body[:2000],
            from_email=from_email,
            from_name=from_name or "(неизвестно)",
            subject=subject or "(нет темы)",
            body=body[:max_body_length],
        ),
        task_type="reply_classify_v1",
    )
