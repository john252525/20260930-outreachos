"""Dev-console FastAPI application."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import nats
import structlog
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from common.logging import configure_logging
from dev_console.api.routes import router as api_router
from dev_console.config import Settings
from dev_console.nats_viewer import NATSViewer
from dev_console.proxy import ServiceProxy
from dev_console.tenants_db import TenantLister

logger = structlog.get_logger()

STATIC_DIR = Path(__file__).parent / "static"

_SWAGGER_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>__SERVICE__ — OpenAPI</title>
<link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
</head>
<body>
<div id="swagger-ui"></div>
<script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
<script>
window.onload = () => {
  window.ui = SwaggerUIBundle({ url: "/docs/__SERVICE__/openapi.json", dom_id: "#swagger-ui" });
};
</script>
</body>
</html>"""


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = Settings()
    configure_logging(level=settings.log_level, service_name=settings.service_name)

    proxy = ServiceProxy(
        {
            "tenant-service": settings.tenant_service_url,
            "brief-service": settings.brief_service_url,
            "llm-gateway": settings.llm_gateway_url,
            "contact-store": settings.contact_store_url,
            "icp-service": settings.icp_service_url,
            "sourcing-service": settings.sourcing_service_url,
            "composer-service": settings.composer_service_url,
            "review-queue": settings.review_queue_url,
            "sender-email": settings.sender_email_url,
            "reply-classifier": settings.reply_classifier_url,
            "analytics-service": settings.analytics_service_url,
            "experiments-service": settings.experiments_service_url,
        }
    )
    nc = await nats.connect(settings.nats_url, name=settings.service_name)

    tenant_lister = TenantLister(settings.database_url_admin)
    await tenant_lister.connect()

    app.state.settings = settings
    app.state.tenant_lister = tenant_lister
    app.state.proxy = proxy
    app.state.viewer = NATSViewer(nc)

    logger.info("service_started", service=settings.service_name)
    try:
        yield
    finally:
        await tenant_lister.close()
        await nc.close()
        await proxy.close()
        logger.info("service_stopped")


def create_app() -> FastAPI:
    app = FastAPI(title="Outreach Dev Console", version="0.1.0", lifespan=lifespan)
    app.include_router(api_router)

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/healthz", include_in_schema=False)
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/docs/{service}", include_in_schema=False)
    async def service_docs(service: str, request: Request) -> HTMLResponse:
        request.app.state.proxy.url_for(service)
        return HTMLResponse(_SWAGGER_HTML.replace("__SERVICE__", service))

    @app.get("/docs/{service}/openapi.json", include_in_schema=False)
    async def service_openapi(service: str, request: Request) -> JSONResponse:
        proxy = request.app.state.proxy
        status, body = await proxy.get(service, "/openapi.json")
        return JSONResponse(content=body, status_code=status)

    return app


app = create_app()
