"""Dev-console FastAPI application."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import nats
import structlog
from fastapi import FastAPI
from fastapi.responses import FileResponse

from common.logging import configure_logging
from dev_console.api.routes import router as api_router
from dev_console.config import Settings
from dev_console.nats_viewer import NATSViewer
from dev_console.proxy import ServiceProxy

logger = structlog.get_logger()

STATIC_DIR = Path(__file__).parent / "static"


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
        }
    )
    nc = await nats.connect(settings.nats_url, name=settings.service_name)

    app.state.settings = settings
    app.state.proxy = proxy
    app.state.viewer = NATSViewer(nc)

    logger.info("service_started", service=settings.service_name)
    try:
        yield
    finally:
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

    return app


app = create_app()
