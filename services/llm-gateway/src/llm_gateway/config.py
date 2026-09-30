"""LLM gateway settings."""

from pydantic import Field

from common.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = Field(default="llm-gateway", alias="SERVICE_NAME")

    default_provider: str = Field(default="deepseek", alias="DEFAULT_PROVIDER")

    deepseek_api_key: str = Field(default="", alias="DEEPSEEK_API_KEY")
    deepseek_base_url: str = Field(default="https://api.deepseek.com", alias="DEEPSEEK_BASE_URL")
    llm_default_model: str = Field(default="deepseek-flash", alias="LLM_DEFAULT_MODEL")

    llm_cache_ttl: int = Field(default=86400, alias="LLM_CACHE_TTL")
    llm_timeout_seconds: int = Field(default=180, alias="LLM_TIMEOUT_SECONDS")

    langfuse_public_key: str = Field(default="", alias="LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key: str = Field(default="", alias="LANGFUSE_SECRET_KEY")
    langfuse_base_url: str = Field(default="https://cloud.langfuse.com", alias="LANGFUSE_BASE_URL")

    @property
    def langfuse_enabled(self) -> bool:
        return bool(self.langfuse_public_key and self.langfuse_secret_key)
