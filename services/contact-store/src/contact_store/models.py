"""ORM models for contact-store."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
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
from db.types import UUID7


class Company(
    Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, SchemaVersionMixin, MetadataMixin
):
    __tablename__ = "companies"

    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="candidate", index=True)

    name_normalized: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    domain_normalized: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    inn: Mapped[str | None] = mapped_column(String(12), nullable=True, index=True)
    ogrn: Mapped[str | None] = mapped_column(String(15), nullable=True, index=True)

    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict[str, Any])

    contacts_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_contacted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "fingerprint", name="uq_companies_tenant_fingerprint"),
        Index("ix_companies_tenant_status", "tenant_id", "status"),
        Index("ix_companies_tenant_created", "tenant_id", "created_at"),
    )

    contacts: Mapped[list["Contact"]] = relationship(back_populates="company")


class Contact(
    Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, SchemaVersionMixin, MetadataMixin
):
    __tablename__ = "contacts"

    company_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("companies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="candidate", index=True)

    full_name_normalized: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    primary_email: Mapped[str | None] = mapped_column(String(320), nullable=True, index=True)
    primary_phone: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    role_category: Mapped[str] = mapped_column(
        String(32), nullable=False, default="unknown", index=True
    )
    seniority: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")

    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict[str, Any])

    last_contacted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_reply_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    replied_positive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "fingerprint", name="uq_contacts_tenant_fingerprint"),
        Index("ix_contacts_tenant_status", "tenant_id", "status"),
        Index("ix_contacts_tenant_created", "tenant_id", "created_at"),
        Index("ix_contacts_company", "company_id"),
    )

    company: Mapped[Company | None] = relationship(back_populates="contacts")


class ContactEmail(Base, UUIDPrimaryKeyMixin, TenantMixin):
    """Separate emails table for fast lookup and dedup."""

    __tablename__ = "contact_emails"

    contact_id: Mapped[UUID] = mapped_column(
        ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    value: Mapped[str] = mapped_column(String(320), nullable=False)
    type: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    evidence: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)

    __table_args__ = (
        Index("ix_contact_emails_tenant_value", "tenant_id", "value", unique=True),
        Index("ix_contact_emails_contact", "contact_id"),
    )


class ContactPhone(Base, UUIDPrimaryKeyMixin, TenantMixin):
    """Separate phones table for fast lookup and dedup."""

    __tablename__ = "contact_phones"

    contact_id: Mapped[UUID] = mapped_column(
        ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    value: Mapped[str] = mapped_column(String(20), nullable=False)
    type: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_whatsapp: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_telegram: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    evidence: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)

    __table_args__ = (
        Index("ix_contact_phones_tenant_value", "tenant_id", "value", unique=True),
        Index("ix_contact_phones_contact", "contact_id"),
    )


class StopListEntry(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Stop-list entries. Global entries have tenant_id = NULL."""

    __tablename__ = "stoplist_entries"

    # nullable: global entries (scope="global") have tenant_id = NULL
    tenant_id: Mapped[UUID | None] = mapped_column(UUID7, nullable=True)
    scope: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    value: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(String(64), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False, default="system")

    __table_args__ = (
        Index("ix_stoplist_lookup", "kind", "value"),
        Index("ix_stoplist_tenant", "tenant_id"),
    )
