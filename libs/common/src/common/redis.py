"""Redis client singleton."""

from redis.asyncio import Redis, from_url

_redis: "Redis[str] | None" = None


def init_redis(url: str) -> "Redis[str]":
    global _redis
    _redis = from_url(url, encoding="utf-8", decode_responses=True)
    return _redis


def get_redis() -> "Redis[str]":
    if _redis is None:
        raise RuntimeError("Redis not initialized")
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()  # type: ignore[attr-defined]
        _redis = None
