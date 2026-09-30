"""Read-only tenant listing for the dev console.

Listing *all* tenants is a system-level operation: under RLS the application
role only sees the tenant it is scoped to. As a dev-only inspector, the
console reads the tenant list directly from Postgres through a dedicated
(read-only) admin connection.
"""

from typing import Any

import asyncpg
import structlog

logger = structlog.get_logger()


class TenantLister:
    def __init__(self, admin_dsn: str) -> None:
        self._dsn = admin_dsn
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        self._pool = await asyncpg.create_pool(self._dsn, min_size=1, max_size=3)

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()

    async def list(self, *, limit: int = 200) -> list[dict[str, Any]]:
        if self._pool is None:
            raise RuntimeError("TenantLister not connected")
        rows = await self._pool.fetch(
            """
            SELECT id, name, slug, status, is_sandbox, created_at
            FROM tenants
            ORDER BY created_at DESC
            LIMIT $1
            """,
            limit,
        )
        return [dict(r) for r in rows]
