"""Integration tests for linkedin-sender (real stack)."""

import uuid

import httpx
import pytest

TS = "http://127.0.0.1:48100"
LI = "http://127.0.0.1:48118"

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_healthz() -> None:
    async with httpx.AsyncClient(base_url=LI, timeout=10) as c:
        r = await c.get("/healthz")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_account_flow() -> None:
    async with httpx.AsyncClient(timeout=20) as c:
        stamp = uuid.uuid4().hex[:8]
        t = (await c.post(f"{TS}/tenants", json={"name": "IT-li", "slug": f"it-li-{stamp}"})).json()["id"]
        h = {"X-Tenant-ID": t, "Idempotency-Key": str(uuid.uuid4())}
        r = await c.post(
            f"{LI}/accounts",
            json={
                "email": f"li-{stamp}@example.com",
                "password": "secret",
                "proxy_url": "http://u:p@proxy:8080",
            },
            headers=h,
        )
        assert r.status_code == 201, r.text
        assert r.json()["status"] == "active"
        r = await c.get(f"{LI}/accounts", headers={"X-Tenant-ID": t})
        assert len(r.json()) == 1


@pytest.mark.asyncio
async def test_rls_isolation() -> None:
    async with httpx.AsyncClient(timeout=15) as c:
        other = str(uuid.uuid4())
        r = await c.get(f"{LI}/accounts", headers={"X-Tenant-ID": other})
        assert r.status_code == 200
        assert r.json() == []
