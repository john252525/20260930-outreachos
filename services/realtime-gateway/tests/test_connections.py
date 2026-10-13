"""Unit tests for the WebSocket connection manager."""

from uuid import uuid4

import pytest
from realtime_gateway.connections import ClientConnection, ConnectionManager


class FakeWS:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_json(self, msg: dict) -> None:
        self.sent.append(msg)


@pytest.mark.asyncio
async def test_broadcast_to_tenant() -> None:
    mgr = ConnectionManager()
    tenant = uuid4()
    ws = FakeWS()
    conn = ClientConnection(user_id=uuid4(), tenant_id=tenant, websocket=ws)
    await mgr.connect(conn, uuid4())
    await mgr.broadcast_to_tenant(tenant, {"type": "event"})
    assert ws.sent == [{"type": "event"}]


@pytest.mark.asyncio
async def test_broadcast_isolated_by_tenant() -> None:
    mgr = ConnectionManager()
    t1, t2 = uuid4(), uuid4()
    ws1, ws2 = FakeWS(), FakeWS()
    await mgr.connect(ClientConnection(user_id=uuid4(), tenant_id=t1, websocket=ws1), uuid4())
    await mgr.connect(ClientConnection(user_id=uuid4(), tenant_id=t2, websocket=ws2), uuid4())
    await mgr.broadcast_to_tenant(t1, {"x": 1})
    assert len(ws1.sent) == 1
    assert len(ws2.sent) == 0


@pytest.mark.asyncio
async def test_disconnect() -> None:
    mgr = ConnectionManager()
    tenant = uuid4()
    cid = uuid4()
    await mgr.connect(ClientConnection(user_id=uuid4(), tenant_id=tenant, websocket=FakeWS()), cid)
    await mgr.disconnect(cid)
    assert mgr.tenant_count() == 0
