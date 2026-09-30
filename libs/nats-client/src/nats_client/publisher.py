"""Event publisher."""

from typing import Any
from uuid import UUID

from nats.js import JetStreamContext

from contracts.base import EventEnvelope
from contracts.events import payload_model_for
from nats_client.subjects import Subjects


class Publisher:
    """Publishes typed events to NATS JetStream."""

    def __init__(self, js: JetStreamContext, *, producer: str) -> None:
        self._js = js
        self._producer = producer

    async def publish(
        self,
        subject: Subjects,
        tenant_id: UUID,
        payload: dict[str, Any],
        *,
        trace_id: str = "",
        correlation_id: UUID | None = None,
        causation_id: UUID | None = None,
    ) -> None:
        event_type = subject.value
        payload_cls = payload_model_for(event_type)
        envelope_cls = EventEnvelope[payload_cls]  # type: ignore[valid-type]
        envelope = envelope_cls(
            event_type=event_type,
            tenant_id=tenant_id,
            trace_id=trace_id,
            causation_id=causation_id,
            correlation_id=correlation_id,
            producer=self._producer,
            payload=payload_cls.model_validate(payload),
        )

        full_subject = Subjects.full(subject, str(tenant_id))
        await self._js.publish(
            full_subject,
            envelope.model_dump_json().encode(),
            headers={
                "Nats-Msg-Id": str(envelope.event_id),
                "X-Event-Type": envelope.event_type,
                "X-Trace-Id": trace_id,
                "X-Tenant-Id": str(tenant_id),
                "X-Schema-Version": envelope.schema_version,
            },
        )
