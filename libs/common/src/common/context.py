"""Context variables for request-scoped data."""

from contextvars import ContextVar, Token
from uuid import UUID

_tenant_id: ContextVar[UUID | None] = ContextVar("tenant_id", default=None)
_trace_id: ContextVar[str | None] = ContextVar("trace_id", default=None)


def set_tenant_id(value: UUID | None) -> Token[UUID | None]:
    return _tenant_id.set(value)


def reset_tenant_id(token: Token[UUID | None]) -> None:
    _tenant_id.reset(token)


def get_tenant_id() -> UUID | None:
    return _tenant_id.get()


def set_trace_id(value: str | None) -> Token[str | None]:
    return _trace_id.set(value)


def reset_trace_id(token: Token[str | None]) -> None:
    _trace_id.reset(token)


def get_trace_id() -> str | None:
    return _trace_id.get()
