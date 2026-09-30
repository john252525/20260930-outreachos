"""Base models and shared primitives for all contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator
from uuid6 import uuid7

T = TypeVar("T")


def utc_now() -> datetime:
    """Timezone-aware UTC now."""
    return datetime.now(UTC)


class EntityBase(BaseModel):
    """Base model for every persisted entity."""

    model_config = ConfigDict(
        extra="ignore",
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    id: UUID = Field(default_factory=uuid7)
    tenant_id: UUID
    schema_version: str = "1.0"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    created_by: str = "system"
    trace_id: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("created_at", "updated_at", mode="after")
    @classmethod
    def _ensure_tz(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        return v.astimezone(UTC)


class Evidence(BaseModel):
    """A single piece of proof for a factual claim."""

    model_config = ConfigDict(extra="ignore")

    source_url: str | None = None
    source_type: str
    extracted_at: datetime = Field(default_factory=utc_now)
    snippet: str | None = None


class Fact(BaseModel, Generic[T]):
    """A value with confidence and evidence."""

    model_config = ConfigDict(extra="ignore")

    value: T | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence: list[Evidence] = Field(default_factory=list)


class EventEnvelope(BaseModel, Generic[T]):
    """Envelope for every NATS event."""

    model_config = ConfigDict(extra="ignore")

    event_id: UUID = Field(default_factory=uuid7)
    event_type: str
    schema_version: str = "1.0"
    occurred_at: datetime = Field(default_factory=utc_now)
    tenant_id: UUID
    trace_id: str = ""
    causation_id: UUID | None = None
    correlation_id: UUID | None = None
    producer: str = "unknown"
    payload: T
