"""Prompt builder for 'Brief -> ICP' generation."""

from icp_service.llm.prompts.base import PROMPT_VERSION, SYSTEM_COMMON, Prompt

ICP_SCHEMA = """{
  "anti_icp": {
    "description": "string (кого НЕ трогаем и почему)",
    "exclude_industries": ["string"],
    "exclude_company_sizes": ["smb" | "mid" | "enterprise"],
    "exclude_geos": ["ISO 3166-1 alpha-2"],
    "exclude_keywords": ["string"]
  },
  "segments": [
    {
      "name": "string (краткое, до 60 символов)",
      "description": "string (1-2 предложения)",
      "priority": "high" | "medium" | "low",
      "estimated_size": "integer | null",
      "firmographic": {
        "industries": ["string"],
        "sub_industries": ["string"],
        "company_sizes": ["smb" | "mid" | "enterprise"],
        "employee_count_min": "integer | null",
        "employee_count_max": "integer | null",
        "revenue_range": {"min": "number | null", "max": "number | null", "currency": "ISO 4217 | null"},
        "geos": ["ISO 3166-1 alpha-2"],
        "company_types": ["manufacturer" | "distributor" | "retailer" | "service" | "agency" | "saas" | "other"]
      },
      "technographic": {
        "uses_technologies": ["string"],
        "does_not_use_technologies": ["string"]
      },
      "pain_hypotheses": [
        {"pain": "string", "why_relevant": "string", "how_we_solve": "string", "confidence": "0.0-1.0"}
      ],
      "trigger_events": [
        {"trigger": "string", "detection_hint": "string", "weight": "0.0-1.0"}
      ],
      "roles_to_contact": [
        {"role_title": "string", "role_category": "decision_maker|influencer|gatekeeper|champion|unknown", "priority": "high|medium|low", "why": "string"}
      ],
      "scoring_weights": {
        "industry_match": "0.0-1.0",
        "size_match": "0.0-1.0",
        "geo_match": "0.0-1.0",
        "pain_match": "0.0-1.0",
        "trigger_match": "0.0-1.0",
        "role_match": "0.0-1.0"
      },
      "estimated_reply_rate": "0.0-1.0 | null",
      "notes": "string | null"
    }
  ],
  "llm_confidence": "0.0-1.0",
  "reasoning": "string (1-3 предложения)"
}"""


def build_generate_icp_prompt(
    *,
    brief_json: str,
    min_segments: int = 1,
    max_segments: int = 5,
) -> Prompt:
    user = f"""Ты — эксперт по B2B-маркетингу и сегментации рынка.

Есть структурированный Brief проекта:

<brief>
{brief_json}
</brief>

Твоя задача — построить ICP (Ideal Customer Profile) с сегментами для целевого outreach.

Требования:
1. Сгенерируй от {min_segments} до {max_segments} сегментов. Сегменты должны быть различимы (разные отрасли, размеры, боли или гео).
2. Для каждого сегмента заполни: firmographic, technographic, pain_hypotheses, trigger_events, roles_to_contact, scoring_weights (сумма ОБЯЗАТЕЛЬНО = 1.0).
3. anti_icp — кого НЕ трогаем: конкуренты, нецелевые отрасли/гео, слишком маленькие/большие компании.
4. llm_confidence — насколько ты уверен в качестве ICP (0.0-1.0). Если в Brief мало данных — ставь низкий.
5. reasoning — 1-3 предложения: почему именно такие сегменты.

ВАЖНО:
- Опирайся ТОЛЬКО на данные из Brief. Не выдумывай отрасли, которых там нет.
- Если Brief неполный (completeness_score < 0.7) — снижай llm_confidence.
- scoring_weights — сумма ровно 1.0. Если не уверен — распредели равномерно.
- estimated_reply_rate — реалистичная оценка (обычно 0.02-0.15 для холодного outreach).

Верни JSON ровно такой структуры (без markdown, без пояснений):
{ICP_SCHEMA}"""
    return Prompt(
        system=SYSTEM_COMMON,
        user=user,
        task_type=f"icp_generate_{PROMPT_VERSION}",
    )
