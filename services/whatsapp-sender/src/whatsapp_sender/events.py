"""Event emission helpers for whatsapp-sender."""

from uuid import UUID

from nats_client.publisher import Publisher
from nats_client.subjects import Subjects


async def emit_message_sent(
    publisher: Publisher,
    *,
    tenant_id: UUID,
    message_id: UUID,
    sender: str,
    provider_message_id: str | None,
    trace_id: str,
) -> None:
    await publisher.publish(
        Subjects.MESSAGE_SENT,
        tenant_id=tenant_id,
        payload={
            "message_id": str(message_id),
            "channel": "whatsapp",
            "sender": sender,
            "provider_message_id": provider_message_id,
        },
        trace_id=trace_id,
        correlation_id=message_id,
    )


async def emit_message_failed(
    publisher: Publisher, *, tenant_id: UUID, message_id: UUID, reason: str, trace_id: str
) -> None:
    await publisher.publish(
        Subjects.MESSAGE_FAILED,
        tenant_id=tenant_id,
        payload={"message_id": str(message_id), "reason": reason},
        trace_id=trace_id,
        correlation_id=message_id,
    )
