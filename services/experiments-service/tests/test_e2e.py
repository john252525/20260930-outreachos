"""Integration tests for experiments-service (real stack)."""

import uuid

import httpx
import pytest

TS = "http://127.0.0.1:48100"
EX = "http://127.0.0.1:48113"

pytestmark = pytest.mark.integration


async def _tenant(c: httpx.AsyncClient) -> str:
    stamp = uuid.uuid4().hex[:8]
    r = await c.post(f"{TS}/tenants", json={"name": "IT-exp", "slug": f"it-exp-{stamp}"})
    return str(r.json()["id"])


@pytest.mark.asyncio
async def test_healthz() -> None:
    async with httpx.AsyncClient(base_url=EX, timeout=10) as c:
        r = await c.get("/healthz")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_full_experiment_cycle() -> None:
    async with httpx.AsyncClient(timeout=30) as c:
        tenant = await _tenant(c)
        h = {"X-Tenant-ID": tenant, "Idempotency-Key": str(uuid.uuid4())}
        body = {
            "name": f"exp-{uuid.uuid4().hex[:6]}",
            "hypothesis": "тест",
            "variable_type": "subject",
            "channel": "email",
            "variants": [
                {"id": "A", "name": "A", "template_id": "email_cold_outreach", "weight": 0.5},
                {"id": "B", "name": "B", "template_id": "email_cold_outreach", "weight": 0.5},
            ],
            "metrics": {"primary": "positive_reply_rate"},
            "sample_size_per_variant": 10,
        }
        r = await c.post(f"{EX}/experiments", json=body, headers=h)
        assert r.status_code == 201, r.text
        exp_id = r.json()["id"]

        # start
        r = await c.post(
            f"{EX}/experiments/{exp_id}/start", headers={**h, "Idempotency-Key": str(uuid.uuid4())}
        )
        assert r.json()["status"] == "running"

        # assign is deterministic
        contact = str(uuid.uuid4())
        a = await c.post(
            f"{EX}/experiments/{exp_id}/assign",
            json={"contact_id": contact},
            headers={**h, "Idempotency-Key": str(uuid.uuid4())},
        )
        b = await c.post(
            f"{EX}/experiments/{exp_id}/assign",
            json={"contact_id": contact},
            headers={**h, "Idempotency-Key": str(uuid.uuid4())},
        )
        assert a.json()["variant_id"] == b.json()["variant_id"]
        assert a.json()["variant_id"] in ("A", "B")

        # evaluate -> insufficient data
        r = await c.post(
            f"{EX}/experiments/{exp_id}/evaluate",
            headers={**h, "Idempotency-Key": str(uuid.uuid4())},
        )
        assert r.json()["results"]["is_significant"] is False


@pytest.mark.asyncio
async def test_weights_must_sum_to_one() -> None:
    async with httpx.AsyncClient(timeout=30) as c:
        tenant = await _tenant(c)
        h = {"X-Tenant-ID": tenant, "Idempotency-Key": str(uuid.uuid4())}
        r = await c.post(
            f"{EX}/experiments",
            json={
                "name": f"bad-{uuid.uuid4().hex[:6]}",
                "variable_type": "subject",
                "variants": [
                    {"id": "A", "weight": 0.3},
                    {"id": "B", "weight": 0.3},
                ],
            },
            headers=h,
        )
        assert r.status_code == 422


@pytest.mark.asyncio
async def test_rls_isolation() -> None:
    async with httpx.AsyncClient(timeout=30) as c:
        tenant = await _tenant(c)
        h = {"X-Tenant-ID": tenant, "Idempotency-Key": str(uuid.uuid4())}
        r = await c.post(
            f"{EX}/experiments",
            json={
                "name": f"rls-{uuid.uuid4().hex[:6]}",
                "variable_type": "subject",
                "variants": [{"id": "A", "weight": 1.0}],
            },
            headers=h,
        )
        exp_id = r.json()["id"]
        other = str(uuid.uuid4())
        r2 = await c.get(f"{EX}/experiments/{exp_id}", headers={"X-Tenant-ID": other})
        assert r2.status_code == 404
