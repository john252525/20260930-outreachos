"""Dev-console API."""

from typing import Any

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api", tags=["console"])

SERVICE_NAMES = [
    "tenant-service",
    "brief-service",
    "llm-gateway",
    "contact-store",
    "icp-service",
    "sourcing-service",
    "composer-service",
    "review-queue",
    "sender-email",
    "reply-classifier",
    "analytics-service",
    "experiments-service",
    "orchestrator",
    "auto-revision",
    "telegram-sender",
]


@router.get("/services")
async def services(request: Request) -> list[dict[str, Any]]:
    proxy = request.app.state.proxy
    results = []
    for name in SERVICE_NAMES:
        info = await proxy.health(name)
        info["docs"] = f"/docs/{name}"
        results.append(info)
    return results


@router.get("/tenants")
async def list_tenants(request: Request) -> Any:
    lister = request.app.state.tenant_lister
    try:
        tenants = await lister.list()
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=502)
    for t in tenants:
        if t.get("id") is not None:
            t["id"] = str(t["id"])
        if t.get("created_at") is not None:
            t["created_at"] = t["created_at"].isoformat()
    return tenants


@router.post("/tenants")
async def create_tenant(request: Request) -> Any:
    payload = await request.json()
    proxy = request.app.state.proxy
    status, body = await proxy.post("tenant-service", "/tenants", json=payload)
    return JSONResponse(content=body, status_code=status)


@router.get("/streams")
async def streams(request: Request) -> Any:
    viewer = request.app.state.viewer
    return await viewer.streams()


@router.get("/events")
async def events(
    request: Request,
    stream: str = Query("BRIEFS"),
    subject: str = Query(">"),
    limit: int = Query(25, ge=1, le=200),
) -> Any:
    viewer = request.app.state.viewer
    return await viewer.recent_messages(stream=stream, subject=subject, limit=limit)


@router.get("/data/companies")
async def data_companies(
    request: Request,
    tenant: str = Query(...),
    limit: int = Query(50, ge=1, le=200),
) -> Any:
    proxy = request.app.state.proxy
    status, body = await proxy.get(
        "contact-store", "/companies", tenant_id=tenant, params={"limit": limit}
    )
    return JSONResponse(content=body, status_code=status)


@router.get("/data/contacts")
async def data_contacts(
    request: Request,
    tenant: str = Query(...),
    limit: int = Query(50, ge=1, le=200),
) -> Any:
    proxy = request.app.state.proxy
    status, body = await proxy.get(
        "contact-store", "/contacts", tenant_id=tenant, params={"limit": limit}
    )
    return JSONResponse(content=body, status_code=status)


@router.get("/data/briefs")
async def data_briefs(
    request: Request,
    tenant: str = Query(...),
    limit: int = Query(50, ge=1, le=200),
) -> Any:
    proxy = request.app.state.proxy
    status, body = await proxy.get(
        "brief-service", "/briefs", tenant_id=tenant, params={"limit": limit}
    )
    return JSONResponse(content=body, status_code=status)


@router.get("/data/review-items")
async def data_review_items(
    request: Request,
    tenant: str = Query(...),
    limit: int = Query(50, ge=1, le=200),
) -> Any:
    proxy = request.app.state.proxy
    status, body = await proxy.get(
        "review-queue",
        "/review-items",
        tenant_id=tenant,
        params={"status": "pending", "limit": limit},
    )
    return JSONResponse(content=body, status_code=status)


@router.get("/data/messages")
async def data_messages(
    request: Request,
    tenant: str = Query(...),
    limit: int = Query(50, ge=1, le=200),
) -> Any:
    proxy = request.app.state.proxy
    status, body = await proxy.get(
        "composer-service", "/messages", tenant_id=tenant, params={"limit": limit}
    )
    return JSONResponse(content=body, status_code=status)


@router.get("/data/searches")
async def data_searches(
    request: Request,
    tenant: str = Query(...),
    limit: int = Query(50, ge=1, le=200),
) -> Any:
    proxy = request.app.state.proxy
    status, body = await proxy.get(
        "sourcing-service", "/searches", tenant_id=tenant, params={"limit": limit}
    )
    return JSONResponse(content=body, status_code=status)


@router.get("/data/icps")
async def data_icps(
    request: Request,
    tenant: str = Query(...),
    limit: int = Query(50, ge=1, le=200),
) -> Any:
    proxy = request.app.state.proxy
    status, body = await proxy.get(
        "icp-service", "/icps", tenant_id=tenant, params={"limit": limit}
    )
    return JSONResponse(content=body, status_code=status)


@router.get("/data/stoplist")
async def data_stoplist(
    request: Request,
    tenant: str = Query(...),
    limit: int = Query(100, ge=1, le=500),
) -> Any:
    proxy = request.app.state.proxy
    status, body = await proxy.get(
        "contact-store", "/stoplist", tenant_id=tenant, params={"limit": limit}
    )
    return JSONResponse(content=body, status_code=status)


@router.get("/data/replies")
async def data_replies(
    request: Request,
    tenant: str = Query(...),
    limit: int = Query(50, ge=1, le=200),
) -> Any:
    proxy = request.app.state.proxy
    status, body = await proxy.get(
        "reply-classifier", "/replies", tenant_id=tenant, params={"limit": limit}
    )
    return JSONResponse(content=body, status_code=status)


@router.get("/data/experiments")
async def data_experiments(
    request: Request,
    tenant: str = Query(...),
    limit: int = Query(50, ge=1, le=200),
) -> Any:
    proxy = request.app.state.proxy
    status, body = await proxy.get(
        "experiments-service", "/experiments", tenant_id=tenant, params={"limit": limit}
    )
    return JSONResponse(content=body, status_code=status)


@router.get("/data/funnel")
async def data_funnel(
    request: Request,
    tenant: str = Query(...),
) -> Any:
    proxy = request.app.state.proxy
    status, body = await proxy.get("analytics-service", "/analytics/funnel", tenant_id=tenant)
    return JSONResponse(content=body, status_code=status)


@router.get("/data/analytics-overview")
async def data_analytics_overview(
    request: Request,
    tenant: str = Query(...),
) -> Any:
    proxy = request.app.state.proxy
    status, body = await proxy.get("analytics-service", "/analytics/overview", tenant_id=tenant)
    return JSONResponse(content=body, status_code=status)


@router.get("/data/flows")
async def data_flows(
    request: Request,
    tenant: str = Query(...),
    limit: int = Query(50, ge=1, le=200),
) -> Any:
    proxy = request.app.state.proxy
    status, body = await proxy.get(
        "orchestrator", "/flows", tenant_id=tenant, params={"limit": limit}
    )
    return JSONResponse(content=body, status_code=status)


@router.get("/data/flow-steps")
async def data_flow_steps(
    request: Request,
    tenant: str = Query(...),
    flow_id: str = Query(...),
) -> Any:
    proxy = request.app.state.proxy
    status, body = await proxy.get("orchestrator", f"/flows/{flow_id}/steps", tenant_id=tenant)
    return JSONResponse(content=body, status_code=status)


@router.get("/data/revisions")
async def data_revisions(
    request: Request,
    tenant: str = Query(...),
    limit: int = Query(50, ge=1, le=200),
) -> Any:
    proxy = request.app.state.proxy
    status, body = await proxy.get(
        "auto-revision", "/revisions", tenant_id=tenant, params={"limit": limit}
    )
    return JSONResponse(content=body, status_code=status)


@router.get("/data/telegram-accounts")
async def data_telegram_accounts(
    request: Request,
    tenant: str = Query(...),
) -> Any:
    proxy = request.app.state.proxy
    status, body = await proxy.get("telegram-sender", "/accounts", tenant_id=tenant)
    return JSONResponse(content=body, status_code=status)


@router.get("/data/telegram-attempts")
async def data_telegram_attempts(
    request: Request,
    tenant: str = Query(...),
    limit: int = Query(50, ge=1, le=200),
) -> Any:
    proxy = request.app.state.proxy
    status, body = await proxy.get(
        "telegram-sender", "/attempts", tenant_id=tenant, params={"limit": limit}
    )
    return JSONResponse(content=body, status_code=status)
