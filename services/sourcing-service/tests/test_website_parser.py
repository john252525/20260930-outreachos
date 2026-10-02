"""Tests for the website parser connector."""

import httpx
import pytest
import respx
from sourcing_service.connectors.base import SearchCriteria
from sourcing_service.connectors.website_parser import WebsiteParserConnector

_HTML = (
    """
<html><head><title>Ромашка</title>
<meta name="description" content="Производство гидробортов"></head>
<body><h1>Ромашка</h1>
<p>Свяжитесь: sales@romashka.ru, тел +7 900 123-45-67</p>
<p>"""
    + ("Текст компании. " * 60)
    + """</p></body></html>
"""
)


@pytest.mark.asyncio
@respx.mock
async def test_parse_extracts_text_and_contacts() -> None:
    respx.get("https://romashka.ru").mock(return_value=httpx.Response(200, text=_HTML))
    connector = WebsiteParserConnector()
    criteria = SearchCriteria(keywords=[], extra={"urls": ["https://romashka.ru"]})
    result = await connector.search(criteria)
    assert len(result.candidates) == 1
    cand = result.candidates[0]
    assert cand.domain == "romashka.ru"
    assert "sales@romashka.ru" in cand.raw_payload["emails"]
    assert any("+7" in p for p in cand.raw_payload["phones"])
    await connector.close()


@pytest.mark.asyncio
async def test_no_urls_returns_error() -> None:
    connector = WebsiteParserConnector()
    result = await connector.search(SearchCriteria(keywords=[]))
    assert result.candidates == []
    assert result.error
    await connector.close()
