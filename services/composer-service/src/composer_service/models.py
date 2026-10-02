"""ORM models for composer-service."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base
from db.mixins import (
    MetadataMixin,
    SchemaVersionMixin,
    TenantMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class Message(
    Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, SchemaVersionMixin, MetadataMixin
):
    __tablename__ = "messages"

    contact_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    company_id: Mapped[UUID | None] = mapped_column(nullable=True, index=True)
    campaign_id: Mapped[UUID | None] = mapped_column(nullable=True, index=True)

    channel: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft", index=True)

    sequence_step: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    sequence_total_steps: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    parent_message_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"), nullable=True
    )
    is_followup: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    followup_after_days: Mapped[int | None] = mapped_column(Integer, nullable=True)

    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    body_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(String(8), nullable=False, default="ru")
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    personalization: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict[str, Any]
    )
    sender: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict[str, Any])
    recipient_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict[str, Any]
    )
    experiment: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    delivery: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict[str, Any])
    engagement: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict[str, Any]
    )
    review: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict[str, Any])

    __table_args__ = (
        Index("ix_messages_tenant_status", "tenant_id", "status"),
        Index("ix_messages_tenant_contact", "tenant_id", "contact_id"),
        Index("ix_messages_tenant_channel", "tenant_id", "channel"),
        Index("ix_messages_tenant_created", "tenant_id", "created_at"),
    )
