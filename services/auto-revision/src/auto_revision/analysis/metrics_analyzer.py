"""Collects metrics from analytics-service and detects problem zones."""

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any
from uuid import UUID

import structlog

from auto_revision.clients.analytics_client import AnalyticsClient
from auto_revision.config import Settings

logger = structlog.get_logger()


@dataclass
class MetricsSnapshot:
    sent: int = 0
    replied: int = 0
    positive_replied: int = 0
    bounced: int = 0
    failed: int = 0
    reply_rate: float = 0.0
    positive_reply_rate: float = 0.0
    bounce_rate: float = 0.0
    by_template: list[dict[str, Any]] = field(default_factory=list)
    by_segment: list[dict[str, Any]] = field(default_factory=list)
    reply_categories: list[dict[str, Any]] = field(default_factory=list)
    best_segment_id: str | None = None
    worst_segment_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "sent": self.sent,
            "replied": self.replied,
            "positive_replied": self.positive_replied,
            "bounced": self.bounced,
            "failed": self.failed,
            "reply_rate": self.reply_rate,
            "positive_reply_rate": self.positive_reply_rate,
            "bounce_rate": self.bounce_rate,
            "by_template": self.by_template,
            "by_segment": self.by_segment,
            "reply_categories": self.reply_categories,
        }


class MetricsAnalyzer:
    def __init__(self, analytics: AnalyticsClient, settings: Settings) -> None:
        self._analytics = analytics
        self._settings = settings

    async def analyze(
        self,
        *,
        tenant_id: UUID,
        window_days: int | None = None,
    ) -> MetricsSnapshot:
        days = window_days or self._settings.analysis_window_days
        to_date = date.today()
        from_date = to_date - timedelta(days=days)
        tid = str(tenant_id)

        overview = await self._analytics.get_overview(
            tenant_id=tid, from_date=from_date.isoformat(), to_date=to_date.isoformat()
        )
        by_template = await self._analytics.get_by_template(
            tenant_id=tid, from_date=from_date.isoformat(), to_date=to_date.isoformat()
        )
        categories = await self._analytics.get_reply_categories(
            tenant_id=tid, from_date=from_date.isoformat(), to_date=to_date.isoformat()
        )
        segments = await self._analytics.get_segments(
            tenant_id=tid, from_date=from_date.isoformat(), to_date=to_date.isoformat()
        )

        best_segment = None
        worst_segment = None
        scored = [s for s in segments if (s.get("sent") or 0) > 0]
        if scored:
            scored.sort(
                key=lambda s: (s.get("replied_positive", 0) or 0) / max(s.get("sent", 1), 1),
                reverse=True,
            )
            best_segment = scored[0].get("segment_id")
            worst_segment = scored[-1].get("segment_id")

        return MetricsSnapshot(
            sent=int(overview.get("sent", 0)),
            replied=int(overview.get("replied", 0)),
            positive_replied=int(overview.get("positive_count", 0)),
            bounced=int(overview.get("bounced", 0)),
            failed=int(overview.get("failed", 0)),
            reply_rate=float(overview.get("reply_rate", 0.0)),
            positive_reply_rate=float(overview.get("positive_reply_rate", 0.0)),
            bounce_rate=float(overview.get("bounce_rate", 0.0)),
            by_template=by_template,
            by_segment=segments,
            reply_categories=categories,
            best_segment_id=best_segment,
            worst_segment_id=worst_segment,
        )

    def find_worst_template(self, metrics: MetricsSnapshot) -> str | None:
        candidates = [t for t in metrics.by_template if (t.get("sent") or 0) > 0]
        if not candidates:
            return None
        candidates.sort(key=lambda t: t.get("reply_rate", 0.0))
        return str(candidates[0].get("template_id") or "") or None
