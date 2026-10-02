"""Data access layer for composer-service."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from composer_service.models import Message


class MessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    @property
    def session(self) -> AsyncSession:
        return self._s

    async def get(self, message_id: UUID) -> Message | None:
        return await self._s.get(Message, message_id)

    async def add(self, message: Message) -> Message:
        self._s.add(message)
        await self._s.flush()
        return message

    async def list(
        self,
        *,
        tenant_id: UUID,
        status: str | None = None,
        contact_id: UUID | None = None,
        channel: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Message]:
        stmt = select(Message).where(Message.tenant_id == tenant_id)
        if status:
            stmt = stmt.where(Message.status == status)
        if contact_id:
            stmt = stmt.where(Message.contact_id == contact_id)
        if channel:
            stmt = stmt.where(Message.channel == channel)
        stmt = stmt.order_by(Message.created_at.desc()).limit(limit).offset(offset)
        return list((await self._s.execute(stmt)).scalars().all())
