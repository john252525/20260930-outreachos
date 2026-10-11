"""Reply-centric metrics."""

from datetime import UTC, date, datetime, time
from typing import Any
from uuid import UUID

from sqlalchemy import String, bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession


class ReplyMetrics:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def category_breakdown(
        self, *, tenant_id: UUID, from_date: date, to_date: date
    ) -> list[dict[str, Any]]:
        sql = """
            SELECT category,
                   SUM(reply_count) AS count,
                   AVG(avg_confidence) AS confidence
            FROM analytics.mv_daily_reply_metrics
            WHERE tenant_id = :tid AND day BETWEEN :from_date AND :to_date
            GROUP BY 1
            ORDER BY count DESC
        """
        result = await self._s.execute(
            text(sql),
            {"tid": str(tenant_id), "from_date": from_date, "to_date": to_date},
        )
        return [dict(r._mapping) for r in result]

    async def positive_reply_rate(
        self,
        *,
        tenant_id: UUID,
        from_date: date,
        to_date: date,
        template_id: str | None = None,
    ) -> dict[str, Any]:
        from_ts = datetime.combine(from_date, time.min, tzinfo=UTC)
        to_ts = datetime.combine(to_date, time.max, tzinfo=UTC)
        sql = """
            WITH sent AS (
                SELECT DISTINCT m.contact_id
                FROM messages m
                WHERE m.tenant_id = :tid
                  AND m.status IN ('sent', 'delivered', 'replied', 'closed')
                  AND m.sent_at BETWEEN :from_ts AND :to_ts
                  AND (:template_id IS NULL OR m.personalization->>'template_id' = :template_id)
            ),
            positive AS (
                SELECT DISTINCT r.contact_id
                FROM replies r
                WHERE r.tenant_id = :tid
                  AND r.category IN ('positive', 'question')
                  AND r.received_at BETWEEN :from_ts AND :to_ts
            )
            SELECT
                (SELECT COUNT(*) FROM sent) AS sent_count,
                (SELECT COUNT(*) FROM positive) AS positive_count
        """
        stmt = text(sql).bindparams(bindparam("template_id", type_=String))
        row = (
            await self._s.execute(
                stmt,
                {
                    "tid": str(tenant_id),
                    "from_ts": from_ts,
                    "to_ts": to_ts,
                    "template_id": template_id,
                },
            )
        ).one()
        d = dict(row._mapping)
        sent = int(d["sent_count"] or 0)
        positive = int(d["positive_count"] or 0)
        return {
            "sent_count": sent,
            "positive_count": positive,
            "positive_reply_rate": (positive / sent) if sent else 0.0,
        }

    async def funnel(self, *, tenant_id: UUID) -> dict[str, Any]:
        sql = "SELECT * FROM analytics.mv_funnel WHERE tenant_id = :tid"
        row = (await self._s.execute(text(sql), {"tid": str(tenant_id)})).one_or_none()
        if row is None:
            return {
                "contacted": 0,
                "sent": 0,
                "replied": 0,
                "replied_positive": 0,
                "bounced": 0,
                "closed": 0,
                "approved": 0,
                "draft": 0,
            }
        d = dict(row._mapping)
        d.pop("tenant_id", None)
        positive_sql = """
            SELECT COUNT(DISTINCT m.contact_id) AS replied_positive
            FROM messages m
            WHERE m.tenant_id = :tid
              AND EXISTS (
                  SELECT 1 FROM replies r
                  WHERE r.message_id = m.id
                    AND r.category IN ('positive', 'question')
              )
        """
        prow = (await self._s.execute(text(positive_sql), {"tid": str(tenant_id)})).one()
        d["replied_positive"] = int(dict(prow._mapping)["replied_positive"] or 0)
        return d
