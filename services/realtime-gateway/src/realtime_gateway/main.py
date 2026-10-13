"""Realtime-gateway FastAPI application."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

import structlog
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from common.health import router as health_router
from common.logging import configure_logging
from common.middleware.tenant import TenantMiddleware
from common.redis import close_redis, get_redis, init_redis
from nats_client.client import NATSConnection
from realtime_gateway.auth import decode_token
from realtime_gateway.config import Settings
from realtime_gateway.connections import ClientConnection, ConnectionManager
from realtime_gateway.handlers.nats_bridge import NATSBridge
from realtime_gateway.presence import Presence
from realtime_gateway.pubsub import PubSub

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = Settings()
    configure_logging(level=settings.log_level, service_name=settings.service_name)
    init_redis(settings.redis_url)

    manager = ConnectionManager()
    pubsub = PubSub(settings.redis_url, manager)

    nats_conn = NATSConnection(settings.nats_url, name=settings.service_name)
    await nats_conn.connect()

    app.state.settings = settings
    app.state.manager = manager
    app.state.pubsub = pubsub
    app.state.presence = Presence(get_redis(), ttl_seconds=settings.presence_ttl_seconds)

    bridge = NATSBridge(nats_conn, pubsub, durable=settings.nats_durable_name)

    tasks = [
        asyncio.create_task(pubsub.subscribe_forever()),
        asyncio.create_task(bridge.run_forever()),
        asyncio.create_task(bridge.run_flows()),
    ]

    logger.info("service_started", service=settings.service_name)
    try:
        yield
    finally:
        for t in tasks:
            t.cancel()
        await pubsub.close()
        await nats_conn.close()
        await close_redis()
        logger.info("service_stopped")


def create_app() -> FastAPI:
    app = FastAPI(title="Realtime Gateway", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        TenantMiddleware, skip_paths={"/healthz", "/readyz", "/docs", "/openapi.json", "/ws"}
    )
    app.include_router(health_router)

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket, token: str = "") -> None:
        settings = app.state.settings
        try:
            payload = decode_token(token, settings.jwt_secret)
        except Exception:
            await websocket.close(code=4001, reason="invalid_token")
            return

        user_id = UUID(payload["sub"])
        tenant_id = UUID(payload["tenant_id"])
        await websocket.accept()
        connection_id = uuid4()
        conn = ClientConnection(user_id=user_id, tenant_id=tenant_id, websocket=websocket)
        manager: ConnectionManager = app.state.manager
        await manager.connect(conn, connection_id)
        await app.state.presence.set_online(tenant_id, user_id)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            await manager.disconnect(connection_id)
            await app.state.presence.set_offline(tenant_id, user_id)

    @app.get("/presence")
    async def presence() -> JSONResponse:
        from common.context import get_tenant_id

        tenant_id = get_tenant_id()
        if tenant_id is None:
            return JSONResponse({"error": "missing_tenant"}, status_code=400)
        online = await app.state.presence.list_online(tenant_id)
        return JSONResponse({"online": online})

    return app


app = create_app()
