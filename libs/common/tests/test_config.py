"""Tests for config, logging, errors, context."""

import pytest

from common.config import BaseServiceSettings
from common.context import get_tenant_id, get_trace_id, set_tenant_id, set_trace_id
from common.errors import ConflictError, NotFoundError


def test_settings_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://x:y@h/db")
    monkeypatch.setenv("NATS_URL", "nats://x:y@h:4222")
    monkeypatch.setenv("REDIS_URL", "redis://:p@h:6379/0")
    s = BaseServiceSettings()
    assert s.database_url.startswith("postgresql")
    assert s.nats_url.startswith("nats")


def test_context_set_get() -> None:
    from uuid import uuid4

    tid = uuid4()
    set_tenant_id(tid)
    assert get_tenant_id() == tid
    set_tenant_id(None)
    assert get_tenant_id() is None


def test_trace_context() -> None:
    set_trace_id("abc")
    assert get_trace_id() == "abc"


def test_error_defaults() -> None:
    assert NotFoundError().status_code == 404
    assert ConflictError("dup").code == "conflict"
    assert ConflictError("dup").message == "dup"
