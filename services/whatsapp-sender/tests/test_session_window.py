"""Unit tests for the 24h session window."""

from datetime import UTC, datetime, timedelta

import pytest
from whatsapp_sender.session_window import SessionWindowChecker


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self.store[key] = value


@pytest.mark.asyncio
async def test_window_closed_initially() -> None:
    r = FakeRedis()
    w = SessionWindowChecker(r, window_hours=24)
    assert await w.is_open(tenant_id="t", phone="+7") is False


@pytest.mark.asyncio
async def test_window_open_after_inbound() -> None:
    r = FakeRedis()
    w = SessionWindowChecker(r, window_hours=24)
    await w.mark_inbound(tenant_id="t", phone="+7")
    assert await w.is_open(tenant_id="t", phone="+7") is True


@pytest.mark.asyncio
async def test_window_expired() -> None:
    r = FakeRedis()
    w = SessionWindowChecker(r, window_hours=24)
    old = datetime.now(UTC) - timedelta(hours=30)
    r.store["wa:window:t:+7"] = old.isoformat()
    assert await w.is_open(tenant_id="t", phone="+7") is False
