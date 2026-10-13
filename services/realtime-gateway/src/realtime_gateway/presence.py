"""Presence tracking in Redis (with TTL)."""

from typing import Any
from uuid import UUID


class Presence:
    def __init__(self, redis: Any, *, ttl_seconds: int = 60) -> None:
        self._redis = redis
        self._ttl = ttl_seconds

    async def set_online(self, tenant_id: UUID, user_id: UUID) -> None:
        await self._redis.setex(f"presence:{tenant_id}:{user_id}", self._ttl, "1")

    async def set_offline(self, tenant_id: UUID, user_id: UUID) -> None:
        await self._redis.delete(f"presence:{tenant_id}:{user_id}")

    async def list_online(self, tenant_id: UUID) -> list[str]:
        keys = await self._redis.keys(f"presence:{tenant_id}:*")
        return [str(k).split(":")[-1] for k in keys]
