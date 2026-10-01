"""ICP service settings."""

from pydantic import Field

from common.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = Field(default="icp-service", alias="SERVICE_NAME")
    brief_service_url: str = Field(default="http://brief-service:8000", alias="BRIEF_SERVICE_URL")
    llm_gateway_url: str = Field(default="http://llm-gateway:8000", alias="LLM_GATEWAY_URL")

    # LLM
    llm_model: str = Field(default="deepseek-flash", alias="ICP_LLM_MODEL")
    llm_temperature: float = Field(default=0.4, alias="ICP_LLM_TEMPERATURE")
    llm_max_tokens: int = Field(default=16384, alias="ICP_LLM_MAX_TOKENS")

    # Validation
    min_segments: int = Field(default=1, alias="ICP_MIN_SEGMENTS")
    max_segments: int = Field(default=5, alias="ICP_MAX_SEGMENTS")
    min_confidence: float = Field(default=0.6, alias="ICP_MIN_CONFIDENCE")
