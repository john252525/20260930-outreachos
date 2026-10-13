"""Redis pub/sub for cross-instance broadcast."""

import json
from typing import Any
from uuid import UUID

import redis.asyncio as aioredis
import structlog

from realtime_gateway.connections import ConnectionManager

logger = structlog.get_logger()


class PubSub:
    def __init__(self, redis_url: str, manager: ConnectionManager) -> None:
        self._redis = aioredis.from_url(redis_url, decode_responses=True)
        self._pubsub = self._redis.pubsub()
        self._manager = manager
        self._channel = "realtime:broadcast"

    async def publish(self, *, tenant_id: UUID, message: dict[str, Any]) -> None:
        payload = json.dumps({"tenant_id": str(tenant_id), "message": message})
        await self._redis.publish(self._channel, payload)

    async def subscribe_forever(self) -> None:
        await self._pubsub.subscribe(self._channel)
        async for msg in self._pubsub.listen():
            if msg.get("type") != "message":
                continue
            try:
                data = json.loads(msg["data"])
                await self._manager.broadcast_to_tenant(UUID(data["tenant_id"]), data["message"])
            except Exception as e:
                logger.warning("pubsub_message_failed", error=str(e))

    async def close(self) -> None:
        await self._pubsub.close()
        await self._redis.aclose()
