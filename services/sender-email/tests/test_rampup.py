"""Unit tests for the ramp-up limiter and scheduler."""

from datetime import UTC, datetime, timedelta

from sender_email.rampup.limiter import WarmUpScheduler


def test_schedule_day1():
    s = WarmUpScheduler()
    d, h = s.compute_limits(datetime.now(UTC))
    assert d == 5
    assert h == 2


def test_schedule_stabilized():
    s = WarmUpScheduler()
    d, h = s.compute_limits(datetime.now(UTC) - timedelta(days=40))
    assert d == 50
    assert h == 10


def test_schedule_midway():
    s = WarmUpScheduler()
    d, h = s.compute_limits(datetime.now(UTC) - timedelta(days=4))
    assert d == 25
    assert h == 6
