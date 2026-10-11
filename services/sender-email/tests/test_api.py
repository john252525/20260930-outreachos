"""Integration test for sender-email (full sprint-3 flow, dry-run)."""

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
SE = "http://127.0.0.1:48108"

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_healthz() -> None:
    async with httpx.AsyncClient(base_url=SE, timeout=10) as c:
        r = await c.get("/healthz")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_full_send_flow_dry_run() -> None:
    stamp = uuid.uuid4().hex[:8]
    async with httpx.AsyncClient(timeout=180) as c:
        t = (await c.post(f"{TS}/tenants", json={"name": "IT-se", "slug": f"it-se-{stamp}"})).json()["id"]
        h = {"X-Tenant-ID": t, "Idempotency-Key": str(uuid.uuid4())}

        acc = (
            await c.post(
                f"{SE}/accounts",
                json={
                    "email": "sergey@example.com", "user_id": "user-1",
                    "smtp_host": "smtp.example.com", "smtp_username": "dry-run",
                    "smtp_password": "secret",
                },
                headers=h,
            )
        ).json()
        assert acc["status"] == "unverified"
        await c.post(f"{SE}/accounts/{acc['id']}/verify",
                     headers={**h, "Idempotency-Key": str(uuid.uuid4())})

        cid = (await c.post(f"{CS}/companies",
               json={"payload": {"name": {"value": "Test Co", "confidence": 1.0, "evidence": []},
                                 "domain": {"value": f"t-{stamp}.ru", "confidence": 1.0, "evidence": []}}},
               headers=h)).json()["company"]["id"]
        ct = (await c.post(f"{CS}/contacts",
              json={"payload": {"full_name": {"value": "Ivan Petrov", "confidence": 1.0, "evidence": []},
                                "emails": [{"value": f"ivan-{stamp}@t.ru", "is_primary": True, "confidence": 0.9, "evidence": []}],
                                "phones": [], "company_id": cid}},
              headers={**h, "Idempotency-Key": str(uuid.uuid4())})).json()["contact"]["id"]
        bid = (await c.post(f"{BR}/briefs", json={"text": "Гидроборты, ищем дистрибьюторов"},
               headers={**h, "Idempotency-Key": str(uuid.uuid4())})).json()["id"]
        await c.post(f"{BR}/briefs/{bid}/complete", headers={**h, "Idempotency-Key": str(uuid.uuid4())})
        ir = (await c.post(f"{ICP}/icps", json={"brief_id": bid},
              headers={**h, "Idempotency-Key": str(uuid.uuid4())})).json()
        msg = (await c.post(f"{CO}/messages",
               json={"contact_id": ct, "icp_id": ir["id"],
                     "segment_id": ir["payload"]["segments"][0]["id"],
                     "channel": "email", "sender_user_id": "user-1",
                     "sender_from_name": "S", "sender_signature": "S, Sales"},
               headers={**h, "Idempotency-Key": str(uuid.uuid4())})).json()
        msg_id = msg["id"]

        # wait for review item
        item_id = None
        for _ in range(15):
            items = (await c.get(f"{RV}/review-items?status=pending", headers=h)).json()
            match = [i for i in items if i["message_id"] == msg_id]
            if match:
                item_id = match[0]["id"]
                break
            await asyncio.sleep(2)
        assert item_id

        await c.post(f"{RV}/review-items/{item_id}/approve", json={},
                     headers={**h, "X-User-Id": "rev-1", "Idempotency-Key": str(uuid.uuid4())})

        # wait for send
        status = "approved"
        for _ in range(15):
            m = (await c.get(f"{CO}/messages/{msg_id}", headers=h)).json()
            status = m["status"]
            if status in ("sent", "failed"):
                break
            await asyncio.sleep(2)
        assert status == "sent", m
        assert (m.get("delivery") or {}).get("provider_message_id", "").startswith("dry-run-")
