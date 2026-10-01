"""Integration tests for the icp-service HTTP API."""

import uuid

import httpx
import pytest

ICP_URL = "http://127.0.0.1:48104"
TENANT_URL = "http://127.0.0.1:48100"
BRIEF_URL = "http://127.0.0.1:48102"

pytestmark = pytest.mark.integration


async def _make_complete_brief(c: httpx.AsyncClient, tenant: str) -> str:
    """Create a brief and force-complete it."""
    r = await c.post(
        "/briefs",
        json={"text": "Производим гидроборты для грузовиков, ищем дистрибьюторов в РФ"},
        headers={"X-Tenant-ID": tenant, "Idempotency-Key": str(uuid.uuid4())},
    )
    brief_id = r.json()["id"]
    await c.post(
        f"/briefs/{brief_id}/complete",
        headers={"X-Tenant-ID": tenant, "Idempotency-Key": str(uuid.uuid4())},
    )
    return brief_id


@pytest.mark.asyncio
async def test_healthz() -> None:
    async with httpx.AsyncClient(base_url=ICP_URL, timeout=10) as c:
        r = await c.get("/healthz")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_generate_and_get() -> None:
    tenant = str(uuid.uuid4())
    async with httpx.AsyncClient(base_url=BRIEF_URL, timeout=180) as c:
        brief_id = await _make_complete_brief(c, tenant)

        gen = await c.post(
            f"{ICP_URL}/icps",
            json={"brief_id": brief_id},
            headers={"X-Tenant-ID": tenant, "Idempotency-Key": str(uuid.uuid4())},
        )
        assert gen.status_code == 201, gen.text
        data = gen.json()
        assert data["version"] == 1
        assert data["is_active"] is True
        assert data["segments_count"] >= 1
        assert data["brief_id"] == brief_id
        icp_id = data["id"]

        # weights sum to 1.0
        for seg in data["payload"]["segments"]:
            assert abs(sum(seg["scoring_weights"].values()) - 1.0) < 1e-6

        got = await c.get(f"{ICP_URL}/icps/{icp_id}", headers={"X-Tenant-ID": tenant})
        assert got.status_code == 200
        assert got.json()["id"] == icp_id


@pytest.mark.asyncio
async def test_revise_and_activate() -> None:
    tenant = str(uuid.uuid4())
    async with httpx.AsyncClient(base_url=BRIEF_URL, timeout=240) as c:
        brief_id = await _make_complete_brief(c, tenant)
        h = {"X-Tenant-ID": tenant, "Idempotency-Key": str(uuid.uuid4())}

        gen = await c.post(f"{ICP_URL}/icps", json={"brief_id": brief_id}, headers=h)
        assert gen.status_code == 201
        icp_id = gen.json()["id"]

        rev = await c.post(
            f"{ICP_URL}/icps/{icp_id}/revise",
            headers={"X-Tenant-ID": tenant, "Idempotency-Key": str(uuid.uuid4())},
        )
        assert rev.status_code == 201
        assert rev.json()["version"] == 2
        assert rev.json()["is_active"] is True

        # v1 is no longer active
        v1 = await c.get(f"{ICP_URL}/icps/{icp_id}", headers={"X-Tenant-ID": tenant})
        assert v1.json()["is_active"] is False

        # active for brief -> v2
        act = await c.get(
            f"{ICP_URL}/icps/active/by-brief/{brief_id}", headers={"X-Tenant-ID": tenant}
        )
        assert act.json()["version"] == 2

        # rollback to v1
        back = await c.post(
            f"{ICP_URL}/icps/{icp_id}/activate",
            headers={"X-Tenant-ID": tenant, "Idempotency-Key": str(uuid.uuid4())},
        )
        assert back.status_code == 200
        assert back.json()["version"] == 1
        assert back.json()["is_active"] is True

        act2 = await c.get(
            f"{ICP_URL}/icps/active/by-brief/{brief_id}", headers={"X-Tenant-ID": tenant}
        )
        assert act2.json()["version"] == 1


@pytest.mark.asyncio
async def test_rls_isolation() -> None:
    tenant = str(uuid.uuid4())
    other = str(uuid.uuid4())
    async with httpx.AsyncClient(base_url=BRIEF_URL, timeout=180) as c:
        brief_id = await _make_complete_brief(c, tenant)
        gen = await c.post(
            f"{ICP_URL}/icps",
            json={"brief_id": brief_id},
            headers={"X-Tenant-ID": tenant, "Idempotency-Key": str(uuid.uuid4())},
        )
        icp_id = gen.json()["id"]
        r = await c.get(f"{ICP_URL}/icps/{icp_id}", headers={"X-Tenant-ID": other})
        assert r.status_code == 404
