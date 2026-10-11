"""Segment-level metrics via direct joins."""

from datetime import UTC, date, datetime, time
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class SegmentMetrics:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def by_segment(
        self, *, tenant_id: UUID, from_date: date, to_date: date
    ) -> list[dict[str, Any]]:
        from_ts = datetime.combine(from_date, time.min, tzinfo=UTC)
        to_ts = datetime.combine(to_date, time.max, tzinfo=UTC)
        sql = """
            SELECT
                (m.personalization->>'segment_id') AS segment_id,
                COUNT(DISTINCT m.contact_id) AS contacted,
                COUNT(DISTINCT m.contact_id) FILTER (
                    WHERE m.status IN ('sent', 'delivered', 'replied', 'closed')
                ) AS sent,
                COUNT(DISTINCT m.contact_id) FILTER (WHERE m.status = 'replied') AS replied,
                COUNT(DISTINCT m.contact_id) FILTER (
                    WHERE EXISTS (
                        SELECT 1 FROM replies r
                        WHERE r.message_id = m.id
                          AND r.category IN ('positive', 'question')
                    )
                ) AS replied_positive
            FROM messages m
            WHERE m.tenant_id = :tid
              AND m.created_at BETWEEN :from_ts AND :to_ts
            GROUP BY 1
            ORDER BY sent DESC
        """
        result = await self._s.execute(
            text(sql),
            {"tid": str(tenant_id), "from_ts": from_ts, "to_ts": to_ts},
        )
        return [dict(r._mapping) for r in result]
