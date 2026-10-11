"""Experiment variant metrics (source: messages.experiment + replies)."""

from typing import Any
from uuid import UUID

from sqlalchemy import String, bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession


class ExperimentMetrics:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def variant_stats(self, *, tenant_id: UUID, experiment_id: UUID) -> list[dict[str, Any]]:
        sql = """
            SELECT
                m.experiment->>'variant_id' AS variant_id,
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
                ) AS positive_replied
            FROM messages m
            WHERE m.tenant_id = :tid
              AND m.experiment->>'experiment_id' = :exp
            GROUP BY 1
        """
        stmt = text(sql).bindparams(bindparam("exp", type_=String))
        result = await self._s.execute(stmt, {"tid": str(tenant_id), "exp": str(experiment_id)})
        return [dict(r._mapping) for r in result]
