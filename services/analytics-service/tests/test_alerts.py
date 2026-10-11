"""Unit tests for the alert engine thresholds."""

from typing import Any
from uuid import UUID

import pytest
from analytics_service.alerts.engine import AlertEngine
from analytics_service.config import Settings


class FakeRepo:
    def __init__(self, overview: dict[str, Any]) -> None:
        self._overview = overview

    async def overview(self, **kwargs: Any) -> dict[str, Any]:
        return self._overview


class FakePublisher:
    def __init__(self) -> None:
        self.published: list[dict[str, Any]] = []

    async def publish(
        self, subject: Any, tenant_id: UUID, payload: dict[str, Any], **kw: Any
    ) -> None:
        self.published.append({"subject": str(subject), **payload})


def _settings() -> Settings:
    return Settings(
        SERVICE_NAME="analytics-service",
        DATABASE_URL="postgresql+asyncpg://x:y@localhost/db",
        DATABASE_URL_ADMIN="postgresql+asyncpg://x:y@localhost/db",
        NATS_URL="nats://localhost:4222",
        REDIS_URL="redis://localhost:6379/0",
    )


@pytest.mark.asyncio
async def test_low_reply_rate_alerts() -> None:
    repo = FakeRepo({"sent": 100, "reply_rate": 0.01, "bounce_rate": 0.0})
    pub = FakePublisher()
    engine = AlertEngine(repo, pub, _settings())  # type: ignore[arg-type]
    alerts = await engine.check_all(tenant_id=UUID(int=1))
    assert any(a["type"] == "low_reply_rate" for a in alerts)
    assert any(p["alert_type"] == "low_reply_rate" for p in pub.published)


@pytest.mark.asyncio
async def test_high_bounce_rate_alerts() -> None:
    repo = FakeRepo({"sent": 100, "reply_rate": 0.5, "bounce_rate": 0.2})
    pub = FakePublisher()
    engine = AlertEngine(repo, pub, _settings())  # type: ignore[arg-type]
    alerts = await engine.check_all(tenant_id=UUID(int=2))
    assert any(a["type"] == "high_bounce_rate" for a in alerts)


@pytest.mark.asyncio
async def test_no_alert_on_small_sample() -> None:
    repo = FakeRepo({"sent": 10, "reply_rate": 0.0, "bounce_rate": 0.9})
    pub = FakePublisher()
    engine = AlertEngine(repo, pub, _settings())  # type: ignore[arg-type]
    alerts = await engine.check_all(tenant_id=UUID(int=3))
    assert alerts == []
    assert pub.published == []
