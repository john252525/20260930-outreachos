"""Data access layer for reply-classifier."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reply_classifier.models import Reply


class ReplyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    @property
    def session(self) -> AsyncSession:
        return self._s

    async def get(self, reply_id: UUID) -> Reply | None:
        return await self._s.get(Reply, reply_id)

    async def get_by_message_and_email(
        self, *, tenant_id: UUID, message_id: UUID, from_email: str
    ) -> Reply | None:
        stmt = select(Reply).where(
            Reply.tenant_id == tenant_id,
            Reply.message_id == message_id,
            Reply.from_email == from_email,
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def add(self, reply: Reply) -> Reply:
        self._s.add(reply)
        await self._s.flush()
        return reply

    async def list(
        self,
        *,
        tenant_id: UUID,
        status: str | None = None,
        category: str | None = None,
        message_id: UUID | None = None,
        contact_id: UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Reply]:
        stmt = select(Reply).where(Reply.tenant_id == tenant_id)
        if status:
            stmt = stmt.where(Reply.status == status)
        if category:
            stmt = stmt.where(Reply.category == category)
        if message_id:
            stmt = stmt.where(Reply.message_id == message_id)
        if contact_id:
            stmt = stmt.where(Reply.contact_id == contact_id)
        stmt = stmt.order_by(Reply.received_at.desc()).limit(limit).offset(offset)
        return list((await self._s.execute(stmt)).scalars().all())
