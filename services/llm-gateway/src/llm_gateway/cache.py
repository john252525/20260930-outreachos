"""Redis-backed response cache."""

import hashlib
import json
from typing import Any

from redis.asyncio import Redis

from llm_gateway.schemas import CompleteRequest


def prompt_hash(req: CompleteRequest, provider: str = "") -> str:
    payload = {
        "provider": provider,
        "system": req.system,
        "user": req.user,
        "model": req.model,
        "temperature": req.temperature,
        "max_tokens": req.max_tokens,
        "json_mode": req.json_mode,
    }
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    return hashlib.sha256(blob).hexdigest()


async def cache_get(redis: "Redis[str]", key: str) -> dict[str, Any] | None:
    raw = await redis.get(f"llm:cache:{key}")
    if raw is None:
        return None
    return dict(json.loads(raw))


async def cache_set(
    redis: "Redis[str]", key: str, value: dict[str, Any], *, ttl: int = 86400
) -> None:
    await redis.setex(f"llm:cache:{key}", ttl, json.dumps(value, ensure_ascii=False))
