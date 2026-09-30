"""NATS subjects and stream mapping."""

from enum import StrEnum


class Subjects(StrEnum):
    TENANT_CREATED = "tenant.created"
    TENANT_UPDATED = "tenant.updated"
    TENANT_ARCHIVED = "tenant.archived"
    TENANT_RESTORED = "tenant.restored"

    BRIEF_CREATED = "brief.created"
    BRIEF_UPDATED = "brief.updated"
    BRIEF_QUESTIONS_ASKED = "brief.questions_asked"
    BRIEF_COMPLETED = "brief.completed"

    ICP_GENERATED = "icp.generated"
    ICP_REVISED = "icp.revised"

    CONTACTS_SEARCH_STARTED = "contacts.search_started"
    CONTACTS_FOUND = "contacts.found"
    CONTACTS_ENRICHED = "contacts.enriched"

    MESSAGE_DRAFTED = "message.drafted"
    MESSAGE_APPROVED = "message.approved"
    MESSAGE_REJECTED = "message.rejected"
    MESSAGE_QUEUED = "message.queued"
    MESSAGE_SENT = "message.sent"
    MESSAGE_BOUNCED = "message.bounced"
    MESSAGE_FAILED = "message.failed"

    REPLY_RECEIVED = "reply.received"
    REPLY_CLASSIFIED = "reply.classified"

    EXPERIMENT_CREATED = "experiment.created"
    EXPERIMENT_VARIANT_WON = "experiment.variant_won"

    LLM_CALLED = "llm.called"
    COST_RECORDED = "cost.recorded"

    @classmethod
    def full(cls, subject: "Subjects", tenant_id: str) -> str:
        return f"{subject.value}.{tenant_id}"

    @classmethod
    def stream_for(cls, subject: "Subjects") -> str:
        prefix = subject.value.split(".")[0]
        return SUBJECT_TO_STREAM[prefix]


SUBJECT_TO_STREAM: dict[str, str] = {
    "tenant": "TENANTS",
    "brief": "BRIEFS",
    "icp": "BRIEFS",
    "contacts": "BRIEFS",
    "message": "BRIEFS",
    "reply": "BRIEFS",
    "experiment": "BRIEFS",
    "llm": "LLM_CALLS",
    "cost": "LLM_CALLS",
    "system": "SYSTEM",
}
