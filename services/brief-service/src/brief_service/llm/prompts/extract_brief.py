"""Prompt builder for Brief extraction."""

from typing import Any

from brief_service.llm.prompts.base import PROMPT_VERSION, SYSTEM_COMMON, Prompt

EXTRACT_SCHEMA = """{
  "identity": {
    "project_name": "string | null",
    "company_name": "string | null",
    "company_url": "string | null",
    "one_liner": "string | null",
    "industry": "string | null",
    "sub_industry": "string | null",
    "language": "BCP-47 (например 'ru', 'en')",
    "geo_primary": ["ISO 3166-1 alpha-2"],
    "geo_secondary": ["ISO 3166-1 alpha-2"]
  },
  "offering": {
    "what_we_sell": "string",
    "categories": ["string"],
    "differentiators": ["string"],
    "proof_points": ["string"],
    "price_range": {
      "min": "number | null",
      "max": "number | null",
      "currency": "ISO 4217 | null",
      "model": "fixed | subscription | usage | custom | unknown"
    },
    "sales_cycle_days_estimate": "integer | null"
  },
  "targeting_hints": {
    "known_competitors": ["string"],
    "known_customers_examples": ["string"],
    "must_have_criteria": ["string"],
    "must_not_have_criteria": ["string"],
    "geography_notes": "string | null",
    "company_size_hint": "smb | mid | enterprise | any | null",
    "role_hints": ["string"]
  },
  "outreach_goals": {
    "primary_goal": "lead_gen | partnership | hiring | pr | research | other",
    "goal_description": "string | null",
    "target_meetings_per_month": "integer | null",
    "tone_of_voice": "formal | casual | technical | friendly | neutral",
    "forbidden_topics": ["string"],
    "required_mentions": ["string"]
  }
}"""


def build_extract_prompt(
    *,
    raw_text: str | None,
    urls: list[str],
    transcript: str | None,
    website_contents: list[dict[str, Any]] | None = None,
) -> Prompt:
    """Build the prompt that extracts a Brief from raw input."""
    parts = ["Извлеки структурированную информацию о проекте из следующих данных.\n"]

    if raw_text:
        parts.append(f"<текст>\n{raw_text}\n</текст>\n")
    if urls:
        parts.append("<ссылки>")
        for u in urls:
            parts.append(f"  <url>{u}</url>")
        parts.append("</ссылки>\n")
    if website_contents:
        parts.append("<содержимое_сайтов>")
        for item in website_contents:
            parts.append(f'  <site url="{item.get("url", "")}">')
            parts.append(str(item.get("text", ""))[:8000])
            parts.append("  </site>")
        parts.append("</содержимое_сайтов>\n")
    if transcript:
        parts.append(f"<транскрипт>\n{transcript}\n</транскрипт>\n")

    parts.append(
        "Верни JSON ровно такой структуры (без markdown, без пояснений):\n"
        f"{EXTRACT_SCHEMA}\n\n"
        "Если каких-то данных нет — используй null или пустой массив. Не выдумывай."
    )
    return Prompt(
        system=SYSTEM_COMMON,
        user="\n".join(parts),
        task_type=f"brief_extract_{PROMPT_VERSION}",
    )
