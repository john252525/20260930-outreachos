"""Message contract v1."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from contracts.base import EntityBase
from contracts.enums import BounceType, Channel, IdentityType, MessageStatus


class MessageSequence(BaseModel):
    model_config = ConfigDict(extra="ignore")

    step: int = 1
    total_steps: int = 1
    parent_message_id: UUID | None = None
    is_followup: bool = False
    followup_after_days: int | None = None


class MessageContent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    subject: str | None = None
    body_text: str
    body_html: str | None = None
    language: str = "ru"
    word_count: int = 0


class FactualClaim(BaseModel):
    model_config = ConfigDict(extra="ignore")

    claim: str
    evidence_url: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    is_hypothesis: bool = False


class Personalization(BaseModel):
    model_config = ConfigDict(extra="ignore")

    template_id: str = ""
    template_version: str = "1.0"
    llm_model: str = ""
    variables_used: dict[str, Any] = Field(default_factory=dict)
    factual_claims: list[FactualClaim] = Field(default_factory=list)


class Sender(BaseModel):
    model_config = ConfigDict(extra="ignore")

    identity_type: IdentityType = IdentityType.USER
    user_id: str | None = None
    from_email: str | None = None
    from_name: str | None = None
    reply_to: str | None = None
    messaging_account_id: str | None = None
    signature: str | None = None


class RecipientSnapshot(BaseModel):
    model_config = ConfigDict(extra="ignore")

    email: str | None = None
    phone: str | None = None
    messenger_handle: str | None = None
    full_name: str = ""
    position: str | None = None
    company_name: str | None = None


class ExperimentRef(BaseModel):
    model_config = ConfigDict(extra="ignore")

    experiment_id: UUID | None = None
    variant_id: str | None = None
    hypothesis: str | None = None


class SendSchedule(BaseModel):
    model_config = ConfigDict(extra="ignore")

    scheduled_at: datetime | None = None
    sent_at: datetime | None = None
    timezone: str | None = None
    ramp_up_bucket: int | None = None


class Delivery(BaseModel):
    model_config = ConfigDict(extra="ignore")

    provider_message_id: str | None = None
    provider_response: dict[str, Any] = Field(default_factory=dict)
    bounce_type: BounceType | None = None
    bounce_reason: str | None = None
    failed_reason: str | None = None


class Engagement(BaseModel):
    model_config = ConfigDict(extra="ignore")

    opened_count: int = 0
    first_opened_at: datetime | None = None
    last_opened_at: datetime | None = None
    clicked_count: int = 0
    first_clicked_at: datetime | None = None
    replied_at: datetime | None = None
    reply_id: UUID | None = None


class Review(BaseModel):
    model_config = ConfigDict(extra="ignore")

    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    rejection_reason: str | None = None
    edited_by_human: bool = False
    original_body_text: str | None = None


class Message(EntityBase):
    """A single outbound message to a single contact."""

    contact_id: UUID
    company_id: UUID | None = None
    campaign_id: UUID | None = None

    channel: Channel = Channel.EMAIL
    status: MessageStatus = MessageStatus.DRAFT

    sequence: MessageSequence = Field(default_factory=MessageSequence)
    content: MessageContent
    personalization: Personalization = Field(default_factory=Personalization)
    sender: Sender = Field(default_factory=Sender)
    recipient_snapshot: RecipientSnapshot = Field(default_factory=RecipientSnapshot)
    experiment: ExperimentRef = Field(default_factory=ExperimentRef)
    send_schedule: SendSchedule = Field(default_factory=SendSchedule)
    delivery: Delivery = Field(default_factory=Delivery)
    engagement: Engagement = Field(default_factory=Engagement)
    review: Review = Field(default_factory=Review)

    tags: list[str] = Field(default_factory=list)
