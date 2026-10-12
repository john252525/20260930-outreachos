"""API schemas for orchestrator."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FlowStepRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: UUID
    flow_id: UUID
    step_name: str
    status: str
    input_data: dict[str, Any]
    output_data: dict[str, Any]
    attempts: int
    max_attempts: int
    next_retry_at: datetime | None
    error: str | None
    started_at: datetime | None
    finished_at: datetime | None
    duration_ms: int | None


class FlowRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore", populate_by_name=True)

    id: UUID
    tenant_id: UUID
    flow_type: str
    status: str
    brief_id: str | None
    icp_id: UUID | None
    search_job_id: UUID | None
    params: dict[str, Any]
    current_step: str | None
    progress: dict[str, Any]
    total_steps: int
    completed_steps: int
    failed_steps: int
    started_at: datetime | None
    finished_at: datetime | None
    error: str | None
    schema_version: str
    created_at: datetime
    updated_at: datetime


class FlowSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: UUID
    flow_type: str
    status: str
    brief_id: str | None
    icp_id: UUID | None
    search_job_id: UUID | None
    current_step: str | None
    completed_steps: int
    total_steps: int
    created_at: datetime


class TriggerDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contact_ids: list[UUID] | None = None
    channel: str = "email"
    template_id: str | None = None
    sender_config: dict[str, Any] = Field(default_factory=dict)
    max_contacts: int | None = None


class CreateFlowRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    brief_id: str | None = None
    flow_type: str = "brief_to_outreach"
    params: dict[str, Any] = Field(default_factory=dict)
