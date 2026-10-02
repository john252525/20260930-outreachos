"""API schemas for composer-service."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contact_id: UUID
    company_id: UUID | None = None
    icp_id: UUID
    segment_id: str
    channel: str = Field(default="email", pattern="^(email|telegram|whatsapp|linkedin)$")
    template_id: str | None = None
    template_version: str | None = None
    language: str = "ru"

    sender_identity_type: str = Field(default="user", pattern="^(user|service)$")
    sender_user_id: str | None = None
    sender_from_email: str | None = None
    sender_from_name: str | None = None
    sender_signature: str | None = None

    experiment_id: UUID | None = None
    variant_id: str | None = None
    hypothesis: str | None = None

    parent_message_id: UUID | None = None
    sequence_step: int = 1
    sequence_total_steps: int = 1
    followup_after_days: int | None = None


class MessageUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: str | None = None
    body_text: str | None = None
    status: str | None = None
    review: dict[str, Any] | None = None


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore", populate_by_name=True)

    id: UUID
    tenant_id: UUID
    contact_id: UUID
    company_id: UUID | None
    campaign_id: UUID | None
    channel: str
    status: str
    sequence_step: int
    sequence_total_steps: int
    parent_message_id: UUID | None
    is_followup: bool
    followup_after_days: int | None
    subject: str | None
    body_text: str
    body_html: str | None
    language: str
    word_count: int
    personalization: dict[str, Any]
    sender: dict[str, Any]
    recipient_snapshot: dict[str, Any]
    experiment: dict[str, Any] | None
    scheduled_at: datetime | None
    sent_at: datetime | None
    delivery: dict[str, Any]
    engagement: dict[str, Any]
    review: dict[str, Any]
    schema_version: str
    created_at: datetime
    updated_at: datetime


class MessageSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: UUID
    contact_id: UUID
    channel: str
    status: str
    subject: str | None
    word_count: int
    created_at: datetime


class TemplateInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")
    template_id: str
    template_version: str
    channel: str
