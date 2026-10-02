"""Tests for the registry connector (with a fake provider)."""

import pytest
from sourcing_service.connectors.base import SearchCriteria
from sourcing_service.connectors.registry_connector import RegistryConnector, RegistryProvider


class _FakeProvider(RegistryProvider):
    name = "fake"

    async def search_by_query(self, query: str, *, limit: int = 10) -> list[dict]:
        return [
            {
                "data": {
                    "name": {"short_with_opf": "ООО Ромашка"},
                    "inn": "7707083893",
                    "ogrn": "1027700132195",
                    "address": {"value": "Москва"},
                    "state": {"status": "ACTIVE"},
                }
            },
            {
                "data": {
                    "name": {"short_with_opf": "ООО Мертвая"},
                    "inn": "0000000000",
                    "state": {"status": "LIQUIDATED"},
                }
            },
        ]

    async def search_by_inn(self, inn: str) -> dict | None:
        return None


@pytest.mark.asyncio
async def test_registry_filters_liquidated() -> None:
    connector = RegistryConnector(_FakeProvider())
    criteria = SearchCriteria(keywords=["Ромашка"], limit=10)
    result = await connector.search(criteria)
    assert len(result.candidates) == 1
    assert result.candidates[0].raw_payload["inn"] == "7707083893"
    await connector.close()
