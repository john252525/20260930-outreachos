"""Business logic for tenant settings."""

from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.types import generate_uuid7
from tenant_service.models import TenantSettings
from tenant_service.settings_schemas import TenantSettingsUpdate

logger = structlog.get_logger()


class TenantSettingsService:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_or_create(self, tenant_id: UUID) -> TenantSettings:
        stmt = select(TenantSettings).where(TenantSettings.tenant_id == tenant_id)
        settings = (await self._s.execute(stmt)).scalar_one_or_none()
        if settings is None:
            settings = TenantSettings(id=generate_uuid7(), tenant_id=tenant_id)
            self._s.add(settings)
            await self._s.flush()
        return settings

    async def update(self, tenant_id: UUID, data: TenantSettingsUpdate) -> TenantSettings:
        settings = await self.get_or_create(tenant_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            if value is not None:
                setattr(settings, field, value)
        await self._s.flush()
        await self._s.refresh(settings)
        logger.info("tenant_settings_updated", tenant_id=str(tenant_id))
        return settings
