"""ORM models for auto-revision."""

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


class Revision(
    Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, SchemaVersionMixin, MetadataMixin
):
    __tablename__ = "revisions"

    trigger_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    trigger_context: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    template_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    template_version: Mapped[str] = mapped_column(String(16), nullable=False, default="v1")
    segment_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)

    diagnosis: Mapped[str] = mapped_column(Text, nullable=False, default="")
    proposed_changes: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    proposed_template: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    experiment_id: Mapped[UUID | None] = mapped_column(nullable=True, index=True)
    override_version: Mapped[str | None] = mapped_column(String(64), nullable=True)

    reviewed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    llm_model: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    llm_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    __table_args__ = (
        Index("ix_revisions_tenant_status", "tenant_id", "status"),
        Index("ix_revisions_tenant_template", "tenant_id", "template_id"),
    )
