"""Very conservative warm-up schedule for LinkedIn accounts.

LinkedIn bans aggressively — new accounts start at 5 actions/day and only
reach the ceiling (20/day) after a month.
"""

from datetime import UTC, datetime
from typing import Any


class WarmUpScheduler:
    def compute_limits(self, warmup_started_at: datetime | None) -> tuple[int, int]:
        """Returns (daily_limit, weekly_limit)."""
        if warmup_started_at is None:
            return (5, 20)
        days = (datetime.now(UTC) - warmup_started_at).days
        if days < 7:
            return (5, 20)
        if days < 14:
            return (10, 40)
        if days < 30:
            return (15, 60)
        return (20, 80)


class LinkedInRateLimiter:
    def __init__(self, redis: Any) -> None:
        self._redis = redis

    async def can_send(self, *, account_id: str, daily: int, weekly: int) -> tuple[bool, str]:
        day_raw = await self._redis.get(f"li:daily:{account_id}")
        day_used = int(day_raw or 0)
        week_raw = await self._redis.get(f"li:weekly:{account_id}")
        week_used = int(week_raw or 0)
        if day_used >= daily:
            return False, "daily_limit"
        if week_used >= weekly:
            return False, "weekly_limit"
        return True, ""

    async def record_send(self, *, account_id: str) -> None:
        day_key = f"li:daily:{account_id}"
        week_key = f"li:weekly:{account_id}"
        await self._redis.incr(day_key)
        await self._redis.expire(day_key, 86400)
        await self._redis.incr(week_key)
        await self._redis.expire(week_key, 7 * 86400)
