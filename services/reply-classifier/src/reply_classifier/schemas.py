"""API schemas for reply-classifier."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ReplyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore", populate_by_name=True)

    id: UUID
    tenant_id: UUID
    message_id: UUID
    contact_id: UUID
    channel: str
    received_at: datetime
    from_email: str
    from_name: str | None
    subject: str | None
    raw_content: str
    language: str | None
    classification: dict[str, Any]
    category: str | None
    classification_confidence: float | None
    suggested_next_action: dict[str, Any]
    handled_by: str | None
    handled_at: datetime | None
    outcome: str | None
    status: str
    schema_version: str
    created_at: datetime
    updated_at: datetime


class ReplySummary(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: UUID
    message_id: UUID
    contact_id: UUID
    received_at: datetime
    from_email: str
    subject: str | None
    category: str | None
    classification_confidence: float | None
    status: str


class MarkHandledRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    outcome: str | None = None
