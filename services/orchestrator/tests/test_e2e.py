"""Integration tests for orchestrator (real stack)."""

import uuid

import httpx
import pytest

TS = "http://127.0.0.1:48100"
ORCH = "http://127.0.0.1:48114"

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_healthz() -> None:
    async with httpx.AsyncClient(base_url=ORCH, timeout=10) as c:
        r = await c.get("/healthz")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_metrics_public() -> None:
    async with httpx.AsyncClient(base_url=ORCH, timeout=10) as c:
        r = await c.get("/metrics")
    assert r.status_code == 200
    assert "orchestrator_" in r.text


@pytest.mark.asyncio
async def test_flows_require_tenant() -> None:
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(f"{ORCH}/flows")
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_flows_rls_isolation() -> None:
    async with httpx.AsyncClient(timeout=15) as c:
        other = str(uuid.uuid4())
        r = await c.get(f"{ORCH}/flows", headers={"X-Tenant-ID": other})
        assert r.status_code == 200
        assert r.json() == []


@pytest.mark.asyncio
async def test_stats_shape() -> None:
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(f"{ORCH}/stats", headers={"X-Tenant-ID": str(uuid.uuid4())})
    assert r.status_code == 200
    data = r.json()
    assert "flows" in data
    assert "steps" in data
