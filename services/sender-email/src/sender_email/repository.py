"""Data access layer for sender-email."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sender_email.models import SendAttempt, SenderAccount


class SenderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    @property
    def session(self) -> AsyncSession:
        return self._s

    async def get_account(self, account_id: UUID) -> SenderAccount | None:
        return await self._s.get(SenderAccount, account_id)

    async def get_account_by_email(self, tenant_id: UUID, email: str) -> SenderAccount | None:
        stmt = select(SenderAccount).where(
            SenderAccount.tenant_id == tenant_id, SenderAccount.email == email
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def list_accounts(self, tenant_id: UUID) -> list[SenderAccount]:
        stmt = (
            select(SenderAccount)
            .where(SenderAccount.tenant_id == tenant_id)
            .order_by(SenderAccount.created_at.desc())
        )
        return list((await self._s.execute(stmt)).scalars().all())

    async def list_active_accounts(self) -> list[SenderAccount]:
        stmt = select(SenderAccount).where(SenderAccount.status == "active")
        return list((await self._s.execute(stmt)).scalars().all())

    async def add_account(self, account: SenderAccount) -> SenderAccount:
        self._s.add(account)
        await self._s.flush()
        return account

    async def select_account(
        self, tenant_id: UUID, *, user_id: str | None = None
    ) -> SenderAccount | None:
        """Select an active mailbox: prefer the specified user's account."""
        stmt = select(SenderAccount).where(
            SenderAccount.tenant_id == tenant_id, SenderAccount.status == "active"
        )
        if user_id:
            stmt = stmt.where(SenderAccount.user_id == user_id)
        account = (await self._s.execute(stmt)).scalars().first()
        if account is None and user_id:
            stmt2 = select(SenderAccount).where(
                SenderAccount.tenant_id == tenant_id, SenderAccount.status == "active"
            )
            account = (await self._s.execute(stmt2)).scalars().first()
        return account

    async def add_attempt(self, attempt: SendAttempt) -> SendAttempt:
        self._s.add(attempt)
        await self._s.flush()
        return attempt

    async def find_attempt_by_smtp_message_id(self, smtp_message_id: str) -> SendAttempt | None:
        stmt = select(SendAttempt).where(SendAttempt.smtp_message_id == smtp_message_id)
        return (await self._s.execute(stmt)).scalars().first()
