"""Auto-revision settings."""

from pydantic import Field

from common.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = Field(default="auto-revision", alias="SERVICE_NAME")

    llm_gateway_url: str = Field(default="http://llm-gateway:8000", alias="LLM_GATEWAY_URL")
    analytics_service_url: str = Field(
        default="http://analytics-service:8000", alias="ANALYTICS_SERVICE_URL"
    )
    experiments_service_url: str = Field(
        default="http://experiments-service:8000", alias="EXPERIMENTS_SERVICE_URL"
    )
    composer_service_url: str = Field(
        default="http://composer-service:8000", alias="COMPOSER_SERVICE_URL"
    )

    # LLM
    llm_model: str = Field(default="deepseek-flash", alias="REVISION_LLM_MODEL")
    llm_temperature: float = Field(default=0.4, alias="REVISION_LLM_TEMPERATURE")
    llm_max_tokens: int = Field(default=4096, alias="REVISION_LLM_MAX_TOKENS")

    # Analysis
    analysis_window_days: int = Field(default=30, alias="REVISION_WINDOW_DAYS")
    min_confidence: float = Field(default=0.6, alias="REVISION_MIN_CONFIDENCE")
    max_sample_emails: int = Field(default=10, alias="REVISION_MAX_SAMPLE_EMAILS")

    # Experiments
    experiment_sample_size_per_variant: int = Field(
        default=200, alias="REVISION_EXPERIMENT_SAMPLE_PER_VARIANT"
    )

    # NATS
    nats_durable_name: str = Field(default="auto-revision", alias="NATS_DURABLE_NAME")
