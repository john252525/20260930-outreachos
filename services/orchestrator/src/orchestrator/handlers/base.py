"""Base interfaces for orchestrator step handlers."""

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from contracts.base import EventEnvelope
from orchestrator.models import Flow, FlowStep
from orchestrator.repository import FlowRepository


class StepHandler(ABC):
    """Base interface for an event handler."""

    event_type: str
    step_name: str

    @abstractmethod
    async def handle(self, envelope: EventEnvelope[Any]) -> None:
        """Process an event, possibly creating FlowStep and calling services."""
        ...


def start_step(
    *,
    tenant_id: UUID,
    flow_id: UUID,
    step_name: str,
    input_data: dict[str, Any],
    max_attempts: int,
) -> FlowStep:
    return FlowStep(
        tenant_id=tenant_id,
        flow_id=flow_id,
        step_name=step_name,
        status="running",
        input_data=input_data,
        started_at=datetime.now(UTC),
        max_attempts=max_attempts,
    )


def complete_step(step: FlowStep, *, output_data: dict[str, Any]) -> None:
    step.status = "completed"
    step.output_data = output_data
    step.finished_at = datetime.now(UTC)
    if step.started_at is not None:
        step.duration_ms = int((step.finished_at - step.started_at).total_seconds() * 1000)


def schedule_retry(step: FlowStep, *, error: str, delay_seconds: int) -> None:
    from datetime import timedelta

    step.status = "retry_scheduled"
    step.error = error
    step.next_retry_at = datetime.now(UTC) + timedelta(seconds=delay_seconds * (2**step.attempts))


async def find_running_flow(repo: FlowRepository, tenant_id: UUID, flow_id: UUID) -> Flow | None:
    flow = await repo.get(flow_id)
    if flow is None or flow.status not in ("running", "paused"):
        return None
    return flow
