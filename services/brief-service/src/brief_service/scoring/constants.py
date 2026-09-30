"""Weights and thresholds for Brief scoring. Change only deliberately."""

# Top-level group weights (sum = 1.0)
GROUP_WEIGHTS: dict[str, float] = {
    "identity": 0.25,
    "offering": 0.30,
    "targeting_hints": 0.20,
    "outreach_goals": 0.25,
}

# Field weights inside each group (sum inside a group = 1.0)
FIELD_WEIGHTS: dict[str, dict[str, float]] = {
    "identity": {
        "project_name": 0.15,
        "company_name": 0.10,
        "company_url": 0.10,
        "one_liner": 0.15,
        "industry": 0.20,
        "sub_industry": 0.05,
        "language": 0.05,
        "geo_primary": 0.20,
    },
    "offering": {
        "what_we_sell": 0.30,
        "categories": 0.15,
        "differentiators": 0.20,
        "proof_points": 0.10,
        "price_range": 0.15,
        "sales_cycle_days_estimate": 0.10,
    },
    "targeting_hints": {
        "known_customers_examples": 0.20,
        "must_have_criteria": 0.30,
        "must_not_have_criteria": 0.15,
        "company_size_hint": 0.15,
        "role_hints": 0.20,
    },
    "outreach_goals": {
        "primary_goal": 0.40,
        "goal_description": 0.20,
        "tone_of_voice": 0.20,
        "forbidden_topics": 0.10,
        "required_mentions": 0.10,
    },
}

# Field priority for missing_info
FIELD_PRIORITY: dict[str, str] = {
    "identity.project_name": "high",
    "identity.industry": "high",
    "identity.geo_primary": "high",
    "identity.company_url": "medium",
    "identity.one_liner": "medium",
    "identity.company_name": "medium",
    "identity.language": "low",
    "identity.sub_industry": "low",
    "offering.what_we_sell": "high",
    "offering.differentiators": "high",
    "offering.categories": "medium",
    "offering.proof_points": "medium",
    "offering.price_range": "medium",
    "offering.sales_cycle_days_estimate": "low",
    "targeting_hints.must_have_criteria": "high",
    "targeting_hints.known_customers_examples": "medium",
    "targeting_hints.role_hints": "medium",
    "targeting_hints.company_size_hint": "medium",
    "targeting_hints.must_not_have_criteria": "low",
    "outreach_goals.primary_goal": "high",
    "outreach_goals.tone_of_voice": "medium",
    "outreach_goals.goal_description": "medium",
    "outreach_goals.forbidden_topics": "low",
    "outreach_goals.required_mentions": "low",
}

# Human-readable explanations of why a field matters
FIELD_WHY_NEEDED: dict[str, str] = {
    "identity.project_name": "Без названия проекта сложно идентифицировать бриф",
    "identity.industry": "Отрасль определяет ЦА и источники поиска",
    "identity.geo_primary": "География критична для таргетинга",
    "identity.company_url": "Сайт компании — ключевой источник для OSINT",
    "identity.one_liner": "Краткое описание помогает в персонализации писем",
    "identity.company_name": "Нужно для поиска компании в реестрах",
    "identity.language": "Язык определяет язык коммуникации",
    "identity.sub_industry": "Уточняет нишу для более точного таргетинга",
    "offering.what_we_sell": "Без этого невозможно построить оффер",
    "offering.differentiators": "Определяет, чем цеплять в письме",
    "offering.categories": "Помогает сегментировать ЦА",
    "offering.proof_points": "Кейсы и цифры повышают доверие",
    "offering.price_range": "Влияет на сегментацию по размеру клиента",
    "offering.sales_cycle_days_estimate": "Помогает планировать follow-up",
    "targeting_hints.must_have_criteria": "Определяет, кого искать",
    "targeting_hints.known_customers_examples": "Помогает найти похожих клиентов",
    "targeting_hints.role_hints": "Определяет, к кому обращаться",
    "targeting_hints.company_size_hint": "Влияет на сегментацию",
    "targeting_hints.must_not_have_criteria": "Помогает отсеять неподходящих",
    "outreach_goals.primary_goal": "Цель outreach определяет тон и CTA",
    "outreach_goals.tone_of_voice": "Влияет на стиль письма",
    "outreach_goals.goal_description": "Уточняет ожидаемый результат",
    "outreach_goals.forbidden_topics": "Помогает избежать нежелательных тем",
    "outreach_goals.required_mentions": "Что обязательно упомянуть в письмах",
}
