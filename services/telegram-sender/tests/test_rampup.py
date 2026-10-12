"""Unit tests for the Telegram warm-up scheduler."""

from datetime import UTC, datetime, timedelta

from telegram_sender.rampup import WarmUpScheduler


def test_day_zero() -> None:
    s = WarmUpScheduler()
    assert s.compute_limits(datetime.now(UTC)) == (3, 1)


def test_none_start() -> None:
    s = WarmUpScheduler()
    assert s.compute_limits(None) == (3, 1)


def test_midway() -> None:
    s = WarmUpScheduler()
    assert s.compute_limits(datetime.now(UTC) - timedelta(days=10)) == (10, 3)


def test_stabilized() -> None:
    s = WarmUpScheduler()
    assert s.compute_limits(datetime.now(UTC) - timedelta(days=60)) == (30, 5)


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, int] = {}

    async def get(self, key: str) -> int | None:
        return self.store.get(key)

    async def incr(self, key: str) -> None:
        self.store[key] = self.store.get(key, 0) + 1

    async def expire(self, key: str, ttl: int) -> None:
        return None


import pytest  # noqa: E402
from telegram_sender.rampup import TelegramRateLimiter  # noqa: E402


@pytest.mark.asyncio
async def test_rate_limiter_blocks_daily() -> None:
    r = FakeRedis()
    limiter = TelegramRateLimiter(r)
    for _ in range(3):
        can, _ = await limiter.can_send(account_id="a", daily=3, hourly=10)
        assert can
        await limiter.record_send(account_id="a")
    can, reason = await limiter.can_send(account_id="a", daily=3, hourly=10)
    assert not can
    assert reason == "daily_limit"


@pytest.mark.asyncio
async def test_rate_limiter_blocks_hourly() -> None:
    r = FakeRedis()
    limiter = TelegramRateLimiter(r)
    for _ in range(2):
        await limiter.record_send(account_id="b")
    can, reason = await limiter.can_send(account_id="b", daily=100, hourly=2)
    assert not can
    assert reason == "hourly_limit"
