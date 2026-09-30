"""Event emission helpers for brief-service."""

from typing import Any

from brief_service.models import Brief
from nats_client.publisher import Publisher
from nats_client.subjects import Subjects


async def emit_brief_created(publisher: Publisher, brief: Brief, *, trace_id: str) -> None:
    await publisher.publish(
        Subjects.BRIEF_CREATED,
        tenant_id=brief.tenant_id,
        payload={
            "brief": {
                "id": str(brief.id),
                "status": brief.status,
                "completeness_score": brief.completeness_score,
            }
        },
        trace_id=trace_id,
        correlation_id=brief.id,
    )


async def emit_brief_questions_asked(
    publisher: Publisher, brief: Brief, *, questions: list[dict[str, Any]], trace_id: str
) -> None:
    await publisher.publish(
        Subjects.BRIEF_QUESTIONS_ASKED,
        tenant_id=brief.tenant_id,
        payload={
            "brief_id": str(brief.id),
            "questions": [
                {"question": q["question"], "priority": q.get("priority", "medium")}
                for q in questions
            ],
        },
        trace_id=trace_id,
        correlation_id=brief.id,
    )


async def emit_brief_completed(publisher: Publisher, brief: Brief, *, trace_id: str) -> None:
    await publisher.publish(
        Subjects.BRIEF_COMPLETED,
        tenant_id=brief.tenant_id,
        payload={"brief": {"id": str(brief.id), "completeness_score": brief.completeness_score}},
        trace_id=trace_id,
        correlation_id=brief.id,
    )


async def emit_brief_updated(publisher: Publisher, brief: Brief, *, trace_id: str) -> None:
    await publisher.publish(
        Subjects.BRIEF_UPDATED,
        tenant_id=brief.tenant_id,
        payload={
            "brief": {
                "id": str(brief.id),
                "status": brief.status,
                "completeness_score": brief.completeness_score,
            }
        },
        trace_id=trace_id,
        correlation_id=brief.id,
    )
