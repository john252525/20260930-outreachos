"""Pull-consumer subscriber."""

import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import nats
from nats.aio.msg import Msg
from nats.js.api import ConsumerConfig, DeliverPolicy
from nats.js.client import JetStreamContext

from contracts.base import EventEnvelope
from contracts.events import parse_event

logger = logging.getLogger(__name__)

Handler = Callable[[EventEnvelope[Any]], Awaitable[None]]


class Subscriber:
    """Pull-based JetStream consumer."""

    def __init__(
        self,
        js: JetStreamContext,
        *,
        stream: str,
        durable: str,
        filter_subjects: list[str],
        handler: Handler,
        batch_size: int = 10,
        fetch_timeout: float = 5.0,
        deliver_policy: DeliverPolicy = DeliverPolicy.ALL,
    ) -> None:
        self._js = js
        self._stream = stream
        self._durable = durable
        self._filter = filter_subjects
        self._handler = handler
        self._batch_size = batch_size
        self._fetch_timeout = fetch_timeout
        self._deliver_policy = deliver_policy
        self._sub: Any = None

    async def start(self) -> None:
        config = ConsumerConfig(
            durable_name=self._durable,
            filter_subjects=self._filter,
            deliver_policy=self._deliver_policy,
            ack_wait=30,
            max_deliver=5,
        )
        subject = self._filter[0] if len(self._filter) == 1 else ">"
        self._sub = await self._js.pull_subscribe(
            subject=subject,
            durable=self._durable,
            stream=self._stream,
            config=config,
        )
        logger.info("Subscribed: stream=%s durable=%s", self._stream, self._durable)

    async def stop(self) -> None:
        if self._sub is not None:
            await self._sub.unsubscribe()
            self._sub = None

    async def run_forever(self) -> None:
        if self._sub is None:
            raise RuntimeError("Subscriber not started. Call start() first.")
        while True:
            try:
                messages = await self._sub.fetch(
                    batch=self._batch_size, timeout=self._fetch_timeout
                )
            except nats.errors.TimeoutError:
                continue
            except nats.errors.ConnectionClosedError:
                logger.warning("NATS connection closed, stopping subscriber")
                return
            for msg in messages:
                await self._process(msg)

    async def _process(self, msg: Msg) -> None:
        headers = msg.headers or {}
        event_type = headers.get("X-Event-Type", "")
        try:
            data = json.loads(msg.data)
            envelope = parse_event(event_type=event_type, data=data)
        except Exception as e:
            logger.exception("Failed to parse event: %s", e)
            await msg.term()
            return

        try:
            await self._handler(envelope)
            await msg.ack()
        except Exception as e:
            logger.exception("Handler failed: %s", e)
            await msg.nak(delay=5)
