"""Data access layer for linkedin-sender."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from linkedin_sender.models import LinkedInAccount, LinkedInSendAttempt


class LinkedInRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    @property
    def session(self) -> AsyncSession:
        return self._s

    async def get_account(self, account_id: UUID) -> LinkedInAccount | None:
        return await self._s.get(LinkedInAccount, account_id)

    async def list_accounts(self, tenant_id: UUID) -> list[LinkedInAccount]:
        stmt = (
            select(LinkedInAccount)
            .where(LinkedInAccount.tenant_id == tenant_id)
            .order_by(LinkedInAccount.created_at.desc())
        )
        return list((await self._s.execute(stmt)).scalars().all())

    async def select_account(self, tenant_id: UUID) -> LinkedInAccount | None:
        stmt = (
            select(LinkedInAccount)
            .where(
                LinkedInAccount.tenant_id == tenant_id,
                LinkedInAccount.status == "active",
            )
            .order_by(LinkedInAccount.created_at.asc())
        )
        return (await self._s.execute(stmt)).scalars().first()

    async def add_account(self, account: LinkedInAccount) -> LinkedInAccount:
        self._s.add(account)
        await self._s.flush()
        return account

    async def add_attempt(self, attempt: LinkedInSendAttempt) -> LinkedInSendAttempt:
        self._s.add(attempt)
        await self._s.flush()
        return attempt

    async def list_attempts(self, tenant_id: UUID, *, limit: int = 50) -> list[LinkedInSendAttempt]:
        stmt = (
            select(LinkedInSendAttempt)
            .where(LinkedInSendAttempt.tenant_id == tenant_id)
            .order_by(LinkedInSendAttempt.created_at.desc())
            .limit(limit)
        )
        return list((await self._s.execute(stmt)).scalars().all())
