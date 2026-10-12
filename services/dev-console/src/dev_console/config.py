"""Dev-console settings.

The console is a read-mostly inspector for the dev environment. It proxies
requests to the other services and reads NATS events. It does not touch the
database directly.
"""

from pydantic import Field

from common.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = Field(default="dev-console", alias="SERVICE_NAME")

    tenant_service_url: str = Field(
        default="http://tenant-service:8000", alias="TENANT_SERVICE_URL"
    )
    brief_service_url: str = Field(default="http://brief-service:8000", alias="BRIEF_SERVICE_URL")
    llm_gateway_url: str = Field(default="http://llm-gateway:8000", alias="LLM_GATEWAY_URL")
    contact_store_url: str = Field(default="http://contact-store:8000", alias="CONTACT_STORE_URL")
    icp_service_url: str = Field(default="http://icp-service:8000", alias="ICP_SERVICE_URL")
    sourcing_service_url: str = Field(
        default="http://sourcing-service:8000", alias="SOURCING_SERVICE_URL"
    )
    composer_service_url: str = Field(
        default="http://composer-service:8000", alias="COMPOSER_SERVICE_URL"
    )
    review_queue_url: str = Field(default="http://review-queue:8000", alias="REVIEW_QUEUE_URL")
    sender_email_url: str = Field(default="http://sender-email:8000", alias="SENDER_EMAIL_URL")
    reply_classifier_url: str = Field(
        default="http://reply-classifier:8000", alias="REPLY_CLASSIFIER_URL"
    )
    analytics_service_url: str = Field(
        default="http://analytics-service:8000", alias="ANALYTICS_SERVICE_URL"
    )
    experiments_service_url: str = Field(
        default="http://experiments-service:8000", alias="EXPERIMENTS_SERVICE_URL"
    )
    orchestrator_url: str = Field(default="http://orchestrator:8000", alias="ORCHESTRATOR_URL")
    auto_revision_url: str = Field(default="http://auto-revision:8000", alias="AUTO_REVISION_URL")
    telegram_sender_url: str = Field(
        default="http://telegram-sender:8000", alias="TELEGRAM_SENDER_URL"
    )
    linkedin_sender_url: str = Field(
        default="http://linkedin-sender:8000", alias="LINKEDIN_SENDER_URL"
    )

    events_default_limit: int = Field(default=25, alias="CONSOLE_EVENTS_LIMIT")

    # Read-only DSN for listing all tenants (system-level, bypasses RLS).
    # Dev-only: this is an inspector tool.
    database_url_admin: str = Field(..., alias="DATABASE_URL_ADMIN")
