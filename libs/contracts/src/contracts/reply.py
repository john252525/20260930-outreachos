"""Reply contract v1."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from contracts.base import EntityBase, utc_now
from contracts.enums import Channel, NextAction, ReplyCategory, Sentiment


class Classification(BaseModel):
    model_config = ConfigDict(extra="ignore")

    category: ReplyCategory = ReplyCategory.UNKNOWN
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    sentiment: Sentiment = Sentiment.NEUTRAL
    intent: str | None = None
    extracted_questions: list[str] = Field(default_factory=list)
    extracted_actions: list[str] = Field(default_factory=list)
    classified_by: str = "llm"
    classified_at: datetime = Field(default_factory=utc_now)


class SuggestedNextAction(BaseModel):
    model_config = ConfigDict(extra="ignore")

    action: NextAction = NextAction.FORWARD_TO_HUMAN
    reason: str = ""
    draft_reply: str | None = None


class Reply(EntityBase):
    """Inbound reply to a message."""

    message_id: UUID
    contact_id: UUID
    channel: Channel = Channel.EMAIL
    received_at: datetime = Field(default_factory=utc_now)
    raw_content: str = ""
    language: str | None = None

    classification: Classification = Field(default_factory=Classification)
    suggested_next_action: SuggestedNextAction = Field(default_factory=SuggestedNextAction)

    handled_by: str | None = None
    handled_at: datetime | None = None
    outcome: str | None = None
