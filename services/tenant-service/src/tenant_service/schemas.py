"""Pydantic schemas for tenant-service API."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TenantCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")
    is_sandbox: bool = False


class TenantUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=255)
    status: str | None = None


class TenantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore", populate_by_name=True)

    id: UUID
    name: str
    slug: str
    status: str
    is_sandbox: bool
    schema_version: str
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, object] = Field(default_factory=dict, validation_alias="metadata_")
