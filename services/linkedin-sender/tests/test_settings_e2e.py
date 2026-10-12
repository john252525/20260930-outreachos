"""Integration tests for per-tenant settings (tenant-service)."""

import uuid

import httpx
import pytest

TS = "http://127.0.0.1:48100"

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_settings_autocreate_and_patch() -> None:
    async with httpx.AsyncClient(timeout=20) as c:
        stamp = uuid.uuid4().hex[:8]
        t = (
            await c.post(f"{TS}/tenants", json={"name": "IT-set", "slug": f"it-set-{stamp}"})
        ).json()["id"]
        h = {"X-Tenant-ID": t, "Idempotency-Key": str(uuid.uuid4())}
        r = await c.get(f"{TS}/tenants/{t}/settings", headers={"X-Tenant-ID": t})
        assert r.status_code == 200
        assert r.json()["email_enabled"] is True

        r = await c.patch(
            f"{TS}/tenants/{t}/settings",
            json={"linkedin_enabled": True, "auto_contacts_to_drafts": True},
            headers=h,
        )
        assert r.json()["linkedin_enabled"] is True
        assert r.json()["auto_contacts_to_drafts"] is True
