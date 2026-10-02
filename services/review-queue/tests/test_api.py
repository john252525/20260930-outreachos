"""Integration tests for review-queue (real stack + LLM)."""

import asyncio
import uuid

import httpx
import pytest

TS = "http://127.0.0.1:48100"
BR = "http://127.0.0.1:48102"
ICP = "http://127.0.0.1:48104"
CS = "http://127.0.0.1:48103"
CO = "http://127.0.0.1:48106"
RV = "http://127.0.0.1:48107"

pytestmark = pytest.mark.integration


async def _draft(c: httpx.AsyncClient) -> tuple[str, str]:
    stamp = uuid.uuid4().hex[:8]
    t = (
        await c.post(f"{TS}/tenants", json={"name": "IT-rev", "slug": f"it-rev-{stamp}"})
    ).json()["id"]
    h = {"X-Tenant-ID": t, "Idempotency-Key": str(uuid.uuid4())}
    cid = (
        await c.post(
            f"{CS}/companies",
            json={"payload": {"name": {"value": "ООО Т", "confidence": 1.0, "evidence": []},
                              "domain": {"value": f"t-{stamp}.ru", "confidence": 1.0, "evidence": []}}},
            headers=h,
        )
    ).json()["company"]["id"]
    ct = (
        await c.post(
            f"{CS}/contacts",
            json={"payload": {"full_name": {"value": "Иван Петров", "confidence": 1.0, "evidence": []},
                              "emails": [{"value": f"i-{stamp}@t.ru", "is_primary": True, "confidence": 0.9, "evidence": []}],
                              "phones": [], "company_id": cid}},
            headers={**h, "Idempotency-Key": str(uuid.uuid4())},
        )
    ).json()["contact"]["id"]
    bid = (
        await c.post(f"{BR}/briefs", json={"text": "Производим гидроборты, ищем дистрибьюторов"},
                     headers={**h, "Idempotency-Key": str(uuid.uuid4())})
    ).json()["id"]
    await c.post(f"{BR}/briefs/{bid}/complete", headers={**h, "Idempotency-Key": str(uuid.uuid4())})
    ir = (
        await c.post(f"{ICP}/icps", json={"brief_id": bid}, headers={**h, "Idempotency-Key": str(uuid.uuid4())})
    ).json()
    msg = (
        await c.post(f"{CO}/messages",
                     json={"contact_id": ct, "icp_id": ir["id"], "segment_id": ir["payload"]["segments"][0]["id"],
                           "channel": "email", "sender_from_name": "С", "sender_signature": "С, Sales"},
                     headers={**h, "Idempotency-Key": str(uuid.uuid4())})
    ).json()
    return t, msg["id"]


@pytest.mark.asyncio
async def test_healthz() -> None:
    async with httpx.AsyncClient(base_url=RV, timeout=10) as c:
        r = await c.get("/healthz")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_full_review_flow() -> None:
    async with httpx.AsyncClient(timeout=180) as c:
        tenant, msg_id = await _draft(c)
        h = {"X-Tenant-ID": tenant}

        # wait for review item via NATS
        item_id = None
        for _ in range(15):
            r = await c.get(f"{RV}/review-items?status=pending", headers=h)
            items = r.json()
            match = [i for i in items if i["message_id"] == msg_id]
            if match:
                item_id = match[0]["id"]
                break
            await asyncio.sleep(2)
        assert item_id, "review item not created"

        # approve
        r = await c.post(
            f"{RV}/review-items/{item_id}/approve",
            json={},
            headers={**h, "X-User-Id": "rev-1", "Idempotency-Key": str(uuid.uuid4())},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "approved"

        # message updated in composer
        m = await c.get(f"{CO}/messages/{msg_id}", headers=h)
        assert m.json()["status"] == "approved"
        assert m.json()["review"]["reviewed_by"] == "rev-1"


@pytest.mark.asyncio
async def test_rls_isolation() -> None:
    async with httpx.AsyncClient(timeout=180) as c:
        tenant, msg_id = await _draft(c)
        item_id = None
        for _ in range(15):
            r = await c.get(f"{RV}/review-items?status=pending", headers={"X-Tenant-ID": tenant})
            match = [i for i in r.json() if i["message_id"] == msg_id]
            if match:
                item_id = match[0]["id"]
                break
            await asyncio.sleep(2)
        assert item_id
        other = str(uuid.uuid4())
        r2 = await c.get(f"{RV}/review-items/{item_id}", headers={"X-Tenant-ID": other})
        assert r2.status_code == 404
