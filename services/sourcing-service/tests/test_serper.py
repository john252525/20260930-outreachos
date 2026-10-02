"""Tests for the Serper connector."""

import httpx
import pytest
import respx
from sourcing_service.connectors.base import SearchCriteria
from sourcing_service.connectors.serper import SerperConnector


@pytest.mark.asyncio
@respx.mock
async def test_serper_search_success() -> None:
    respx.post("https://google.serper.dev/search").mock(
        return_value=httpx.Response(
            200,
            json={
                "organic": [
                    {
                        "link": "https://romashka.ru/about",
                        "title": "Ромашка",
                        "snippet": "Производство",
                    },
                    {"link": "https://romashka.ru/contacts", "title": "Контакты", "snippet": "..."},
                    {"link": "https://test.com", "title": "Test", "snippet": "..."},
                ]
            },
        )
    )
    connector = SerperConnector(
        api_key="test", base_url="https://google.serper.dev", rate_limit_per_sec=1000
    )
    criteria = SearchCriteria(
        keywords=["гидроборты дистрибьютор"], geo=["RU"], language="ru", limit=10
    )
    result = await connector.search(criteria)
    assert len(result.candidates) == 2
    assert result.candidates[0].domain == "romashka.ru"
    assert result.cost_usd > 0
    await connector.close()


@pytest.mark.asyncio
async def test_serper_unavailable_without_key() -> None:
    connector = SerperConnector(api_key="", base_url="https://google.serper.dev")
    assert not connector.is_available
    await connector.close()


@pytest.mark.asyncio
@respx.mock
async def test_serper_blacklist() -> None:
    respx.post("https://google.serper.dev/search").mock(
        return_value=httpx.Response(
            200,
            json={"organic": [{"link": "https://bad.com", "title": "Bad", "snippet": ""}]},
        )
    )
    connector = SerperConnector(
        api_key="k", base_url="https://google.serper.dev", rate_limit_per_sec=1000
    )
    criteria = SearchCriteria(keywords=["x"], domain_blacklist=["bad.com"])
    result = await connector.search(criteria)
    assert result.candidates == []
    await connector.close()
