"""Data access layer for ml-scoring."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ml_scoring.models import ContactFeatures


class FeatureRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    @property
    def session(self) -> AsyncSession:
        return self._s

    async def get_features(self, tenant_id: UUID, contact_id: UUID) -> ContactFeatures | None:
        stmt = select(ContactFeatures).where(
            ContactFeatures.tenant_id == tenant_id, ContactFeatures.contact_id == contact_id
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def upsert(self, features: ContactFeatures) -> ContactFeatures:
        existing = await self.get_features(features.tenant_id, features.contact_id)
        if existing is not None:
            for k, v in features.__dict__.items():
                if k.startswith("_") or k in (
                    "id",
                    "tenant_id",
                    "contact_id",
                    "created_at",
                    "updated_at",
                ):
                    continue
                setattr(existing, k, v)
            await self._s.flush()
            return existing
        self._s.add(features)
        await self._s.flush()
        return features

    async def count_labelled(self, tenant_id: UUID) -> int:
        from sqlalchemy import func

        stmt = (
            select(func.count())
            .select_from(ContactFeatures)
            .where(ContactFeatures.tenant_id == tenant_id)
        )
        return int((await self._s.execute(stmt)).scalar_one())
