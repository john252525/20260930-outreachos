"""API schemas for review-queue."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ReviewItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: UUID
    tenant_id: UUID
    message_id: UUID
    contact_id: UUID
    channel: str
    status: str
    priority: str
    assigned_to: str | None
    reviewed_by: str | None
    reviewed_at: datetime | None
    snapshot: dict[str, Any]
    edit: dict[str, Any] | None
    rejection: dict[str, Any] | None
    scheduled_send_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ApproveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scheduled_send_at: datetime | None = None


class RejectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=1, max_length=128)
    note: str | None = None


class EditRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject: str | None = None
    body_text: str = Field(min_length=1)


class AssignRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assigned_to: str = Field(min_length=1, max_length=128)


class BulkApproveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    item_ids: list[UUID] = Field(min_length=1, max_length=200)
