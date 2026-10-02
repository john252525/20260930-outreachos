"""Tests for the Yandex XML connector."""

import httpx
import pytest
import respx
from sourcing_service.connectors.base import SearchCriteria
from sourcing_service.connectors.yandex_xml import YandexXMLConnector

_SAMPLE_XML = """<?xml version="1.0" encoding="utf-8"?>
<yandexsearch>
  <response>
    <results>
      <grouping>
        <group>
          <doc>
            <url>https://romashka.ru</url>
            <title>Ромашка</title>
            <passages><passage>Производство гидробортов</passage></passages>
          </doc>
          <doc>
            <url>https://romashka.ru/about</url>
            <title>О нас</title>
            <passages><passage>...</passage></passages>
          </doc>
        </group>
      </grouping>
    </results>
  </response>
</yandexsearch>"""


@pytest.mark.asyncio
@respx.mock
async def test_yandex_search_success() -> None:
    respx.get("https://yandex.com/search/xml").mock(
        return_value=httpx.Response(200, text=_SAMPLE_XML)
    )
    connector = YandexXMLConnector(user="u", key="k")
    criteria = SearchCriteria(keywords=["гидроборты"], geo=["RU"], limit=10)
    result = await connector.search(criteria)
    assert len(result.candidates) == 1  # dup domain removed
    assert result.candidates[0].domain == "romashka.ru"
    await connector.close()


@pytest.mark.asyncio
async def test_yandex_unavailable_without_creds() -> None:
    connector = YandexXMLConnector(user="", key="")
    assert not connector.is_available
    await connector.close()


def test_yandex_region_mapping() -> None:
    assert YandexXMLConnector._geo_to_yandex_region(["RU"]) == "225"
    assert YandexXMLConnector._geo_to_yandex_region(["KZ"]) == "159"
    assert YandexXMLConnector._geo_to_yandex_region([]) == "225"
