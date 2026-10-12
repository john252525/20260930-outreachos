"""ORM models for orchestrator."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
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


class Flow(
    Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, SchemaVersionMixin, MetadataMixin
):
    __tablename__ = "flows"

    flow_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)

    brief_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    icp_id: Mapped[UUID | None] = mapped_column(nullable=True, index=True)
    search_job_id: Mapped[UUID | None] = mapped_column(nullable=True, index=True)

    params: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    current_step: Mapped[str | None] = mapped_column(String(64), nullable=True)
    progress: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    total_steps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_steps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_steps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    steps: Mapped[list["FlowStep"]] = relationship(
        back_populates="flow", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_flows_tenant_type_status", "tenant_id", "flow_type", "status"),)


class FlowStep(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    __tablename__ = "flow_steps"

    flow_id: Mapped[UUID] = mapped_column(
        ForeignKey("flows.id", ondelete="CASCADE"), nullable=False, index=True
    )

    step_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)

    input_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    output_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    next_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    flow: Mapped[Flow] = relationship(back_populates="steps")

    __table_args__ = (
        Index("ix_flow_steps_flow_step", "flow_id", "step_name"),
        Index("ix_flow_steps_status_retry", "status", "next_retry_at"),
    )
