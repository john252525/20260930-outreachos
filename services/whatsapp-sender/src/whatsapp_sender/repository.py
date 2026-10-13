"""Data access layer for whatsapp-sender."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from whatsapp_sender.models import (
    WhatsAppAccount,
    WhatsAppSendAttempt,
    WhatsAppTemplate,
)


class WhatsAppRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    @property
    def session(self) -> AsyncSession:
        return self._s

    async def get_account(self, account_id: UUID) -> WhatsAppAccount | None:
        return await self._s.get(WhatsAppAccount, account_id)

    async def list_accounts(self, tenant_id: UUID) -> list[WhatsAppAccount]:
        stmt = (
            select(WhatsAppAccount)
            .where(WhatsAppAccount.tenant_id == tenant_id)
            .order_by(WhatsAppAccount.created_at.desc())
        )
        return list((await self._s.execute(stmt)).scalars().all())

    async def select_account(self, tenant_id: UUID) -> WhatsAppAccount | None:
        stmt = (
            select(WhatsAppAccount)
            .where(WhatsAppAccount.tenant_id == tenant_id, WhatsAppAccount.status == "active")
            .order_by(WhatsAppAccount.created_at.asc())
        )
        return (await self._s.execute(stmt)).scalars().first()

    async def add_account(self, account: WhatsAppAccount) -> WhatsAppAccount:
        self._s.add(account)
        await self._s.flush()
        return account

    async def add_attempt(self, attempt: WhatsAppSendAttempt) -> WhatsAppSendAttempt:
        self._s.add(attempt)
        await self._s.flush()
        return attempt

    async def list_attempts(self, tenant_id: UUID, *, limit: int = 50) -> list[WhatsAppSendAttempt]:
        stmt = (
            select(WhatsAppSendAttempt)
            .where(WhatsAppSendAttempt.tenant_id == tenant_id)
            .order_by(WhatsAppSendAttempt.created_at.desc())
            .limit(limit)
        )
        return list((await self._s.execute(stmt)).scalars().all())

    async def add_template(self, template: WhatsAppTemplate) -> WhatsAppTemplate:
        self._s.add(template)
        await self._s.flush()
        return template

    async def list_templates(self, tenant_id: UUID) -> list[WhatsAppTemplate]:
        stmt = (
            select(WhatsAppTemplate)
            .where(WhatsAppTemplate.tenant_id == tenant_id)
            .order_by(WhatsAppTemplate.created_at.desc())
        )
        return list((await self._s.execute(stmt)).scalars().all())

    async def get_template_to_send(self, tenant_id: UUID) -> WhatsAppTemplate | None:
        stmt = (
            select(WhatsAppTemplate)
            .where(WhatsAppTemplate.tenant_id == tenant_id, WhatsAppTemplate.status == "approved")
            .order_by(WhatsAppTemplate.created_at.desc())
        )
        return (await self._s.execute(stmt)).scalars().first()
