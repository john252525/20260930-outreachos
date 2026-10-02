"""Integration tests for the sourcing-service HTTP API (real stack + website_parser)."""

import asyncio
import uuid

import httpx
import pytest

SRC_URL = "http://127.0.0.1:48105"
TENANT_URL = "http://127.0.0.1:48100"
BRIEF_URL = "http://127.0.0.1:48102"
ICP_URL = "http://127.0.0.1:48104"

pytestmark = pytest.mark.integration


async def _tenant(c: httpx.AsyncClient) -> str:
    r = await c.post(
        f"{TENANT_URL}/tenants",
        json={"name": "IT-src", "slug": f"it-src-{uuid.uuid4().hex[:8]}"},
    )
    return r.json()["id"]


async def _icp(c: httpx.AsyncClient, tenant: str) -> tuple[str, str]:
    r = await c.post(
        f"{BRIEF_URL}/briefs",
        json={"text": "Продаём промышленное оборудование, ищем дистрибьюторов"},
        headers={"X-Tenant-ID": tenant, "Idempotency-Key": str(uuid.uuid4())},
    )
    bid = r.json()["id"]
    await c.post(
        f"{BRIEF_URL}/briefs/{bid}/complete",
        headers={"X-Tenant-ID": tenant, "Idempotency-Key": str(uuid.uuid4())},
    )
    r2 = await c.post(
        f"{ICP_URL}/icps",
        json={"brief_id": bid},
        headers={"X-Tenant-ID": tenant, "Idempotency-Key": str(uuid.uuid4())},
    )
    data = r2.json()
    return data["id"], data["payload"]["segments"][0]["id"]


@pytest.mark.asyncio
async def test_healthz() -> None:
    async with httpx.AsyncClient(base_url=SRC_URL, timeout=10) as c:
        r = await c.get("/healthz")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_create_search_job_and_wait() -> None:
    async with httpx.AsyncClient(timeout=240) as c:
        tenant = await _tenant(c)
        icp_id, seg_id = await _icp(c, tenant)
        r = await c.post(
            f"{SRC_URL}/searches",
            json={
                "icp_id": icp_id,
                "segment_id": seg_id,
                "sources": ["website_parser"],
                "urls": ["https://toyota-forklift.ru/"],
                "limit_per_source": 3,
            },
            headers={"X-Tenant-ID": tenant, "Idempotency-Key": str(uuid.uuid4())},
        )
        assert r.status_code == 201, r.text
        job_id = r.json()["id"]

        status = "pending"
        g = None
        for _ in range(30):
            g = await c.get(f"{SRC_URL}/searches/{job_id}", headers={"X-Tenant-ID": tenant})
            status = g.json()["status"]
            if status in ("completed", "failed"):
                break
            await asyncio.sleep(4)
        assert status == "completed", g.text if g else ""
        assert g is not None and g.json()["candidates_raw_count"] >= 1


@pytest.mark.asyncio
async def test_rls_isolation() -> None:
    async with httpx.AsyncClient(timeout=240) as c:
        tenant = await _tenant(c)
        icp_id, seg_id = await _icp(c, tenant)
        r = await c.post(
            f"{SRC_URL}/searches",
            json={
                "icp_id": icp_id,
                "segment_id": seg_id,
                "sources": ["website_parser"],
                "urls": [],
            },
            headers={"X-Tenant-ID": tenant, "Idempotency-Key": str(uuid.uuid4())},
        )
        job_id = r.json()["id"]
        other = str(uuid.uuid4())
        r2 = await c.get(f"{SRC_URL}/searches/{job_id}", headers={"X-Tenant-ID": other})
        assert r2.status_code == 404
