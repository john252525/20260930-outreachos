"""ORM models for ml-scoring."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base
from db.mixins import TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class ContactFeatures(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    """Denormalised features for ML scoring (refreshed by a background worker)."""

    __tablename__ = "contact_features"

    contact_id: Mapped[UUID] = mapped_column(nullable=False, index=True)

    role_category: Mapped[str | None] = mapped_column(String(32), nullable=True)
    seniority: Mapped[str | None] = mapped_column(String(32), nullable=True)
    company_industry: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company_size_range: Mapped[str | None] = mapped_column(String(16), nullable=True)
    company_country: Mapped[str | None] = mapped_column(String(2), nullable=True)

    company_employee_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    company_signals_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    days_since_company_created: Mapped[int | None] = mapped_column(Integer, nullable=True)

    has_reply: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_positive_reply: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    messages_sent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_message_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("uq_contact_features_tenant_contact", "tenant_id", "contact_id", unique=True),
    )
