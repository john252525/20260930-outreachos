"""Integration tests for telegram-sender (real stack)."""

import uuid

import httpx
import pytest

TS = "http://127.0.0.1:48100"
TG = "http://127.0.0.1:48116"

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_healthz() -> None:
    async with httpx.AsyncClient(base_url=TG, timeout=10) as c:
        r = await c.get("/healthz")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_full_bot_account_flow() -> None:
    async with httpx.AsyncClient(timeout=20) as c:
        stamp = uuid.uuid4().hex[:8]
        t = (
            await c.post(f"{TS}/tenants", json={"name": "IT-tg", "slug": f"it-tg-{stamp}"})
        ).json()["id"]
        h = {"X-Tenant-ID": t, "Idempotency-Key": str(uuid.uuid4())}
        r = await c.post(
            f"{TG}/accounts",
            json={
                "account_type": "bot",
                "bot_token": "123:TEST",
                "bot_username": f"test_bot_{stamp}",
                "display_name": "Bot",
            },
            headers=h,
        )
        assert r.status_code == 201, r.text
        acc_id = r.json()["id"]
        assert r.json()["status"] == "active"

        # list
        r = await c.get(f"{TG}/accounts", headers={"X-Tenant-ID": t})
        assert len(r.json()) == 1

        # verify
        r = await c.post(f"{TG}/accounts/{acc_id}/verify", headers={**h, "Idempotency-Key": str(uuid.uuid4())})
        assert r.json()["last_verified_at"] is not None

        # attempts empty
        r = await c.get(f"{TG}/attempts", headers={"X-Tenant-ID": t})
        assert r.json() == []


@pytest.mark.asyncio
async def test_rls_isolation() -> None:
    async with httpx.AsyncClient(timeout=15) as c:
        other = str(uuid.uuid4())
        r = await c.get(f"{TG}/accounts", headers={"X-Tenant-ID": other})
        assert r.status_code == 200
        assert r.json() == []
