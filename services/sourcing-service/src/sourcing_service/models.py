"""ORM models for sourcing-service."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base
from db.mixins import (
    MetadataMixin,
    SchemaVersionMixin,
    TenantMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class SearchJob(
    Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, SchemaVersionMixin, MetadataMixin
):
    __tablename__ = "search_jobs"

    icp_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    segment_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    brief_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)

    params: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict[str, Any])
    progress: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict[str, Any])

    candidates_raw_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    candidates_normalized_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    candidates_persisted_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    companies_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    companies_merged: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    contacts_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    contacts_merged: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    total_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_stage: Mapped[str | None] = mapped_column(String(32), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    items: Mapped[list["SearchJobItem"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )


class SearchJobItem(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    __tablename__ = "search_job_items"

    job_id: Mapped[UUID] = mapped_column(
        ForeignKey("search_jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict[str, Any]
    )

    normalized_company: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    normalized_contacts: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)

    score: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)
    score_breakdown: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    status: Mapped[str] = mapped_column(String(32), nullable=False, default="raw", index=True)
    skip_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    company_id: Mapped[UUID | None] = mapped_column(nullable=True, index=True)
    contact_ids: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)

    job: Mapped[SearchJob] = relationship(back_populates="items")
