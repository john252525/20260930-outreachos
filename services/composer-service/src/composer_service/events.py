"""Event emission helpers for composer-service."""

from composer_service.models import Message
from nats_client.publisher import Publisher
from nats_client.subjects import Subjects


async def emit_message_drafted(publisher: Publisher, message: Message, *, trace_id: str) -> None:
    await publisher.publish(
        Subjects.MESSAGE_DRAFTED,
        tenant_id=message.tenant_id,
        payload={
            "message": {
                "id": str(message.id),
                "contact_id": str(message.contact_id),
                "channel": message.channel,
                "template_id": (message.personalization or {}).get("template_id", ""),
            }
        },
        trace_id=trace_id,
        correlation_id=message.id,
    )
