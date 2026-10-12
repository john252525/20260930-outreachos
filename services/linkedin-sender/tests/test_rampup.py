"""Unit tests for the LinkedIn warm-up scheduler and rate limiter."""

from datetime import UTC, datetime, timedelta

import pytest
from linkedin_sender.rampup import LinkedInRateLimiter, WarmUpScheduler


def test_new_account_limits() -> None:
    s = WarmUpScheduler()
    assert s.compute_limits(None) == (5, 20)
    assert s.compute_limits(datetime.now(UTC)) == (5, 20)


def test_stabilized_limits() -> None:
    s = WarmUpScheduler()
    assert s.compute_limits(datetime.now(UTC) - timedelta(days=60)) == (20, 80)


def test_midway_limits() -> None:
    s = WarmUpScheduler()
    assert s.compute_limits(datetime.now(UTC) - timedelta(days=10)) == (10, 40)


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, int] = {}

    async def get(self, key: str) -> int | None:
        return self.store.get(key)

    async def incr(self, key: str) -> None:
        self.store[key] = self.store.get(key, 0) + 1

    async def expire(self, key: str, ttl: int) -> None:
        return None


@pytest.mark.asyncio
async def test_rate_limiter_daily() -> None:
    r = FakeRedis()
    limiter = LinkedInRateLimiter(r)
    for _ in range(5):
        can, _ = await limiter.can_send(account_id="a", daily=5, weekly=100)
        assert can
        await limiter.record_send(account_id="a")
    can, reason = await limiter.can_send(account_id="a", daily=5, weekly=100)
    assert not can
    assert reason == "daily_limit"


@pytest.mark.asyncio
async def test_rate_limiter_weekly() -> None:
    r = FakeRedis()
    limiter = LinkedInRateLimiter(r)
    for _ in range(20):
        await limiter.record_send(account_id="b")
    can, reason = await limiter.can_send(account_id="b", daily=1000, weekly=20)
    assert not can
    assert reason == "weekly_limit"
