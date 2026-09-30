"""Row-level security helpers."""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def set_tenant_context(session: AsyncSession, tenant_id: UUID) -> None:
    """Set app.tenant_id for the current transaction (RLS)."""
    await session.execute(
        text("SELECT set_config('app.tenant_id', :tid, true)"),
        {"tid": str(tenant_id)},
    )


async def clear_tenant_context(session: AsyncSession) -> None:
    await session.execute(text("RESET app.tenant_id"))


async def create_rls_policy(
    session: AsyncSession, table: str, *, column: str = "tenant_id"
) -> None:
    """Create an RLS policy for a table (used in migrations/tests)."""
    await session.execute(text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
    await session.execute(
        text(
            f"""
            CREATE POLICY {table}_tenant_isolation ON {table}
            USING ({column} = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
            WITH CHECK ({column} = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
            """
        )
    )
