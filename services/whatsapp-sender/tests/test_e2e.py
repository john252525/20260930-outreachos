"""Integration tests for whatsapp-sender."""

import uuid

import httpx
import pytest

WA = "http://127.0.0.1:48121"

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_healthz() -> None:
    async with httpx.AsyncClient(base_url=WA, timeout=10) as c:
        r = await c.get("/healthz")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_account_flow() -> None:
    async with httpx.AsyncClient(timeout=20) as c:
        stamp = uuid.uuid4().hex[:8]
        t = (await c.post("http://127.0.0.1:48100/tenants", json={"name": "IT-wa", "slug": f"it-wa-{stamp}"})).json()["id"]
        h = {"X-Tenant-ID": t, "Idempotency-Key": str(uuid.uuid4())}
        r = await c.post(
            f"{WA}/accounts",
            json={"provider": "gupshup", "phone_number": f"+7900{stamp[:7]}", "provider_account_id": "app", "api_key": "k"},
            headers=h,
        )
        assert r.status_code == 201, r.text
        r = await c.get(f"{WA}/accounts", headers={"X-Tenant-ID": t})
        assert len(r.json()) == 1
