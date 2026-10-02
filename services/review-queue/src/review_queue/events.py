"""Event emission helpers for review-queue."""

from typing import Any

from nats_client.publisher import Publisher
from nats_client.subjects import Subjects
from review_queue.models import ReviewItem


async def emit_message_approved(
    publisher: Publisher, item: ReviewItem, message: dict[str, Any], *, trace_id: str
) -> None:
    await publisher.publish(
        Subjects.MESSAGE_APPROVED,
        tenant_id=item.tenant_id,
        payload={
            "message_id": str(item.message_id),
            "approved_by": item.reviewed_by or "unknown",
            "edited": item.edit is not None,
        },
        trace_id=trace_id,
        correlation_id=item.message_id,
    )


async def emit_message_rejected(publisher: Publisher, item: ReviewItem, *, trace_id: str) -> None:
    await publisher.publish(
        Subjects.MESSAGE_REJECTED,
        tenant_id=item.tenant_id,
        payload={
            "message_id": str(item.message_id),
            "rejected_by": item.reviewed_by or "unknown",
            "reason": (item.rejection or {}).get("reason", ""),
        },
        trace_id=trace_id,
        correlation_id=item.message_id,
    )
