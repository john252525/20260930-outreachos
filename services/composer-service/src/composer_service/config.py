"""Composer service settings."""

from pydantic import Field

from common.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = Field(default="composer-service", alias="SERVICE_NAME")
    contact_store_url: str = Field(default="http://contact-store:8000", alias="CONTACT_STORE_URL")
    brief_service_url: str = Field(default="http://brief-service:8000", alias="BRIEF_SERVICE_URL")
    icp_service_url: str = Field(default="http://icp-service:8000", alias="ICP_SERVICE_URL")
    llm_gateway_url: str = Field(default="http://llm-gateway:8000", alias="LLM_GATEWAY_URL")

    # LLM
    llm_model: str = Field(default="deepseek-flash", alias="COMPOSER_LLM_MODEL")
    llm_temperature: float = Field(default=0.6, alias="COMPOSER_LLM_TEMPERATURE")
    llm_max_tokens: int = Field(default=2048, alias="COMPOSER_LLM_MAX_TOKENS")

    # Generation limits
    max_subject_length: int = Field(default=80, alias="COMPOSER_MAX_SUBJECT_LENGTH")
    max_body_words: int = Field(default=250, alias="COMPOSER_MAX_BODY_WORDS")
    min_body_words: int = Field(default=40, alias="COMPOSER_MIN_BODY_WORDS")
    max_concurrent_llm: int = Field(default=5, alias="COMPOSER_MAX_CONCURRENT_LLM")

    # Fact checking
    min_fact_confidence: float = Field(default=0.6, alias="COMPOSER_MIN_FACT_CONFIDENCE")
    strict_fact_check: bool = Field(default=True, alias="COMPOSER_STRICT_FACT_CHECK")

    # Defaults
    default_language: str = Field(default="ru", alias="COMPOSER_DEFAULT_LANGUAGE")
