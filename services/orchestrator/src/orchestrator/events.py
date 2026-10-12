"""Event emission helpers for orchestrator."""

from nats_client.publisher import Publisher
from nats_client.subjects import Subjects
from orchestrator.models import Flow, FlowStep


async def emit_flow_started(publisher: Publisher, flow: Flow, *, trace_id: str) -> None:
    await publisher.publish(
        Subjects.FLOW_STARTED,
        tenant_id=flow.tenant_id,
        payload={"flow": {"id": str(flow.id), "type": flow.flow_type, "brief_id": flow.brief_id}},
        trace_id=trace_id,
        correlation_id=flow.id,
    )


async def emit_flow_step_completed(
    publisher: Publisher, flow: Flow, step: FlowStep, *, trace_id: str
) -> None:
    await publisher.publish(
        Subjects.FLOW_STEP_COMPLETED,
        tenant_id=flow.tenant_id,
        payload={
            "flow_id": str(flow.id),
            "step_name": step.step_name,
            "duration_ms": step.duration_ms,
        },
        trace_id=trace_id,
        correlation_id=flow.id,
    )


async def emit_flow_completed(publisher: Publisher, flow: Flow, *, trace_id: str) -> None:
    await publisher.publish(
        Subjects.FLOW_COMPLETED,
        tenant_id=flow.tenant_id,
        payload={"flow": {"id": str(flow.id), "type": flow.flow_type, "brief_id": flow.brief_id}},
        trace_id=trace_id,
        correlation_id=flow.id,
    )


async def emit_flow_failed(
    publisher: Publisher, flow: Flow, step: FlowStep, *, trace_id: str
) -> None:
    await publisher.publish(
        Subjects.FLOW_FAILED,
        tenant_id=flow.tenant_id,
        payload={
            "flow_id": str(flow.id),
            "step_name": step.step_name,
            "error": step.error or "",
        },
        trace_id=trace_id,
        correlation_id=flow.id,
    )
