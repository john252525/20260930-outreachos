"""API schemas for icp-service."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ICPGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    brief_id: str = Field(min_length=1, max_length=36)


class ICPRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore", populate_by_name=True)
    id: UUID
    tenant_id: UUID
    brief_id: str
    version: int
    is_active: bool
    payload: dict[str, Any]
    segments_count: int
    llm_confidence: float
    schema_version: str
    created_at: datetime
    updated_at: datetime


class ICPSummary(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: UUID
    brief_id: str
    version: int
    is_active: bool
    segments_count: int
    llm_confidence: float
    created_at: datetime
