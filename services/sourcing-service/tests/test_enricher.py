"""Tests for the enricher connector (with a fake provider)."""

import pytest
from sourcing_service.connectors.base import SearchCriteria
from sourcing_service.connectors.enricher import EnricherConnector, EnricherProvider


class _FakeEnricher(EnricherProvider):
    name = "fake"

    async def find_email(
        self, *, domain: str, first_name: str | None, last_name: str | None
    ) -> dict | None:
        return {"email": f"{first_name}@{domain}", "confidence": 90}

    async def domain_emails(self, *, domain: str, limit: int = 10) -> list[dict]:
        return []


@pytest.mark.asyncio
async def test_enricher_finds_email() -> None:
    connector = EnricherConnector(_FakeEnricher())
    criteria = SearchCriteria(
        keywords=[],
        extra={
            "contacts": [
                {
                    "company_domain": "romashka.ru",
                    "full_name": "Иван Петров",
                    "first_name": "Иван",
                    "last_name": "Петров",
                }
            ]
        },
    )
    result = await connector.search(criteria)
    assert len(result.candidates) == 1
    assert result.candidates[0].raw_payload["email"] == "Иван@romashka.ru"
    assert result.cost_usd > 0
    await connector.close()
