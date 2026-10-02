"""ORM models for review-queue."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base
from db.mixins import TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class ReviewItem(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    __tablename__ = "review_items"

    message_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    contact_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(16), nullable=False)

    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="normal", index=True)

    assigned_to: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    edit: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    rejection: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    scheduled_send_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("ix_review_items_tenant_status", "tenant_id", "status"),
        Index("ix_review_items_tenant_priority_status", "tenant_id", "priority", "status"),
        Index("ix_review_items_tenant_assigned", "tenant_id", "assigned_to"),
        Index("ix_review_items_created", "tenant_id", "created_at"),
    )
