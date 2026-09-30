"""Stop-list logic (global + tenant-scoped)."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from contact_store.models import StopListEntry


class StopList:
    """Check and manage the stop-list."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def is_blocked(
        self,
        *,
        tenant_id: UUID,
        email: str | None = None,
        phone: str | None = None,
        domain: str | None = None,
    ) -> tuple[bool, str | None]:
        """Return (is_blocked, reason).

        RLS exposes global entries (tenant_id IS NULL) plus the tenant's own.
        """
        checks: list[tuple[str, str]] = []
        if email:
            checks.append(("email", email))
        if phone:
            checks.append(("phone", phone))
        if domain:
            checks.append(("domain", domain))

        if not checks:
            return False, None

        for kind, value in checks:
            stmt = select(StopListEntry).where(
                StopListEntry.kind == kind,
                StopListEntry.value == value,
            )
            entry = (await self._s.execute(stmt)).scalar_one_or_none()
            if entry is not None:
                return True, entry.reason
        return False, None

    async def add(
        self,
        *,
        tenant_id: UUID,
        kind: str,
        value: str,
        reason: str,
        note: str | None = None,
        created_by: str = "system",
        scope: str = "tenant",
    ) -> StopListEntry:
        """Add an entry. scope='global' is for the system role only."""
        entry = StopListEntry(
            tenant_id=tenant_id if scope == "tenant" else None,
            scope=scope,
            kind=kind,
            value=value,
            reason=reason,
            note=note,
            created_by=created_by,
        )
        self._s.add(entry)
        await self._s.flush()
        return entry

    async def remove(self, entry_id: UUID) -> bool:
        entry = await self._s.get(StopListEntry, entry_id)
        if entry is None:
            return False
        await self._s.delete(entry)
        return True

    async def list(
        self,
        *,
        kind: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[StopListEntry]:
        stmt = select(StopListEntry)
        if kind:
            stmt = stmt.where(StopListEntry.kind == kind)
        stmt = stmt.order_by(StopListEntry.created_at.desc()).limit(limit).offset(offset)
        return list((await self._s.execute(stmt)).scalars().all())
