"""Prompt for diagnosing poor outreach metrics."""

from dataclasses import dataclass

from auto_revision.analysis.metrics_analyzer import MetricsSnapshot


@dataclass(frozen=True)
class Prompt:
    system: str
    user: str
    task_type: str


SYSTEM = """Ты — эксперт по B2B cold outreach. Отвечай ТОЛЬКО валидным JSON.

Твоя задача: проанализировать метрики outreach и предложить 1-2 КОНКРЕТНЫХ изменения в шаблоне письма.
Правила:
- Одно изменение — одна переменная (subject / body / cta / tone).
- Не предлагай generic-советы. Только то, что следует из данных.
- Если из данных нельзя сделать вывод — верни пустой список изменений и низкую confidence.
- confidence (llm_confidence): 0.9+ если проблема очевидна; 0.6-0.9 если разумное предположение; <0.6 если сомневаешься.

Верни JSON:
{
  "diagnosis": "1-2 предложения: что именно не работает и почему",
  "proposed_changes": [
    {"variable_type": "subject|body|cta|tone", "description": "...", "example_before": "...", "example_after": "..."}
  ],
  "llm_confidence": 0.0
}
"""


def build_diagnose_prompt(
    *,
    metrics: MetricsSnapshot,
    template_id: str,
    sample_emails: list[str],
) -> Prompt:
    m = metrics.as_dict()
    cats = (
        ", ".join(f"{c.get('category')}: {c.get('count')}" for c in m.get("reply_categories", []))
        or "(нет данных)"
    )
    templ = (
        ", ".join(
            f"{t.get('template_id')}: reply_rate={t.get('reply_rate')}"
            for t in m.get("by_template", [])
        )
        or "(нет данных)"
    )
    emails = "\n---\n".join(sample_emails[:10]) or "(нет примеров)"

    user = f"""Метрики (окно {30} дней), шаблон `{template_id}`:
- Отправлено: {m["sent"]}
- Reply rate: {m["reply_rate"]:.2%}
- Positive reply rate: {m["positive_reply_rate"]:.2%}
- Bounce rate: {m["bounce_rate"]:.2%}
- Категории ответов: {cats}
- По шаблонам: {templ}

Примеры последних отправленных писем:
{emails}

Проанализируй и верни JSON по формату.
"""
    return Prompt(system=SYSTEM, user=user, task_type="auto_revision_diagnose_v1")
