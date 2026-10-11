"""API schemas for analytics-service."""

from typing import Any

from pydantic import BaseModel, ConfigDict


class Overview(BaseModel):
    model_config = ConfigDict(extra="ignore")
    sent: int = 0
    replied: int = 0
    bounced: int = 0
    failed: int = 0
    approved: int = 0
    draft: int = 0
    reply_rate: float = 0.0
    bounce_rate: float = 0.0
    sent_count: int = 0
    positive_count: int = 0
    positive_reply_rate: float = 0.0


class Funnel(BaseModel):
    model_config = ConfigDict(extra="ignore")
    contacted: int = 0
    sent: int = 0
    replied: int = 0
    replied_positive: int = 0
    bounced: int = 0
    closed: int = 0
    approved: int = 0
    draft: int = 0


class TemplateMetric(BaseModel):
    model_config = ConfigDict(extra="ignore")
    template_id: str | None = None
    template_version: str | None = None
    sent: int = 0
    replied: int = 0
    bounced: int = 0
    failed: int = 0
    reply_rate: float = 0.0
    bounce_rate: float = 0.0


class SenderMetric(BaseModel):
    model_config = ConfigDict(extra="ignore")
    sender_email: str
    sent: int = 0
    bounced: int = 0
    failed: int = 0
    bounce_rate: float = 0.0


class CategoryMetric(BaseModel):
    model_config = ConfigDict(extra="ignore")
    category: str | None = None
    count: int = 0
    confidence: float | None = None


class SourcingStats(BaseModel):
    model_config = ConfigDict(extra="ignore")
    jobs: int = 0
    raw: int = 0
    normalized: int = 0
    persisted: int = 0
    companies_created: int = 0
    contacts_created: int = 0
    total_cost_usd: float = 0.0
    avg_duration_ms: float = 0.0


class SegmentMetric(BaseModel):
    model_config = ConfigDict(extra="ignore")
    segment_id: str | None = None
    contacted: int = 0
    sent: int = 0
    replied: int = 0
    replied_positive: int = 0


class MetricsResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    data: dict[str, Any]
