"""NATS -> Redis pub/sub bridge."""

from typing import Any

import structlog

from contracts.base import EventEnvelope
from nats_client.client import NATSConnection
from nats_client.subscriber import Subscriber
from realtime_gateway.pubsub import PubSub

logger = structlog.get_logger()

SUBJECTS = [
    "message.drafted.*",
    "message.approved.*",
    "message.sent.*",
    "reply.received.*",
    "flow.started.*",
    "flow.completed.*",
    "flow.failed.*",
    "flow.step_completed.*",
]


class NATSBridge:
    def __init__(self, nats_conn: NATSConnection, pubsub: PubSub, *, durable: str) -> None:
        self._nats = nats_conn
        self._pubsub = pubsub
        self._durable = durable

    async def run_forever(self) -> None:
        async def handler(envelope: EventEnvelope[Any]) -> None:
            message = {
                "type": "event",
                "event_type": envelope.event_type,
                "tenant_id": str(envelope.tenant_id),
                "payload": envelope.payload.model_dump(mode="json"),
                "occurred_at": envelope.occurred_at.isoformat(),
            }
            await self._pubsub.publish(tenant_id=envelope.tenant_id, message=message)

        subscriber = Subscriber(
            self._nats.js,
            stream="BRIEFS",
            durable=self._durable,
            filter_subjects=SUBJECTS,
            handler=handler,
            batch_size=10,
            fetch_timeout=5.0,
        )
        await subscriber.start()
        await subscriber.run_forever()

    async def run_flows(self) -> None:
        """Also bridge the FLOWS stream (flow.* events)."""

        async def handler(envelope: EventEnvelope[Any]) -> None:
            message = {
                "type": "event",
                "event_type": envelope.event_type,
                "tenant_id": str(envelope.tenant_id),
                "payload": envelope.payload.model_dump(mode="json"),
                "occurred_at": envelope.occurred_at.isoformat(),
            }
            await self._pubsub.publish(tenant_id=envelope.tenant_id, message=message)

        subscriber = Subscriber(
            self._nats.js,
            stream="FLOWS",
            durable=f"{self._durable}-flows",
            filter_subjects=["flow.>"],
            handler=handler,
            batch_size=10,
            fetch_timeout=5.0,
        )
        await subscriber.start()
        await subscriber.run_forever()
