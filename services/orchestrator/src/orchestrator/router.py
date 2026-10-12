"""Event router dispatching NATS events to handlers."""

from typing import Any

import structlog

from contracts.base import EventEnvelope
from orchestrator.handlers.base import StepHandler

logger = structlog.get_logger()


class EventRouter:
    """Dispatches events to registered handlers by ``event_type``."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[StepHandler]] = {}

    def register(self, handler: StepHandler) -> None:
        self._handlers.setdefault(handler.event_type, []).append(handler)

    async def route(self, envelope: EventEnvelope[Any]) -> None:
        handlers = self._handlers.get(envelope.event_type, [])
        if not handlers:
            logger.debug("no_handlers_for_event", event_type=envelope.event_type)
            return
        for h in handlers:
            try:
                await h.handle(envelope)
            except Exception as e:
                logger.exception(
                    "handler_failed",
                    event_type=envelope.event_type,
                    handler=h.__class__.__name__,
                    error=str(e),
                )
