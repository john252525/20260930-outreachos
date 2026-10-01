"""Dev-console API."""

from typing import Any

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api", tags=["console"])

SERVICE_NAMES = ["tenant-service", "brief-service", "llm-gateway", "contact-store", "icp-service"]


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
