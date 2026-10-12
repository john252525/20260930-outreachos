"""API schemas for auto-revision."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProposeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    trigger_type: str = "manual"
    trigger_context: dict[str, Any] = Field(default_factory=dict)
    window_days: int | None = None


class RejectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = ""


class RevisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore", populate_by_name=True)
    id: UUID
    tenant_id: UUID
    trigger_type: str
    trigger_context: dict[str, Any]
    template_id: str
    template_version: str
    segment_id: str | None
    status: str
    diagnosis: str
    proposed_changes: list[dict[str, Any]]
    proposed_template: dict[str, Any]
    experiment_id: UUID | None
    override_version: str | None
    reviewed_by: str | None
    reviewed_at: datetime | None
    rejection_reason: str | None
    llm_model: str
    llm_confidence: float
    schema_version: str
    created_at: datetime
    updated_at: datetime


class RevisionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")
    id: UUID
    trigger_type: str
    template_id: str
    status: str
    llm_confidence: float
    experiment_id: UUID | None
    created_at: datetime
