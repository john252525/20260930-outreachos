"""Deterministic offline provider for dev/stage verification.

Enabled explicitly via ``DEFAULT_PROVIDER=mock`` (or by requesting a
``mock*`` model). It never calls an external API, so it is safe to use to
exercise the full pipeline (DB writes, caching, events, tracing) without
burning real tokens.

For a few known ``task_type`` values it returns JSON shaped like a plausible
real answer, so downstream parsing/validation can be tested end-to-end.
"""

import hashlib
import json

from llm_gateway.providers.base import LLMProvider, LLMRequest, LLMResponse

_EXTRACT_SAMPLE = {
    "identity": {
        "project_name": "Тестовый проект",
        "industry": "Промышленное производство",
        "language": "ru",
        "geo_primary": ["RU"],
    },
    "offering": {"what_we_sell": "Тестовый продукт"},
    "targeting_hints": {},
    "outreach_goals": {"primary_goal": "lead_gen"},
}

_QUESTIONS_SAMPLE = {
    "questions": [
        {
            "question": "Уточните, в каких регионах вы работаете?",
            "why_needed": "для таргетинга",
            "target_field": "identity.geo_primary",
            "priority": "high",
        }
    ]
}


class MockProvider(LLMProvider):
    name = "mock"

    async def complete(self, req: LLMRequest) -> LLMResponse:
        digest = hashlib.sha256(f"{req.system}|{req.user}|{req.model}".encode()).hexdigest()[:8]

        if "brief_extract" in req.task_type:
            text = json.dumps(_EXTRACT_SAMPLE, ensure_ascii=False)
        elif "generate_questions" in req.task_type:
            text = json.dumps(_QUESTIONS_SAMPLE, ensure_ascii=False)
        elif req.json_mode:
            text = json.dumps({"echo": "mock", "digest": digest}, ensure_ascii=False)
        else:
            text = f"[mock:{req.model}] echo: {req.user[:120]} (digest {digest})"

        fake_in = max(1, len(req.user) // 4)
        return LLMResponse(
            text=text,
            model=req.model,
            tokens_in_cache_hit=0,
            tokens_in_cache_miss=fake_in,
            tokens_out=max(1, len(text) // 4),
            latency_ms=1,
            raw={"mock": True},
        )
