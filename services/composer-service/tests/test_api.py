"""Integration test for composer-service (real stack + LLM)."""

import uuid

import httpx
import pytest

TS = "http://127.0.0.1:48100"
BR = "http://127.0.0.1:48102"
ICP = "http://127.0.0.1:48104"
CS = "http://127.0.0.1:48103"
CO = "http://127.0.0.1:48106"

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_healthz() -> None:
    async with httpx.AsyncClient(base_url=CO, timeout=10) as c:
        r = await c.get("/healthz")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_draft_message() -> None:
    stamp = uuid.uuid4().hex[:8]
    async with httpx.AsyncClient(timeout=180) as c:
        t = (
            await c.post(f"{TS}/tenants", json={"name": "IT-cmp", "slug": f"it-cmp-{stamp}"})
        ).json()["id"]
        h = {"X-Tenant-ID": t, "Idempotency-Key": str(uuid.uuid4())}

        cid = (
            await c.post(
                f"{CS}/companies",
                json={
                    "payload": {
                        "name": {"value": "ООО Тест", "confidence": 1.0, "evidence": []},
                        "domain": {"value": f"test-{stamp}.ru", "confidence": 1.0, "evidence": []},
                    }
                },
                headers=h,
            )
        ).json()["company"]["id"]
        ct = (
            await c.post(
                f"{CS}/contacts",
                json={
                    "payload": {
                        "full_name": {"value": "Иван Петров", "confidence": 1.0, "evidence": []},
                        "emails": [
                            {
                                "value": f"ivan-{stamp}@test.ru",
                                "is_primary": True,
                                "confidence": 0.9,
                                "evidence": [],
                            }
                        ],
                        "phones": [],
                        "company_id": cid,
                    }
                },
                headers={**h, "Idempotency-Key": str(uuid.uuid4())},
            )
        ).json()["contact"]["id"]

        bid = (
            await c.post(
                f"{BR}/briefs",
                json={"text": "Производим гидроборты для грузовиков, ищем дистрибьюторов"},
                headers={**h, "Idempotency-Key": str(uuid.uuid4())},
            )
        ).json()["id"]
        await c.post(
            f"{BR}/briefs/{bid}/complete",
            headers={**h, "Idempotency-Key": str(uuid.uuid4())},
        )
        ir = (
            await c.post(
                f"{ICP}/icps",
                json={"brief_id": bid},
                headers={**h, "Idempotency-Key": str(uuid.uuid4())},
            )
        ).json()
        icp_id = ir["id"]
        seg = ir["payload"]["segments"][0]["id"]

        r = await c.post(
            f"{CO}/messages",
            json={
                "contact_id": ct,
                "icp_id": icp_id,
                "segment_id": seg,
                "channel": "email",
                "language": "ru",
                "sender_identity_type": "user",
                "sender_from_name": "Сергей",
                "sender_signature": "Сергей, Sales",
            },
            headers={**h, "Idempotency-Key": str(uuid.uuid4())},
        )
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["subject"]
        assert data["word_count"] > 10
        assert data["status"] == "draft"
        msg_id = data["id"]

        # RLS
        other = str(uuid.uuid4())
        r2 = await c.get(f"{CO}/messages/{msg_id}", headers={"X-Tenant-ID": other})
        assert r2.status_code == 404
