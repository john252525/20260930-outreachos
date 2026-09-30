"""Health and readiness endpoints."""

from typing import Any

from fastapi import APIRouter

from common.redis import get_redis

router = APIRouter()


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
async def readyz() -> dict[str, Any]:
    checks: dict[str, str] = {}
    try:
        redis = get_redis()
        await redis.ping()
        checks["redis"] = "ok"
    except Exception as e:  # pragma: no cover - defensive
        checks["redis"] = f"fail: {e}"

    overall = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    return {"status": overall, "checks": checks}
