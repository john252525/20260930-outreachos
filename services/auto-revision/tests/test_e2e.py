"""Integration tests for auto-revision (real stack)."""

import uuid

import httpx
import pytest

REV = "http://127.0.0.1:48115"

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_healthz() -> None:
    async with httpx.AsyncClient(base_url=REV, timeout=10) as c:
        r = await c.get("/healthz")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_list_requires_tenant() -> None:
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(f"{REV}/revisions")
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_rls_isolation() -> None:
    async with httpx.AsyncClient(timeout=15) as c:
        other = str(uuid.uuid4())
        r = await c.get(f"{REV}/revisions", headers={"X-Tenant-ID": other})
        assert r.status_code == 200
        assert r.json() == []
