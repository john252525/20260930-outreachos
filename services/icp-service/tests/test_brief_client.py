"""Tests for the brief-service HTTP client (mocked with respx)."""

import httpx
import pytest
import respx
from icp_service.brief_client import BriefClient, BriefNotFoundError


@pytest.mark.asyncio
@respx.mock
async def test_get_brief_success() -> None:
    respx.get("http://brief.local/briefs/abc").mock(
        return_value=httpx.Response(200, json={"id": "abc", "status": "complete"})
    )
    client = BriefClient("http://brief.local")
    result = await client.get_brief("abc", tenant_id="t1")
    assert result["id"] == "abc"
    await client.close()


@pytest.mark.asyncio
@respx.mock
async def test_get_brief_not_found() -> None:
    respx.get("http://brief.local/briefs/abc").mock(return_value=httpx.Response(404))
    client = BriefClient("http://brief.local")
    with pytest.raises(BriefNotFoundError):
        await client.get_brief("abc", tenant_id="t1")
    await client.close()
