"""Prompt builder for candidate normalization."""

from sourcing_service.llm.prompts.base import PROMPT_VERSION, SYSTEM_NORMALIZER, Prompt


def build_normalize_prompt(
    *,
    candidate_title: str | None,
    candidate_snippet: str | None,
    candidate_url: str | None,
    candidate_domain: str | None,
    segment_context: str,
    candidate_extra: str | None = None,
) -> Prompt:
    extra_block = f"- Дополнительно: {candidate_extra}" if candidate_extra else ""
    user = f"""Ты — эксперт по нормализации данных о компаниях из результатов поиска.

Контекст: мы ищем компании для сегмента ICP:
<segment>
{segment_context}
</segment>

Найден кандидат:
- URL: {candidate_url or "(нет)"}
- Домен: {candidate_domain or "(нет)"}
- Заголовок: {candidate_title or "(нет)"}
- Сниппет: {candidate_snippet or "(нет)"}
{extra_block}

Задача: определить, является ли это релевантной компанией для нашего ICP. Если да — нормализовать.

Правила:
1. is_company: true, если это сайт компании (не статья, не каталог, не маркетплейс).
2. is_relevant: true, если компания подходит под сегмент. Иначе false + relevance_reason.
3. company.name — название компании. Если не удаётся извлечь — null.
4. company.domain — домен без www и протокола.
5. company.website — полный URL.
6. company.industry, company.sub_industry — если определяются. Иначе null.
7. company.locations — массив объектов со страной/городом, если известны.
8. company.registry_ids — если есть ИНН/ОГРН (например, из реестра) — заполни ru_inn/ru_ogrn.
9. contacts — если в данных есть люди (ФИО, должности, email, телефон). Иначе пустой массив.
10. Для каждого поля — confidence 0.0-1.0 и evidence с source_url.
11. Не выдумывай данные. Если не знаешь — null.

Верни JSON ровно такой структуры (без markdown, без пояснений):
{{
  "is_company": true,
  "is_relevant": true,
  "relevance_reason": "string",
  "company": {{
    "name": {{"value": "string | null", "confidence": 0.0}},
    "domain": {{"value": "string | null", "confidence": 0.0}},
    "website": {{"value": "string | null", "confidence": 0.0}},
    "industry": {{"value": "string | null", "confidence": 0.0}},
    "sub_industry": {{"value": "string | null", "confidence": 0.0}},
    "registry_ids": {{"ru_inn": "string | null", "ru_ogrn": "string | null"}},
    "locations": []
  }},
  "contacts": [
    {{
      "full_name": "string",
      "position": "string | null",
      "role_category": "decision_maker | influencer | gatekeeper | champion | unknown",
      "seniority": "c_level | vp | director | manager | specialist | unknown",
      "emails": [{{"value": "string", "type": "work", "is_primary": true, "confidence": 0.0}}],
      "phones": [{{"value": "string", "type": "work", "is_primary": true, "confidence": 0.0}}],
      "confidence": 0.0
    }}
  ]
}}"""
    return Prompt(
        system=SYSTEM_NORMALIZER,
        user=user,
        task_type=f"sourcing_normalize_candidate_{PROMPT_VERSION}",
    )
