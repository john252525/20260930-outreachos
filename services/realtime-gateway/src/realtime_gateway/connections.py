"""WebSocket connection manager."""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

import structlog

logger = structlog.get_logger()


@dataclass
class ClientConnection:
    user_id: UUID
    tenant_id: UUID
    websocket: Any
    subscriptions: set[str] = field(default_factory=set)


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[UUID, ClientConnection] = {}
        self._by_tenant: dict[UUID, set[UUID]] = {}

    async def connect(self, conn: ClientConnection, connection_id: UUID) -> None:
        self._connections[connection_id] = conn
        self._by_tenant.setdefault(conn.tenant_id, set()).add(connection_id)
        logger.info("ws_connected", connection_id=str(connection_id), tenant_id=str(conn.tenant_id))

    async def disconnect(self, connection_id: UUID) -> None:
        conn = self._connections.pop(connection_id, None)
        if conn:
            bucket = self._by_tenant.get(conn.tenant_id)
            if bucket is not None:
                bucket.discard(connection_id)
                if not bucket:
                    self._by_tenant.pop(conn.tenant_id, None)

    async def broadcast_to_tenant(self, tenant_id: UUID, message: dict[str, Any]) -> None:
        for cid in list(self._by_tenant.get(tenant_id, set())):
            conn = self._connections.get(cid)
            if conn is None:
                continue
            try:
                await conn.websocket.send_json(message)
            except Exception as e:
                logger.warning("ws_send_failed", connection_id=str(cid), error=str(e))
                await self.disconnect(cid)

    def tenant_count(self) -> int:
        return len(self._by_tenant)
