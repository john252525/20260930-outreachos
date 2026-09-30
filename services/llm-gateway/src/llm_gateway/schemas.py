"""API schemas for llm-gateway."""

from pydantic import BaseModel, ConfigDict, Field


class CompleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_type: str = Field(min_length=1, max_length=64)
    system: str | None = None
    user: str = Field(min_length=1)
    model: str = "deepseek-flash"
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=1, le=32768)
    json_mode: bool = False
    use_cache: bool = True


class CompleteResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    text: str
    model: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    latency_ms: int
    cached: bool = False
