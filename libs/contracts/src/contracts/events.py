"""Event payload models and the registry for all NATS events."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from contracts.base import EventEnvelope
from contracts.enums import Channel, ReplyCategory, TenantStatus


class TenantSnapshot(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: UUID
    name: str
    status: TenantStatus


class TenantCreatedPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    tenant: TenantSnapshot


class TenantUpdatedPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    tenant: TenantSnapshot


class TenantArchivedPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    tenant: TenantSnapshot


class TenantRestoredPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    tenant: TenantSnapshot


class BriefSnapshot(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: UUID
    status: str = ""
    completeness_score: float = 0.0


class BriefCreatedPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    brief: BriefSnapshot


class BriefUpdatedPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    brief: BriefSnapshot


class BriefQuestionsAskedPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    brief_id: UUID
    questions: list[dict[str, Any]] = Field(default_factory=list)


class BriefCompletedPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    brief: BriefSnapshot


class ICPSnapshot(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: UUID
    brief_id: UUID
    version: int
    segments_count: int = 0


class ICPGeneratedPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    icp: ICPSnapshot


class ICPRevisedPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    icp: ICPSnapshot


class ContactsSearchStartedPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    icp_id: UUID
    segment_id: UUID
    sources: list[str] = Field(default_factory=list)


class ContactsFoundPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    icp_id: UUID
    segment_id: UUID | str
    count: int = 0
    contact_ids: list[UUID] = Field(default_factory=list)
    company_ids: list[UUID] = Field(default_factory=list)
    search_job_id: UUID | None = None


class ContactsEnrichedPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    contact_ids: list[UUID] = Field(default_factory=list)


class CompanySnapshot(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: UUID
    fingerprint: str = ""
    status: str = ""


class CompanyCreatedPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    company: CompanySnapshot


class CompanyUpdatedPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    company: CompanySnapshot


class CompanyMergedPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    company: CompanySnapshot


class ContactSnapshot(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: UUID
    fingerprint: str = ""
    status: str = ""
    company_id: UUID | None = None


class ContactCreatedPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    contact: ContactSnapshot


class ContactUpdatedPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    contact: ContactSnapshot


class ContactMergedPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    contact: ContactSnapshot


class ContactUnsubscribedPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    contact: ContactSnapshot


class MessageSnapshot(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: UUID
    contact_id: UUID
    channel: Channel
    template_id: str = ""


class MessageDraftedPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    message: MessageSnapshot


class MessageApprovedPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    message_id: UUID
    approved_by: str
    edited: bool = False


class MessageRejectedPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    message_id: UUID
    rejected_by: str
    reason: str = ""


class MessageQueuedPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    message_id: UUID
    scheduled_at: str | None = None


class MessageSentPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    message_id: UUID
    channel: Channel
    sender: str
    provider_message_id: str | None = None


class MessageBouncedPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    message_id: UUID
    bounce_type: str
    reason: str = ""


class MessageFailedPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    message_id: UUID
    reason: str = ""


class ReplySnapshot(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: UUID
    message_id: UUID
    contact_id: UUID
    channel: Channel
    from_email: str = ""
    from_name: str | None = None
    subject: str | None = None
    body: str = ""
    received_at: str | None = None
    in_reply_to: str | None = None
    references: str | None = None
    message_id_header: str | None = None


class ReplyReceivedPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    reply: ReplySnapshot


class ReplyClassifiedPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    reply_id: UUID
    category: ReplyCategory
    confidence: float = 0.0


class AnalyticsAlertPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    alert_type: str
    value: float = 0.0
    threshold: float = 0.0
    message: str = ""


class FlowSnapshot(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: UUID
    type: str = ""
    brief_id: str | None = None


class FlowStartedPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    flow: FlowSnapshot


class FlowStepCompletedPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    flow_id: UUID
    step_name: str
    duration_ms: int | None = None


class FlowCompletedPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    flow: FlowSnapshot


class FlowFailedPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    flow_id: UUID
    step_name: str = ""
    error: str = ""


class RevisionSnapshot(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: UUID
    template_id: str = ""
    trigger_type: str = ""


class LinkedInBanDetectedPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    account_id: UUID
    reason: str = ""


class RevisionProposedPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    revision: RevisionSnapshot


class RevisionApprovedPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    revision_id: UUID
    experiment_id: UUID | None = None


class RevisionRejectedPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    revision_id: UUID
    reason: str = ""


class ExperimentCreatedPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    experiment_id: UUID
    name: str
    variants_count: int = 0


class ExperimentVariantWonPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    experiment_id: UUID
    variant_id: str


class LLMCalledPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    task_type: str
    model: str
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0


class CostRecordedPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    cost_usd: float = 0.0
    category: str = ""


EVENT_PAYLOAD_MAP: dict[str, type[BaseModel]] = {
    "tenant.created": TenantCreatedPayload,
    "tenant.updated": TenantUpdatedPayload,
    "tenant.archived": TenantArchivedPayload,
    "tenant.restored": TenantRestoredPayload,
    "brief.created": BriefCreatedPayload,
    "brief.updated": BriefUpdatedPayload,
    "brief.questions_asked": BriefQuestionsAskedPayload,
    "brief.completed": BriefCompletedPayload,
    "icp.generated": ICPGeneratedPayload,
    "icp.revised": ICPRevisedPayload,
    "company.created": CompanyCreatedPayload,
    "company.updated": CompanyUpdatedPayload,
    "company.merged": CompanyMergedPayload,
    "contact.created": ContactCreatedPayload,
    "contact.updated": ContactUpdatedPayload,
    "contact.merged": ContactMergedPayload,
    "contact.unsubscribed": ContactUnsubscribedPayload,
    "contacts.search_started": ContactsSearchStartedPayload,
    "contacts.found": ContactsFoundPayload,
    "contacts.enriched": ContactsEnrichedPayload,
    "message.drafted": MessageDraftedPayload,
    "message.approved": MessageApprovedPayload,
    "message.rejected": MessageRejectedPayload,
    "message.queued": MessageQueuedPayload,
    "message.sent": MessageSentPayload,
    "message.bounced": MessageBouncedPayload,
    "message.failed": MessageFailedPayload,
    "reply.received": ReplyReceivedPayload,
    "reply.classified": ReplyClassifiedPayload,
    "analytics.alert": AnalyticsAlertPayload,
    "flow.started": FlowStartedPayload,
    "flow.step_completed": FlowStepCompletedPayload,
    "flow.completed": FlowCompletedPayload,
    "flow.failed": FlowFailedPayload,
    "revision.proposed": RevisionProposedPayload,
    "revision.approved": RevisionApprovedPayload,
    "revision.rejected": RevisionRejectedPayload,
    "linkedin.ban_detected": LinkedInBanDetectedPayload,
    "experiment.created": ExperimentCreatedPayload,
    "experiment.variant_won": ExperimentVariantWonPayload,
    "llm.called": LLMCalledPayload,
    "cost.recorded": CostRecordedPayload,
}


def payload_model_for(event_type: str) -> type[BaseModel]:
    try:
        return EVENT_PAYLOAD_MAP[event_type]
    except KeyError as exc:
        raise ValueError(f"Unknown event type: {event_type}") from exc


def parse_event(event_type: str, data: dict[str, Any]) -> EventEnvelope[Any]:
    """Parse a raw event dict into a typed envelope."""
    model_cls = payload_model_for(event_type)
    envelope_cls = EventEnvelope[model_cls]  # type: ignore[valid-type]
    return envelope_cls.model_validate(data)
