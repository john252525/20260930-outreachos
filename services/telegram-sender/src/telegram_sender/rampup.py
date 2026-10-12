"""Warm-up schedule for Telegram accounts.

Telegram bans much faster than email — daily limits are kept very low.
"""

from datetime import UTC, datetime
from typing import Any


class WarmUpScheduler:
    """Returns (daily_limit, hourly_limit) by day-since-warmup-start."""

    def compute_limits(self, warmup_started_at: datetime | None) -> tuple[int, int]:
        if warmup_started_at is None:
            return (3, 1)
        days = (datetime.now(UTC) - warmup_started_at).days
        if days < 3:
            return (3, 1)
        if days < 7:
            return (5, 2)
        if days < 14:
            return (10, 3)
        if days < 30:
            return (20, 5)
        return (30, 5)


class TelegramRateLimiter:
    """Simple in-DB daily/hourly limit check via Redis counters."""

    def __init__(self, redis: Any) -> None:
        self._redis = redis

    async def can_send(self, *, account_id: str, daily: int, hourly: int) -> tuple[bool, str]:
        redis = self._redis
        day_key = f"tg:daily:{account_id}"
        hour_key = f"tg:hourly:{account_id}"
        daily_used = int(await redis.get(day_key) or 0)
        hourly_used = int(await redis.get(hour_key) or 0)
        if daily_used >= daily:
            return False, "daily_limit"
        if hourly_used >= hourly:
            return False, "hourly_limit"
        return True, ""

    async def record_send(self, *, account_id: str) -> None:
        redis = self._redis
        day_key = f"tg:daily:{account_id}"
        hour_key = f"tg:hourly:{account_id}"
        await redis.incr(day_key)
        await redis.expire(day_key, 86400)
        await redis.incr(hour_key)
        await redis.expire(hour_key, 3600)
