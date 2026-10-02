"""Tests for the LLM normalizer (mocked llm-gateway)."""

import json
import uuid

import httpx
import pytest
import respx
from sourcing_service.config import Settings
from sourcing_service.connectors.base import RawCandidate
from sourcing_service.llm.client import LLMClient
from sourcing_service.normalization.normalizer import Normalizer


@pytest.mark.asyncio
@respx.mock
async def test_normalize_company() -> None:
    respx.post("http://llm.local/v1/complete").mock(
        return_value=httpx.Response(
            200,
            json={
                "text": json.dumps(
                    {
                        "is_company": True,
                        "is_relevant": True,
                        "relevance_reason": "Производство",
                        "company": {
                            "name": {"value": "Ромашка", "confidence": 0.9, "evidence": []},
                            "domain": {"value": "romashka.ru", "confidence": 0.9, "evidence": []},
                        },
                        "contacts": [],
                    }
                ),
                "model": "deepseek-flash",
                "tokens_in": 500,
                "tokens_out": 200,
                "cost_usd": 0.0002,
                "latency_ms": 1500,
            },
        )
    )
    import os

    os.environ["DATABASE_URL"] = "postgresql+asyncpg://x:y@h/db"
    os.environ["NATS_URL"] = "nats://x:y@h:4222"
    os.environ["REDIS_URL"] = "redis://h:6379/0"
    os.environ["LLM_GATEWAY_URL"] = "http://llm.local"

    settings = Settings()
    client = LLMClient(settings)
    normalizer = Normalizer(client)
    cand = RawCandidate(
        source="serper", source_url="https://romashka.ru", domain="romashka.ru", title="Ромашка"
    )
    result = await normalizer.normalize(
        cand, tenant_id=uuid.uuid4(), segment_context="Отрасль: производство"
    )
    assert result.is_company is True
    assert result.company["name"]["value"] == "Ромашка"
    await client.close()
