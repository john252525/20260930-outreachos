"""Aggregate repository exposing all metric views.

All methods take an explicit ``tenant_id`` — this service reads through the
owner DSN (see ADR-017), so tenant isolation is enforced in the query itself.
"""

from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from analytics_service.metrics.experiment_metrics import ExperimentMetrics
from analytics_service.metrics.message_metrics import MessageMetrics
from analytics_service.metrics.reply_metrics import ReplyMetrics
from analytics_service.metrics.segments import SegmentMetrics
from analytics_service.metrics.sender_metrics import SenderMetrics, SourcingMetrics


class MetricsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session
        self.messages = MessageMetrics(session)
        self.replies = ReplyMetrics(session)
        self.senders = SenderMetrics(session)
        self.sourcing = SourcingMetrics(session)
        self.segments = SegmentMetrics(session)
        self.experiments = ExperimentMetrics(session)

    @property
    def session(self) -> AsyncSession:
        return self._s

    async def overview(self, *, tenant_id: UUID, from_date: date, to_date: date) -> dict[str, Any]:
        msg = await self.messages.overview(
            tenant_id=tenant_id, from_date=from_date, to_date=to_date
        )
        pos = await self.replies.positive_reply_rate(
            tenant_id=tenant_id, from_date=from_date, to_date=to_date
        )
        return {**msg, **pos}
