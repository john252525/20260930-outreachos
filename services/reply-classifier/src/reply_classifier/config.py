"""Reply-classifier settings."""

from pydantic import Field

from common.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = Field(default="reply-classifier", alias="SERVICE_NAME")
    llm_gateway_url: str = Field(default="http://llm-gateway:8000", alias="LLM_GATEWAY_URL")
    composer_service_url: str = Field(
        default="http://composer-service:8000", alias="COMPOSER_SERVICE_URL"
    )
    contact_store_url: str = Field(default="http://contact-store:8000", alias="CONTACT_STORE_URL")

    # LLM
    llm_model: str = Field(default="deepseek-flash", alias="REPLY_LLM_MODEL")
    llm_temperature: float = Field(default=0.1, alias="REPLY_LLM_TEMPERATURE")
    llm_max_tokens: int = Field(default=1024, alias="REPLY_LLM_MAX_TOKENS")

    # Classification
    min_confidence: float = Field(default=0.6, alias="REPLY_MIN_CONFIDENCE")
    max_body_length: int = Field(default=10_000, alias="REPLY_MAX_BODY_LENGTH")

    # NATS
    nats_durable_name: str = Field(default="reply-classifier", alias="NATS_DURABLE_NAME")
