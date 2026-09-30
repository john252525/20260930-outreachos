"""ORM models for brief-service."""

from typing import Any

from sqlalchemy import Float, String
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


class Brief(
    Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, SchemaVersionMixin, MetadataMixin
):
    __tablename__ = "briefs"

    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft", index=True)
    completeness_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    raw_input: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    qa_history: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    identity: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    offering: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    targeting_hints: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    outreach_goals: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    missing_info: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)

    created_by: Mapped[str] = mapped_column(String(128), nullable=False, default="system")
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
