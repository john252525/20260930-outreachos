"""Data access layer for telegram-sender."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from telegram_sender.models import TelegramAccount, TelegramSendAttempt


class TelegramRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    @property
    def session(self) -> AsyncSession:
        return self._s

    async def get_account(self, account_id: UUID) -> TelegramAccount | None:
        return await self._s.get(TelegramAccount, account_id)

    async def list_accounts(self, tenant_id: UUID) -> list[TelegramAccount]:
        stmt = (
            select(TelegramAccount)
            .where(TelegramAccount.tenant_id == tenant_id)
            .order_by(TelegramAccount.created_at.desc())
        )
        return list((await self._s.execute(stmt)).scalars().all())

    async def select_account(self, tenant_id: UUID) -> TelegramAccount | None:
        stmt = (
            select(TelegramAccount)
            .where(
                TelegramAccount.tenant_id == tenant_id,
                TelegramAccount.status == "active",
            )
            .order_by(TelegramAccount.created_at.asc())
        )
        return (await self._s.execute(stmt)).scalars().first()

    async def add_account(self, account: TelegramAccount) -> TelegramAccount:
        self._s.add(account)
        await self._s.flush()
        return account

    async def add_attempt(self, attempt: TelegramSendAttempt) -> TelegramSendAttempt:
        self._s.add(attempt)
        await self._s.flush()
        return attempt

    async def list_attempts(self, tenant_id: UUID, *, limit: int = 50) -> list[TelegramSendAttempt]:
        stmt = (
            select(TelegramSendAttempt)
            .where(TelegramSendAttempt.tenant_id == tenant_id)
            .order_by(TelegramSendAttempt.created_at.desc())
            .limit(limit)
        )
        return list((await self._s.execute(stmt)).scalars().all())
