"""API schemas for contact-store."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# ---- Companies ----


class CompanyUpsert(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payload: dict[str, Any]
    status: str = "candidate"


class CompanyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore", populate_by_name=True)

    id: UUID
    tenant_id: UUID
    fingerprint: str
    status: str
    payload: dict[str, Any]
    contacts_count: int
    last_contacted_at: datetime | None
    schema_version: str
    metadata: dict[str, Any] = Field(default_factory=dict[str, Any], validation_alias="metadata_")
    created_at: datetime
    updated_at: datetime


class CompanyUpsertResult(BaseModel):
    model_config = ConfigDict(extra="ignore")
    company: CompanyRead
    action: str


class CompanyBulkUpsert(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[CompanyUpsert] = Field(min_length=1, max_length=500)


class CompanyBulkResult(BaseModel):
    model_config = ConfigDict(extra="ignore")
    created: int
    updated: int
    merged: int
    results: list[CompanyUpsertResult]
    errors: list[dict[str, Any]]


# ---- Contacts ----


class ContactUpsert(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payload: dict[str, Any]
    status: str = "candidate"


class ContactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore", populate_by_name=True)

    id: UUID
    tenant_id: UUID
    company_id: UUID | None
    fingerprint: str
    status: str
    payload: dict[str, Any]
    last_contacted_at: datetime | None
    last_reply_at: datetime | None
    replied_positive: bool
    schema_version: str
    metadata: dict[str, Any] = Field(default_factory=dict[str, Any], validation_alias="metadata_")
    created_at: datetime
    updated_at: datetime


class ContactUpsertResult(BaseModel):
    model_config = ConfigDict(extra="ignore")
    contact: ContactRead
    action: str


class ContactStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str = Field(
        pattern="^(candidate|approved|contacted|replied|qualified|disqualified|unsubscribed|bounced|archived)$"
    )


class OutreachHistoryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    replied_positive: bool | None = None
    last_reply_at: datetime | None = None
    last_contacted_at: datetime | None = None


class ContactBulkUpsert(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[ContactUpsert] = Field(min_length=1, max_length=500)


class ContactBulkResult(BaseModel):
    model_config = ConfigDict(extra="ignore")
    created: int
    updated: int
    merged: int
    blocked: int
    results: list[ContactUpsertResult]
    errors: list[dict[str, Any]]


# ---- Stop-list ----


class StopListEntryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str = Field(pattern="^(email|phone|domain)$")
    value: str = Field(min_length=1, max_length=512)
    reason: str = Field(pattern="^(unsubscribed|bounced_hard|complained|manual|disqualified)$")
    note: str | None = None


class StopListEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")
    id: UUID
    tenant_id: UUID | None
    scope: str
    kind: str
    value: str
    reason: str
    note: str | None
    created_by: str
    created_at: datetime
