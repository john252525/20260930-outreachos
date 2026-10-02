"""Data access layer for review-queue."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from review_queue.models import ReviewItem


class ReviewItemRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    @property
    def session(self) -> AsyncSession:
        return self._s

    async def get(self, item_id: UUID) -> ReviewItem | None:
        return await self._s.get(ReviewItem, item_id)

    async def get_by_message(self, tenant_id: UUID, message_id: UUID) -> ReviewItem | None:
        stmt = select(ReviewItem).where(
            ReviewItem.tenant_id == tenant_id,
            ReviewItem.message_id == message_id,
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def add(self, item: ReviewItem) -> ReviewItem:
        self._s.add(item)
        await self._s.flush()
        return item

    async def list(
        self,
        *,
        tenant_id: UUID,
        status: str | None = None,
        priority: str | None = None,
        assigned_to: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ReviewItem]:
        stmt = select(ReviewItem).where(ReviewItem.tenant_id == tenant_id)
        if status:
            stmt = stmt.where(ReviewItem.status == status)
        if priority:
            stmt = stmt.where(ReviewItem.priority == priority)
        if assigned_to:
            stmt = stmt.where(ReviewItem.assigned_to == assigned_to)
        stmt = stmt.order_by(ReviewItem.created_at.desc()).limit(limit).offset(offset)
        return list((await self._s.execute(stmt)).scalars().all())
