"""Integration tests for analytics-service (real stack)."""

import uuid

import httpx
import pytest

AN = "http://127.0.0.1:48112"

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_healthz() -> None:
    async with httpx.AsyncClient(base_url=AN, timeout=10) as c:
        r = await c.get("/healthz")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_overview_requires_tenant() -> None:
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(f"{AN}/analytics/overview")
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_overview_shape() -> None:
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(f"{AN}/analytics/overview", headers={"X-Tenant-ID": str(uuid.uuid4())})
    assert r.status_code == 200
    data = r.json()
    assert "reply_rate" in data
    assert "bounce_rate" in data


@pytest.mark.asyncio
async def test_rls_isolation() -> None:
    async with httpx.AsyncClient(timeout=15) as c:
        other = str(uuid.uuid4())
        r = await c.get(f"{AN}/analytics/funnel", headers={"X-Tenant-ID": other})
        assert r.status_code == 200
        data = r.json()
        assert data["sent"] == 0
        assert data["replied"] == 0
