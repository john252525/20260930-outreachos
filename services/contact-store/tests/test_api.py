"""Integration tests for the contact-store HTTP API."""

import uuid

import httpx
import pytest

BASE_URL = "http://127.0.0.1:48103"

pytestmark = pytest.mark.integration


def _company(name: str = "Test Corp", domain: str | None = None) -> dict:
    payload: dict = {"name": {"value": name, "confidence": 1.0, "evidence": []}}
    if domain:
        payload["domain"] = {"value": domain, "confidence": 1.0, "evidence": []}
    return {"payload": payload}


def _contact(email: str, name: str = "Test Person", company_id: str | None = None) -> dict:
    payload: dict = {
        "full_name": {"value": name, "confidence": 1.0, "evidence": []},
        "emails": [
            {"value": email, "type": "work", "is_primary": True, "confidence": 0.9, "evidence": []}
        ],
        "phones": [],
    }
    if company_id:
        payload["company_id"] = company_id
    return {"payload": payload}


@pytest.mark.asyncio
async def test_healthz() -> None:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10) as c:
        r = await c.get("/healthz")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_company_upsert_and_merge(headers: dict[str, str]) -> None:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15) as c:
        r1 = await c.post("/companies", json=_company("ООО Ромашка", "romashka.ru"), headers=headers)
        assert r1.status_code == 201
        assert r1.json()["action"] == "created"
        r2 = await c.post(
            "/companies",
            json=_company("Ромашка", "https://www.romashka.ru"),
            headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
        )
        assert r2.status_code == 201
        assert r2.json()["action"] == "merged"
        assert r2.json()["company"]["id"] == r1.json()["company"]["id"]


@pytest.mark.asyncio
async def test_contact_upsert_and_company_count(headers: dict[str, str]) -> None:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15) as c:
        comp = await c.post("/companies", json=_company("C", "c.ru"), headers=headers)
        cid = comp.json()["company"]["id"]
        ct = await c.post(
            "/contacts",
            json=_contact("a@c.ru", company_id=cid),
            headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
        )
        assert ct.status_code == 201
        assert ct.json()["action"] == "created"
        got = await c.get(f"/companies/{cid}", headers=headers)
        assert got.json()["contacts_count"] == 1


@pytest.mark.asyncio
async def test_contact_blocked_by_stoplist(headers: dict[str, str]) -> None:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15) as c:
        await c.post(
            "/stoplist",
            json={"kind": "email", "value": "blocked@x.com", "reason": "manual"},
            headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
        )
        r = await c.post(
            "/contacts",
            json=_contact("blocked@x.com"),
            headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
        )
        assert r.status_code == 409
        assert r.json()["status"] == "blocked"


@pytest.mark.asyncio
async def test_unsubscribe_adds_to_stoplist(headers: dict[str, str]) -> None:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15) as c:
        ct = await c.post(
            "/contacts",
            json=_contact("unsub@x.com"),
            headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
        )
        cid = ct.json()["contact"]["id"]
        r = await c.post(
            f"/contacts/{cid}/status",
            json={"status": "unsubscribed"},
            headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
        )
        assert r.json()["status"] == "unsubscribed"
        sl = await c.get("/stoplist", headers=headers)
        assert "unsub@x.com" in [e["value"] for e in sl.json()]


@pytest.mark.asyncio
async def test_rls_isolation() -> None:
    ha = {"X-Tenant-ID": str(uuid.uuid4()), "Idempotency-Key": str(uuid.uuid4())}
    hb = {"X-Tenant-ID": str(uuid.uuid4())}
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15) as c:
        comp = await c.post("/companies", json=_company("A", "a-iso.ru"), headers=ha)
        cid = comp.json()["company"]["id"]
        r = await c.get(f"/companies/{cid}", headers=hb)
        assert r.status_code == 404
