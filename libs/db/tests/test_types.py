"""Tests for UUID7 type and helpers."""

from uuid import UUID

from db.types import generate_uuid7


def test_generate_uuid7_is_uuidv7() -> None:
    u = generate_uuid7()
    assert isinstance(u, UUID)
    assert u.version == 7


def test_uuid7_monotonic_prefix() -> None:
    a = generate_uuid7()
    b = generate_uuid7()
    # time-ordered: same millisecond prefix is allowed, but never reversed bytes
    assert a.hex[:12] <= b.hex[:12]
