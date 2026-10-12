"""Unit tests for the EventRouter."""

from typing import Any
from uuid import UUID

import pytest
from orchestrator.handlers.base import StepHandler
from orchestrator.router import EventRouter

from contracts.base import EventEnvelope


class RecordingHandler(StepHandler):
    event_type = "test.event"
    step_name = "test_step"

    def __init__(self) -> None:
        self.calls = 0

    async def handle(self, envelope: EventEnvelope[Any]) -> None:
        self.calls += 1


class BoomHandler(StepHandler):
    event_type = "test.event"
    step_name = "boom"

    async def handle(self, envelope: EventEnvelope[Any]) -> None:
        raise RuntimeError("boom")


async def _envelope(event_type: str = "test.event") -> EventEnvelope[Any]:
    return EventEnvelope.model_validate(
        {
            "event_type": event_type,
            "tenant_id": str(UUID(int=1)),
            "payload": {},
        }
    )


@pytest.mark.asyncio
async def test_route_dispatches_registered_handler() -> None:
    router = EventRouter()
    h = RecordingHandler()
    router.register(h)
    await router.route(await _envelope())
    assert h.calls == 1


@pytest.mark.asyncio
async def test_route_ignores_unknown_event() -> None:
    router = EventRouter()
    # no exception
    await router.route(await _envelope("unknown.event"))


@pytest.mark.asyncio
async def test_route_isolates_handler_errors() -> None:
    router = EventRouter()
    good = RecordingHandler()
    router.register(BoomHandler())
    router.register(good)
    await router.route(await _envelope())
    assert good.calls == 1
