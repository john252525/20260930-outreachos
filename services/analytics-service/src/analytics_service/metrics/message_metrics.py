"""Message-centric metrics read from materialized views."""

from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class MessageMetrics:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def daily(
        self,
        *,
        tenant_id: UUID,
        from_date: date,
        to_date: date,
        channel: str | None = None,
        template_id: str | None = None,
    ) -> list[dict[str, Any]]:
        sql = """
            SELECT day, channel, template_id, template_version,
                   sent_count, bounced_count, failed_count,
                   replied_count, approved_count, draft_count, rejected_count,
                   avg_word_count
            FROM analytics.mv_daily_message_metrics
            WHERE tenant_id = :tid
              AND day BETWEEN :from_date AND :to_date
              AND (:channel IS NULL OR channel = :channel)
              AND (:template_id IS NULL OR template_id = :template_id)
            ORDER BY day DESC, channel
        """
        result = await self._s.execute(
            text(sql),
            {
                "tid": str(tenant_id),
                "from_date": from_date,
                "to_date": to_date,
                "channel": channel,
                "template_id": template_id,
            },
        )
        return [dict(r._mapping) for r in result]

    async def by_template(
        self, *, tenant_id: UUID, from_date: date, to_date: date
    ) -> list[dict[str, Any]]:
        sql = """
            SELECT
                template_id,
                template_version,
                SUM(sent_count) AS sent,
                SUM(replied_count) AS replied,
                SUM(bounced_count) AS bounced,
                SUM(failed_count) AS failed,
                CASE WHEN SUM(sent_count) > 0
                     THEN SUM(replied_count)::float / SUM(sent_count)
                     ELSE 0 END AS reply_rate,
                CASE WHEN SUM(sent_count) > 0
                     THEN SUM(bounced_count)::float / SUM(sent_count)
                     ELSE 0 END AS bounce_rate
            FROM analytics.mv_daily_message_metrics
            WHERE tenant_id = :tid AND day BETWEEN :from_date AND :to_date
            GROUP BY 1, 2
            HAVING SUM(sent_count) > 0
            ORDER BY reply_rate DESC
        """
        result = await self._s.execute(
            text(sql),
            {"tid": str(tenant_id), "from_date": from_date, "to_date": to_date},
        )
        return [dict(r._mapping) for r in result]

    async def by_sender(
        self, *, tenant_id: UUID, from_date: date, to_date: date
    ) -> list[dict[str, Any]]:
        sql = """
            SELECT
                sender_email,
                SUM(sent_count) AS sent,
                SUM(bounced_count) AS bounced,
                SUM(failed_count) AS failed,
                CASE WHEN SUM(sent_count) > 0
                     THEN SUM(bounced_count)::float / SUM(sent_count)
                     ELSE 0 END AS bounce_rate
            FROM analytics.mv_daily_sender_metrics
            WHERE tenant_id = :tid AND day BETWEEN :from_date AND :to_date
            GROUP BY 1
            HAVING SUM(sent_count) > 0
            ORDER BY sent DESC
        """
        result = await self._s.execute(
            text(sql),
            {"tid": str(tenant_id), "from_date": from_date, "to_date": to_date},
        )
        return [dict(r._mapping) for r in result]

    async def overview(self, *, tenant_id: UUID, from_date: date, to_date: date) -> dict[str, Any]:
        sql = """
            SELECT
                COALESCE(SUM(sent_count), 0) AS sent,
                COALESCE(SUM(replied_count), 0) AS replied,
                COALESCE(SUM(bounced_count), 0) AS bounced,
                COALESCE(SUM(failed_count), 0) AS failed,
                COALESCE(SUM(approved_count), 0) AS approved,
                COALESCE(SUM(draft_count), 0) AS draft
            FROM analytics.mv_daily_message_metrics
            WHERE tenant_id = :tid AND day BETWEEN :from_date AND :to_date
        """
        row = (
            await self._s.execute(
                text(sql),
                {"tid": str(tenant_id), "from_date": from_date, "to_date": to_date},
            )
        ).one()
        d = dict(row._mapping)
        sent = int(d["sent"] or 0)
        replied = int(d["replied"] or 0)
        bounced = int(d["bounced"] or 0)
        return {
            "sent": sent,
            "replied": replied,
            "bounced": bounced,
            "failed": int(d["failed"] or 0),
            "approved": int(d["approved"] or 0),
            "draft": int(d["draft"] or 0),
            "reply_rate": (replied / sent) if sent else 0.0,
            "bounce_rate": (bounced / sent) if sent else 0.0,
        }
