"""Minimal stand-in for llm-gateway used by CI/offline tests.

Run with:  uvicorn tests.fake_llm_gateway:app --port 8001
"""

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Fake LLM Gateway")


class CompleteRequest(BaseModel):
    task_type: str
    system: str | None = None
    user: str
    model: str = "deepseek-flash"
    temperature: float = 0.7
    max_tokens: int = 4096
    json_mode: bool = False
    use_cache: bool = False


@app.post("/v1/complete")
async def complete(req: CompleteRequest) -> dict[str, object]:
    if "brief_extract" in req.task_type:
        text = (
            '{"identity":{"project_name":"Test","language":"ru","geo_primary":["RU"],'
            '"industry":"IT"},"offering":{"what_we_sell":"Test"},'
            '"targeting_hints":{},"outreach_goals":{"primary_goal":"lead_gen"}}'
        )
    elif "generate_questions" in req.task_type:
        text = (
            '{"questions":[{"question":"Уточните отрасль клиентов?",'
            '"why_needed":"для таргетинга","target_field":"identity.industry",'
            '"priority":"high"}]}'
        )
    else:
        text = "ok"
    return {
        "text": text,
        "model": req.model,
        "tokens_in": 10,
        "tokens_out": 5,
        "cost_usd": 0.0,
        "latency_ms": 100,
    }
