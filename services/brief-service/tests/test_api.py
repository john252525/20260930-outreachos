"""Integration tests for the brief-service HTTP API.

These require a running dev stack (postgres + nats + redis + llm-gateway +
brief-service). Run with:  uv run pytest -m integration
"""

import uuid

import httpx
import pytest

BASE_URL = "http://127.0.0.1:48102"

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_healthz() -> None:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10) as c:
        r = await c.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_create_brief_minimal(headers: dict[str, str]) -> None:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=90) as c:
        r = await c.post(
            "/briefs", json={"text": "Компания делает CRM для малого бизнеса"}, headers=headers
        )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["status"] in ("in_progress", "complete")
    assert data["id"]


@pytest.mark.asyncio
async def test_create_brief_requires_tenant() -> None:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10) as c:
        r = await c.post("/briefs", json={"text": "X"}, headers={"Idempotency-Key": "x"})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_create_brief_requires_input(headers: dict[str, str]) -> None:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10) as c:
        r = await c.post("/briefs", json={}, headers=headers)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_get_brief(headers: dict[str, str]) -> None:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=90) as c:
        create = await c.post("/briefs", json={"text": "X делает Y"}, headers=headers)
        brief_id = create.json()["id"]
        r = await c.get(f"/briefs/{brief_id}", headers=headers)
    assert r.status_code == 200
    assert r.json()["id"] == brief_id


@pytest.mark.asyncio
async def test_rls_isolation() -> None:
    headers_a = {"X-Tenant-ID": str(uuid.uuid4()), "Idempotency-Key": str(uuid.uuid4())}
    headers_b = {"X-Tenant-ID": str(uuid.uuid4())}
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=90) as c:
        create = await c.post("/briefs", json={"text": "A"}, headers=headers_a)
        brief_id = create.json()["id"]
        r = await c.get(f"/briefs/{brief_id}", headers=headers_b)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_status_endpoints(headers: dict[str, str]) -> None:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=90) as c:
        create = await c.post("/briefs", json={"text": "Статусы"}, headers=headers)
        brief_id = create.json()["id"]
        complete = await c.post(
            f"/briefs/{brief_id}/complete",
            headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
        )
        assert complete.json()["status"] == "complete"
        abandon = await c.post(
            f"/briefs/{brief_id}/abandon",
            json={"reason": "test"},
            headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
        )
        assert abandon.json()["status"] == "abandoned"
        archive = await c.delete(
            f"/briefs/{brief_id}",
            headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
        )
        assert archive.status_code == 204
