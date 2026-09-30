"""Integration tests for the dev-console."""

import httpx
import pytest

BASE_URL = "http://127.0.0.1:48110"

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_healthz() -> None:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10) as c:
        r = await c.get("/healthz")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_index_html() -> None:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10) as c:
        r = await c.get("/")
    assert r.status_code == 200
    assert "Outreach Dev Console" in r.text


@pytest.mark.asyncio
async def test_services_reports_all() -> None:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15) as c:
        r = await c.get("/api/services")
    names = {s["service"] for s in r.json()}
    assert {"tenant-service", "brief-service", "llm-gateway", "contact-store"} <= names


@pytest.mark.asyncio
async def test_streams() -> None:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15) as c:
        r = await c.get("/api/streams")
    names = {s["name"] for s in r.json()}
    assert {"TENANTS", "BRIEFS", "CONTACTS", "LLM_CALLS", "SYSTEM"} <= names


@pytest.mark.asyncio
async def test_tenants() -> None:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15) as c:
        r = await c.get("/api/tenants")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
