"""Ramp-up limits and mailbox selection."""

from datetime import UTC, date, datetime
from typing import ClassVar
from uuid import UUID

from redis.asyncio import Redis

from sender_email.models import SenderAccount


class RampUpLimiter:
    """Per-mailbox send limits (hourly + daily) backed by Redis."""

    def __init__(self, redis: "Redis[str]") -> None:
        self._redis = redis

    async def can_send(self, account: SenderAccount) -> tuple[bool, str | None]:
        if account.status != "active":
            return False, f"account_status:{account.status}"

        hour_key = f"send:hourly:{account.id}:{datetime.now(UTC).strftime('%Y%m%d%H')}"
        hourly_sent = int(await self._redis.get(hour_key) or 0)
        if hourly_sent >= account.hourly_limit_current:
            return False, f"hourly_limit:{hourly_sent}/{account.hourly_limit_current}"

        day_key = f"send:daily:{account.id}:{date.today().isoformat()}"
        daily_sent = int(await self._redis.get(day_key) or 0)
        if daily_sent >= account.daily_limit_current:
            return False, f"daily_limit:{daily_sent}/{account.daily_limit_current}"

        return True, None

    async def record_send(self, account_id: UUID) -> None:
        hour_key = f"send:hourly:{account_id}:{datetime.now(UTC).strftime('%Y%m%d%H')}"
        await self._redis.incr(hour_key)
        await self._redis.expire(hour_key, 7200)
        day_key = f"send:daily:{account_id}:{date.today().isoformat()}"
        await self._redis.incr(day_key)
        await self._redis.expire(day_key, 7 * 86400)


class WarmUpScheduler:
    """Gradually increases mailbox limits."""

    SCHEDULE: ClassVar[list[tuple[int, int, int]]] = [
        (1, 5, 2),
        (2, 10, 3),
        (3, 15, 5),
        (4, 20, 5),
        (5, 25, 6),
        (6, 30, 7),
        (7, 35, 8),
        (10, 40, 8),
        (14, 45, 9),
        (21, 50, 10),
        (30, 50, 10),
    ]

    def compute_limits(self, warmup_started_at: datetime) -> tuple[int, int]:
        days = (datetime.now(UTC) - warmup_started_at).days + 1
        daily, hourly = self.SCHEDULE[-1][1], self.SCHEDULE[-1][2]
        for day_threshold, d, h in self.SCHEDULE:
            if days >= day_threshold:
                daily, hourly = d, h
        return daily, hourly
