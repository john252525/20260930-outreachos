"""Brief service settings."""

from pydantic import Field

from common.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = Field(default="brief-service", alias="SERVICE_NAME")
    llm_gateway_url: str = Field(default="http://llm-gateway:8000", alias="LLM_GATEWAY_URL")

    # Intake limits
    max_raw_text_length: int = Field(default=50_000, alias="BRIEF_MAX_RAW_TEXT_LENGTH")
    max_urls_per_request: int = Field(default=10, alias="BRIEF_MAX_URLS")
    max_questions_per_iteration: int = Field(default=1, alias="BRIEF_MAX_QUESTIONS_PER_ITER")
    completeness_threshold: float = Field(default=0.85, alias="BRIEF_COMPLETENESS_THRESHOLD")

    # LLM
    llm_model: str = Field(default="deepseek-flash", alias="BRIEF_LLM_MODEL")
    llm_temperature: float = Field(default=0.3, alias="BRIEF_LLM_TEMPERATURE")
    llm_max_tokens: int = Field(default=4096, alias="BRIEF_LLM_MAX_TOKENS")
