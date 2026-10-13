"""API schemas for campaign-service."""

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CampaignCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    owner_user_id: UUID | None = None
    start_date: date | None = None
    end_date: date | None = None
    goals: dict[str, Any] = Field(default_factory=dict)
    budget: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)


class CampaignUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = None
    description: str | None = None
    status: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    goals: dict[str, Any] | None = None
    budget: dict[str, Any] | None = None
    tags: list[str] | None = None


class CampaignRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore", populate_by_name=True)
    id: UUID
    tenant_id: UUID
    name: str
    description: str | None
    owner_user_id: UUID | None
    status: str
    start_date: date | None
    end_date: date | None
    goals: dict[str, Any]
    budget: dict[str, Any]
    targeting_summary: dict[str, Any]
    metrics: dict[str, Any]
    tags: list[str]
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CampaignSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")
    id: UUID
    name: str
    status: str
    start_date: date | None
    end_date: date | None
    created_at: datetime
