"""API schemas for sourcing-service."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SearchCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    icp_id: UUID
    segment_id: str = Field(min_length=1, max_length=36)
    sources: list[str] | None = None
    limit_per_source: int | None = Field(default=None, ge=1, le=200)
    urls: list[str] | None = None  # parse these URLs directly (website_parser)


class SearchJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore", populate_by_name=True)
    id: UUID
    tenant_id: UUID
    icp_id: UUID
    segment_id: str
    brief_id: str
    status: str
    params: dict[str, Any]
    progress: dict[str, Any]
    candidates_raw_count: int
    candidates_normalized_count: int
    candidates_persisted_count: int
    companies_created: int
    companies_merged: int
    contacts_created: int
    contacts_merged: int
    total_cost_usd: float
    duration_ms: int | None
    error: str | None
    error_stage: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime


class SearchJobSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")
    id: UUID
    icp_id: UUID
    segment_id: str
    status: str
    candidates_raw_count: int
    candidates_persisted_count: int
    total_cost_usd: float
    duration_ms: int | None
    created_at: datetime


class SearchStats(BaseModel):
    model_config = ConfigDict(extra="ignore")
    period_days: int
    total_jobs: int
    completed_jobs: int
    failed_jobs: int
    total_candidates_raw: int
    total_candidates_persisted: int
    total_companies_created: int
    total_contacts_created: int
    total_cost_usd: float
    avg_duration_ms: int
    avg_yield_percent: float
    by_source: dict[str, dict[str, int]]
    by_status: dict[str, int]
