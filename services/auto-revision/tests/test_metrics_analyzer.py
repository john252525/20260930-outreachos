"""Unit tests for the metrics analyzer (with a fake analytics client)."""

from typing import Any
from uuid import UUID

import pytest
from auto_revision.analysis.metrics_analyzer import MetricsAnalyzer
from auto_revision.config import Settings


class FakeAnalytics:
    def __init__(self) -> None:
        self.overview = {
            "sent": 100,
            "replied": 5,
            "positive_count": 2,
            "bounced": 1,
            "failed": 0,
            "reply_rate": 0.05,
            "positive_reply_rate": 0.02,
            "bounce_rate": 0.01,
        }
        self.by_template = [
            {"template_id": "email_cold_outreach", "sent": 60, "reply_rate": 0.01},
            {"template_id": "email_followup", "sent": 40, "reply_rate": 0.1},
        ]
        self.categories = [{"category": "positive", "count": 2}]
        self.segments = [
            {"segment_id": "s1", "sent": 50, "replied_positive": 3},
            {"segment_id": "s2", "sent": 50, "replied_positive": 0},
        ]

    async def get_overview(self, **kw: Any) -> dict[str, Any]:
        return self.overview

    async def get_by_template(self, **kw: Any) -> list[dict[str, Any]]:
        return self.by_template

    async def get_reply_categories(self, **kw: Any) -> list[dict[str, Any]]:
        return self.categories

    async def get_segments(self, **kw: Any) -> list[dict[str, Any]]:
        return self.segments


def _settings() -> Settings:
    return Settings(
        SERVICE_NAME="auto-revision",
        DATABASE_URL="postgresql+asyncpg://x:y@localhost/db",
        NATS_URL="nats://localhost:4222",
        REDIS_URL="redis://localhost:6379/0",
    )


@pytest.mark.asyncio
async def test_analyze_snapshot() -> None:
    analyzer = MetricsAnalyzer(FakeAnalytics(), _settings())  # type: ignore[arg-type]
    snap = await analyzer.analyze(tenant_id=UUID(int=1))
    assert snap.sent == 100
    assert snap.reply_rate == 0.05
    assert snap.worst_segment_id == "s2"
    assert snap.best_segment_id == "s1"


def test_find_worst_template() -> None:
    analyzer = MetricsAnalyzer(FakeAnalytics(), _settings())  # type: ignore[arg-type]
    from auto_revision.analysis.metrics_analyzer import MetricsSnapshot

    snap = MetricsSnapshot(by_template=FakeAnalytics().by_template)
    assert analyzer.find_worst_template(snap) == "email_cold_outreach"


def test_find_worst_template_empty() -> None:
    analyzer = MetricsAnalyzer(FakeAnalytics(), _settings())  # type: ignore[arg-type]
    from auto_revision.analysis.metrics_analyzer import MetricsSnapshot

    assert analyzer.find_worst_template(MetricsSnapshot()) is None
