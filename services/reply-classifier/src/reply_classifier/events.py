"""Event emission helpers for reply-classifier."""

from nats_client.publisher import Publisher
from nats_client.subjects import Subjects
from reply_classifier.models import Reply


async def emit_reply_classified(publisher: Publisher, reply: Reply, *, trace_id: str) -> None:
    await publisher.publish(
        Subjects.REPLY_CLASSIFIED,
        tenant_id=reply.tenant_id,
        payload={
            "reply_id": str(reply.id),
            "category": reply.category or "unknown",
            "confidence": reply.classification_confidence or 0.0,
        },
        trace_id=trace_id,
        correlation_id=reply.message_id,
    )
