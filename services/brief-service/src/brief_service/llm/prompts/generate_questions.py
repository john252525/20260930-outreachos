"""Prompt builder for clarifying-question generation."""

from typing import Any

from brief_service.llm.prompts.base import PROMPT_VERSION, SYSTEM_COMMON, Prompt

QUESTIONS_SCHEMA = """{
  "questions": [
    {
      "question": "string (на русском, конкретный, открытый, не да/нет)",
      "why_needed": "string (зачем этот вопрос)",
      "target_field": "string (поле Brief, которое закрывает вопрос, например 'offering.price_range.min')",
      "priority": "high | medium | low"
    }
  ]
}"""


def build_generate_questions_prompt(
    *,
    brief_json: str,
    missing_fields: list[dict[str, Any]],
    already_asked: list[str],
    max_questions: int = 1,
) -> Prompt:
    asked_block = "\n".join(f"- {q}" for q in already_asked) or "(нет)"
    missing_block = (
        "\n".join(
            f"- {m['field']}: {m['why_needed']} (приоритет: {m['priority']})"
            for m in missing_fields
        )
        or "(нет)"
    )

    user = f"""Есть частично заполненный Brief проекта:
<brief>
{brief_json}
</brief>

Не хватает следующих данных (в порядке приоритета):
{missing_block}

Уже были заданы эти вопросы (не повторяй их):
{asked_block}

Сгенерируй РОВНО {max_questions} уточняющий вопрос, который:
1. Закрывает самое приоритетное недостающее поле.
2. Сформулирован на русском, конкретно, открыто (не да/нет).
3. Учитывает контекст уже имеющихся данных (не спрашивай то, что можно вывести).
4. Не повторяет ранее заданные вопросы.

Верни JSON ровно такой структуры (без markdown, без пояснений):
{QUESTIONS_SCHEMA}"""
    return Prompt(
        system=SYSTEM_COMMON,
        user=user,
        task_type=f"brief_generate_questions_{PROMPT_VERSION}",
    )
