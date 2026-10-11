"""Integration test for reply-classifier (real stack + LLM)."""

import uuid

import httpx
import pytest

TS = "http://127.0.0.1:48100"
BR = "http://127.0.0.1:48102"
ICP = "http://127.0.0.1:48104"
CS = "http://127.0.0.1:48103"
CO = "http://127.0.0.1:48106"
RC = "http://127.0.0.1:48111"

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_healthz() -> None:
    async with httpx.AsyncClient(base_url=RC, timeout=10) as c:
        r = await c.get("/healthz")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_list_replies_requires_tenant() -> None:
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(f"{RC}/replies")
    # Middleware rejects missing tenant header
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_rls_isolation() -> None:
    async with httpx.AsyncClient(timeout=30) as c:
        other = str(uuid.uuid4())
        r = await c.get(f"{RC}/replies", headers={"X-Tenant-ID": other})
        assert r.status_code == 200
        assert r.json() == []
