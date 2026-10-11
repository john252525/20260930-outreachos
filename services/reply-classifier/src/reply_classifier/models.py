"""ORM models for reply-classifier."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, Float, Index, String, Text
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


class Reply(
    Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, SchemaVersionMixin, MetadataMixin
):
    __tablename__ = "replies"

    message_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    contact_id: Mapped[UUID] = mapped_column(nullable=False, index=True)

    channel: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    # Raw content
    from_email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    from_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(500), nullable=True)
    raw_content: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str | None] = mapped_column(String(8), nullable=True)

    # Headers (threading)
    in_reply_to: Mapped[str | None] = mapped_column(String(255), nullable=True)
    references: Mapped[str | None] = mapped_column(Text, nullable=True)
    message_id_header: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Classification (JSONB with the full structured payload)
    classification: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict[str, Any]
    )

    # Hot columns mirrored from ``classification`` for fast lookups
    category: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    classification_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Suggested next action
    suggested_next_action: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict[str, Any]
    )

    # Human handling
    handled_by: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    handled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Status: pending | classified | needs_review | handled | archived
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)

    __table_args__ = (
        Index("ix_replies_tenant_message", "tenant_id", "message_id"),
        Index("ix_replies_tenant_contact", "tenant_id", "contact_id"),
        Index("ix_replies_tenant_status", "tenant_id", "status"),
        Index("ix_replies_tenant_received", "tenant_id", "received_at"),
        Index("ix_replies_tenant_category", "tenant_id", "category"),
        Index(
            "ix_replies_tenant_category_conf",
            "tenant_id",
            "category",
            "classification_confidence",
        ),
    )
