"""Prompt for generating a revised template."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Prompt:
    system: str
    user: str
    task_type: str


SYSTEM = """Ты — эксперт по B2B cold outreach. Отвечай ТОЛЬКО валидным JSON.

Тебе дан диагноз проблем и список предлагаемых изменений. Сгенерируй НОВУЮ версию промпта письма.

Правила:
- system_prompt: инструкции модели-копирайтеру (ок 10-15 правил, plain text).
- user_prompt_template: шаблон входных данных с плейсхолдерами {{ contact_name }}, {{ company_name }}, {{ what_we_sell }}, {{ sender_name }}.
- Внеси РОВНО те изменения, что в диагнозе. Остальное сохрани.
- Не выдумывай новые факты о компании.

Верни JSON:
{
  "system_prompt": "...",
  "user_prompt_template": "...",
  "variables_used": ["contact_name", "company_name", "what_we_sell", "sender_name"],
  "summary": "1 предложение: что изменено"
}
"""


def build_revise_prompt(
    *,
    template_id: str,
    original_system: str,
    original_user_template: str,
    diagnosis: str,
    proposed_changes: list[dict[str, str]],
) -> Prompt:
    changes = (
        "\n".join(
            f"- [{c.get('variable_type')}] {c.get('description')} "
            f"(было: {c.get('example_before')} → станет: {c.get('example_after')})"
            for c in proposed_changes
        )
        or "(нет явных изменений)"
    )
    user = f"""Шаблон: `{template_id}`

Диагноз:
{diagnosis}

Предлагаемые изменения:
{changes}

Текущий system_prompt:
<system>
{original_system}
</system>

Текущий user_prompt_template:
<user>
{original_user_template}
</user>

Сгенерируй новую версию (JSON по формату).
"""
    return Prompt(system=SYSTEM, user=user, task_type="auto_revision_revise_v1")
