"""Sender and sourcing metrics."""

from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class SenderMetrics:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

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


class SourcingMetrics:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def summary(self, *, tenant_id: UUID, from_date: date, to_date: date) -> dict[str, Any]:
        sql = """
            SELECT
                COALESCE(SUM(jobs_count), 0) AS jobs,
                COALESCE(SUM(raw_count), 0) AS raw,
                COALESCE(SUM(normalized_count), 0) AS normalized,
                COALESCE(SUM(persisted_count), 0) AS persisted,
                COALESCE(SUM(companies_created), 0) AS companies_created,
                COALESCE(SUM(contacts_created), 0) AS contacts_created,
                COALESCE(SUM(total_cost_usd), 0) AS total_cost_usd,
                AVG(avg_duration_ms) AS avg_duration_ms
            FROM analytics.mv_daily_sourcing_metrics
            WHERE tenant_id = :tid AND day BETWEEN :from_date AND :to_date
        """
        row = (
            await self._s.execute(
                text(sql),
                {"tid": str(tenant_id), "from_date": from_date, "to_date": to_date},
            )
        ).one()
        d = dict(row._mapping)
        return {
            "jobs": int(d["jobs"] or 0),
            "raw": int(d["raw"] or 0),
            "normalized": int(d["normalized"] or 0),
            "persisted": int(d["persisted"] or 0),
            "companies_created": int(d["companies_created"] or 0),
            "contacts_created": int(d["contacts_created"] or 0),
            "total_cost_usd": float(d["total_cost_usd"] or 0.0),
            "avg_duration_ms": float(d["avg_duration_ms"]) if d["avg_duration_ms"] else 0.0,
        }
