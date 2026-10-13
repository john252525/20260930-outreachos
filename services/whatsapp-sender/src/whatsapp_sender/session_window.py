"""WhatsApp 24-hour session window checker (Redis)."""

from datetime import UTC, datetime
from typing import Any


class SessionWindowChecker:
    def __init__(self, redis: Any, *, window_hours: int = 24) -> None:
        self._redis = redis
        self._window_hours = window_hours

    async def is_open(self, *, tenant_id: str, phone: str) -> bool:
        key = f"wa:window:{tenant_id}:{phone}"
        last_inbound = await self._redis.get(key)
        if not last_inbound:
            return False
        last_dt = datetime.fromisoformat(str(last_inbound))
        return (datetime.now(UTC) - last_dt).total_seconds() < self._window_hours * 3600

    async def mark_inbound(self, *, tenant_id: str, phone: str) -> None:
        key = f"wa:window:{tenant_id}:{phone}"
        await self._redis.setex(
            key, (self._window_hours + 24) * 3600, datetime.now(UTC).isoformat()
        )
