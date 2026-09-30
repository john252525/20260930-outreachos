"""NATS JetStream connection manager."""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import nats
from nats.aio.client import Client as NATSClient
from nats.js import JetStreamContext
from nats.js.errors import NotFoundError

from nats_client.streams import STREAMS

logger = logging.getLogger(__name__)


class NATSConnection:
    """Manages a NATS connection and bootstraps JetStream streams."""

    def __init__(self, url: str, *, name: str = "outreach-service") -> None:
        self._url = url
        self._name = name
        self._nc: NATSClient | None = None
        self._js: JetStreamContext | None = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        async with self._lock:
            if self._nc is not None and not self._nc.is_closed:
                return
            self._nc = await nats.connect(
                self._url,
                name=self._name,
                reconnect_time_wait=2,
                max_reconnect_attempts=60,
                error_cb=self._on_error,
                disconnected_cb=self._on_disconnected,
                reconnected_cb=self._on_reconnected,
            )
            self._js = self._nc.jetstream()
            await self._bootstrap_streams()
            logger.info("Connected to NATS: %s", self._url)

    async def _bootstrap_streams(self) -> None:
        assert self._js is not None
        for cfg in STREAMS:
            try:
                await self._js.stream_info(cfg.name)
            except NotFoundError:
                await self._js.add_stream(
                    name=cfg.name,
                    subjects=cfg.subjects,
                    max_age=cfg.max_age_seconds,
                    max_bytes=cfg.max_bytes,
                    storage=cfg.storage,
                    retention=cfg.retention,
                )
                logger.info("Created stream: %s", cfg.name)

    async def close(self) -> None:
        if self._nc is not None and not self._nc.is_closed:
            await self._nc.drain()
            self._nc = None
            self._js = None

    @property
    def js(self) -> JetStreamContext:
        if self._js is None:
            raise RuntimeError("NATS not connected. Call connect() first.")
        return self._js

    async def _on_error(self, e: Exception) -> None:
        logger.error("NATS error: %s", e)

    async def _on_disconnected(self) -> None:
        logger.warning("NATS disconnected")

    async def _on_reconnected(self) -> None:
        logger.info("NATS reconnected")


@asynccontextmanager
async def nats_connection(url: str, *, name: str) -> AsyncIterator[NATSConnection]:
    """Async context manager yielding a connected NATSConnection."""
    conn = NATSConnection(url, name=name)
    await conn.connect()
    try:
        yield conn
    finally:
        await conn.close()
