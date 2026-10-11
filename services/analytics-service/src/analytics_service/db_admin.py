"""Admin (owner) engine for analytics-service.

See ADR-017: analytics reads via the owner DSN so REFRESH MATERIALIZED VIEW
sees all tenants. Tenant isolation is enforced by explicit ``tenant_id`` filters
in every query.
"""

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

_engine: AsyncEngine | None = None
_factory: async_sessionmaker[AsyncSession] | None = None


def init_admin_engine(database_url: str) -> AsyncEngine:
    global _engine, _factory
    _engine = create_async_engine(
        database_url,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=3600,
    )
    _factory = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)
    return _engine


def admin_session_factory() -> async_sessionmaker[AsyncSession]:
    if _factory is None:
        raise RuntimeError("Admin engine not initialized. Call init_admin_engine() first.")
    return _factory


async def healthcheck_admin() -> bool:
    if _engine is None:
        return False
    from sqlalchemy import text

    async with _engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return True


async def dispose_admin_engine() -> None:
    global _engine, _factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _factory = None
