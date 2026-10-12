"""Background worker retrying scheduled flow steps via the router."""

import asyncio
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import text

from contracts.base import EventEnvelope
from contracts.events import parse_event
from db.rls import set_tenant_context
from db.session import async_session_factory
from orchestrator.config import Settings
from orchestrator.db_admin import admin_session_factory
from orchestrator.metrics import FLOW_STEP_RETRIES
from orchestrator.repository import FlowRepository
from orchestrator.router import EventRouter

logger = structlog.get_logger()

TENANT_LIST_QUERY = text("SELECT id FROM tenants WHERE status <> 'deleted'")


class RetryWorker:
    def __init__(self, router: EventRouter, settings: Settings) -> None:
        self._router = router
        self._settings = settings
        self._stopped = False

    async def run_forever(self) -> None:
        while not self._stopped:
            try:
                await self.process_retries()
            except Exception as e:
                logger.exception("retry_worker_failed", error=str(e))
            await asyncio.sleep(self._settings.retry_poll_interval_seconds)

    async def process_retries(self) -> int:
        now = datetime.now(UTC)
        processed = 0
        admin_factory = admin_session_factory()
        async with admin_factory() as admin_session:
            rows = (await admin_session.execute(TENANT_LIST_QUERY)).all()
        for r in rows:
            tenant_id = UUID(str(r[0]))
            processed += await self._retry_for_tenant(tenant_id, now=now)
        return processed

    async def _retry_for_tenant(self, tenant_id: UUID, *, now: datetime) -> int:
        count = 0
        async with async_session_factory() as session, session.begin():
            await set_tenant_context(session, tenant_id)
            repo = FlowRepository(session)
            steps = await repo.due_retries(tenant_id, now=now, limit=10)
            retry_specs: list[dict[str, Any]] = []
            for step in steps:
                step.status = "running"
                step.attempts += 1
                retry_specs.append(
                    {
                        "step_id": step.id,
                        "event_type": step.input_data.get("original_event_type"),
                        "event_payload": step.input_data.get("original_event_payload"),
                        "trace_id": f"retry-{step.id}",
                    }
                )
            await session.flush()

        for spec in retry_specs:
            if not spec["event_type"] or spec["event_payload"] is None:
                await self._mark_failed(
                    tenant_id, spec["step_id"], "No original event data for retry"
                )
                continue
            envelope: EventEnvelope[Any] = parse_event(
                event_type=str(spec["event_type"]),
                data={
                    "event_type": spec["event_type"],
                    "tenant_id": str(tenant_id),
                    "trace_id": spec["trace_id"],
                    "producer": "orchestrator/retry-worker",
                    "payload": spec["event_payload"],
                },
            )
            FLOW_STEP_RETRIES.labels(step_name=spec["event_type"]).inc()
            try:
                await self._router.route(envelope)
                count += 1
            except Exception as e:
                logger.exception("retry_route_failed", step_id=str(spec["step_id"]), error=str(e))
        return count

    async def _mark_failed(self, tenant_id: UUID, step_id: UUID, error: str) -> None:
        async with async_session_factory() as session, session.begin():
            await set_tenant_context(session, tenant_id)
            await session.execute(
                text("UPDATE flow_steps SET status='failed', error=:e WHERE id=:id"),
                {"e": error, "id": str(step_id)},
            )

    def stop(self) -> None:
        self._stopped = True
