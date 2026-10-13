"""Integration tests for whatsapp templates."""

import uuid

import httpx
import pytest

WA = "http://127.0.0.1:48121"

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_template_flow() -> None:
    async with httpx.AsyncClient(timeout=20) as c:
        stamp = uuid.uuid4().hex[:8]
        t = (await c.post("http://127.0.0.1:48100/tenants", json={"name": "IT-wat", "slug": f"it-wat-{stamp}"})).json()["id"]
        h = {"X-Tenant-ID": t, "Idempotency-Key": str(uuid.uuid4())}
        r = await c.post(
            f"{WA}/templates",
            json={"name": f"tmpl_{stamp}", "language": "ru", "category": "marketing", "body_template": "Привет {{1}}"},
            headers=h,
        )
        assert r.status_code == 201, r.text
        r = await c.get(f"{WA}/templates", headers={"X-Tenant-ID": t})
        assert len(r.json()) == 1
