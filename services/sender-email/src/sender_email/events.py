"""Event emission helpers for sender-email."""

from datetime import datetime
from uuid import UUID

from nats_client.publisher import Publisher
from nats_client.subjects import Subjects
from sender_email.models import SendAttempt


async def emit_message_sent(
    publisher: Publisher,
    *,
    tenant_id: UUID,
    message_id: UUID,
    channel: str,
    sender: str,
    provider_message_id: str | None,
    trace_id: str,
) -> None:
    await publisher.publish(
        Subjects.MESSAGE_SENT,
        tenant_id=tenant_id,
        payload={
            "message_id": str(message_id),
            "channel": channel,
            "sender": sender,
            "provider_message_id": provider_message_id,
        },
        trace_id=trace_id,
        correlation_id=message_id,
    )


async def emit_message_bounced(
    publisher: Publisher,
    *,
    tenant_id: UUID,
    message_id: UUID,
    bounce_type: str,
    bounce_reason: str,
    trace_id: str,
) -> None:
    await publisher.publish(
        Subjects.MESSAGE_BOUNCED,
        tenant_id=tenant_id,
        payload={
            "message_id": str(message_id),
            "bounce_type": bounce_type,
            "reason": bounce_reason,
        },
        trace_id=trace_id,
        correlation_id=message_id,
    )


async def emit_reply_received(
    publisher: Publisher,
    *,
    tenant_id: UUID,
    message_id: UUID,
    contact_id: UUID,
    channel: str,
    trace_id: str,
    from_email: str = "",
    from_name: str | None = None,
    subject: str | None = None,
    body: str = "",
    received_at: datetime | None = None,
    in_reply_to: str | None = None,
    references: str | None = None,
    message_id_header: str | None = None,
) -> None:
    reply_id = message_id
    await publisher.publish(
        Subjects.REPLY_RECEIVED,
        tenant_id=tenant_id,
        payload={
            "reply": {
                "id": str(reply_id),
                "message_id": str(message_id),
                "contact_id": str(contact_id),
                "channel": channel,
                "from_email": from_email,
                "from_name": from_name,
                "subject": subject,
                "body": body[:10_000],
                "received_at": received_at.isoformat() if received_at else None,
                "in_reply_to": in_reply_to,
                "references": references,
                "message_id_header": message_id_header,
            }
        },
        trace_id=trace_id,
        correlation_id=message_id,
    )


def attempt_summary(attempt: SendAttempt) -> dict[str, str | None]:
    return {"status": attempt.status, "smtp_message_id": attempt.smtp_message_id}
