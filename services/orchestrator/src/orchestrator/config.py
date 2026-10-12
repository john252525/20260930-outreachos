"""Orchestrator settings."""

from pydantic import Field

from common.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = Field(default="orchestrator", alias="SERVICE_NAME")

    # Owner DSN for cross-tenant listing (retry worker) — ADR-017.
    database_url_admin: str = Field(default="", alias="DATABASE_URL_ADMIN")

    # Service URLs
    icp_service_url: str = Field(default="http://icp-service:8000", alias="ICP_SERVICE_URL")
    sourcing_service_url: str = Field(
        default="http://sourcing-service:8000", alias="SOURCING_SERVICE_URL"
    )
    composer_service_url: str = Field(
        default="http://composer-service:8000", alias="COMPOSER_SERVICE_URL"
    )
    review_queue_url: str = Field(default="http://review-queue:8000", alias="REVIEW_QUEUE_URL")
    contact_store_url: str = Field(default="http://contact-store:8000", alias="CONTACT_STORE_URL")
    brief_service_url: str = Field(default="http://brief-service:8000", alias="BRIEF_SERVICE_URL")
    sender_email_url: str = Field(default="http://sender-email:8000", alias="SENDER_EMAIL_URL")
    revision_service_url: str = Field(
        default="http://auto-revision:8000", alias="REVISION_SERVICE_URL"
    )

    # Automation levels
    auto_brief_to_icp: bool = Field(default=True, alias="ORCH_AUTO_BRIEF_TO_ICP")
    auto_icp_to_sourcing: bool = Field(default=True, alias="ORCH_AUTO_ICP_TO_SOURCING")
    auto_contacts_to_drafts: bool = Field(default=False, alias="ORCH_AUTO_CONTACTS_TO_DRAFTS")
    auto_drafts_to_review: bool = Field(default=True, alias="ORCH_AUTO_DRAFTS_TO_REVIEW")
    auto_approved_to_send: bool = Field(default=True, alias="ORCH_AUTO_APPROVED_TO_SEND")
    auto_revision_enabled: bool = Field(default=False, alias="ORCH_AUTO_REVISION_ENABLED")

    # Sourcing default params
    default_sources: list[str] = Field(
        default_factory=lambda: ["serper"], alias="ORCH_DEFAULT_SOURCES"
    )
    default_limit_per_source: int = Field(default=50, alias="ORCH_DEFAULT_LIMIT_PER_SOURCE")
    max_sources_per_search: int = Field(default=3, alias="ORCH_MAX_SEGMENTS_PER_SEARCH")

    # Draft default params
    default_max_contacts_per_flow: int = Field(100, alias="ORCH_DEFAULT_MAX_CONTACTS")
    default_channel: str = Field(default="email", alias="ORCH_DEFAULT_CHANNEL")

    # Retry
    max_step_retries: int = Field(default=3, alias="ORCH_MAX_STEP_RETRIES")
    retry_delay_seconds: int = Field(default=60, alias="ORCH_RETRY_DELAY")
    retry_poll_interval_seconds: int = Field(default=30, alias="ORCH_RETRY_POLL_INTERVAL")

    # NATS
    nats_durable_name: str = Field(default="orchestrator", alias="NATS_DURABLE_NAME")
