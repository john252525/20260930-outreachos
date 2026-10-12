"""Template override repository and application logic."""

import re
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from composer_service.models import TemplateOverride

_VAR_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}")


class TemplateOverrideRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    @property
    def session(self) -> AsyncSession:
        return self._s

    async def get_active(self, *, tenant_id: UUID, template_id: str) -> TemplateOverride | None:
        stmt = select(TemplateOverride).where(
            TemplateOverride.tenant_id == tenant_id,
            TemplateOverride.template_id == template_id,
            TemplateOverride.is_active.is_(True),
        )
        return (await self._s.execute(stmt)).scalars().first()

    async def get_by_version(
        self, *, tenant_id: UUID, template_id: str, override_version: str
    ) -> TemplateOverride | None:
        stmt = select(TemplateOverride).where(
            TemplateOverride.tenant_id == tenant_id,
            TemplateOverride.template_id == template_id,
            TemplateOverride.override_version == override_version,
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def add(self, override: TemplateOverride) -> TemplateOverride:
        stmt = select(TemplateOverride).where(
            TemplateOverride.tenant_id == override.tenant_id,
            TemplateOverride.template_id == override.template_id,
            TemplateOverride.is_active.is_(True),
        )
        for existing in (await self._s.execute(stmt)).scalars().all():
            existing.is_active = False
        self._s.add(override)
        await self._s.flush()
        return override

    async def list_all(self, *, tenant_id: UUID) -> list[TemplateOverride]:
        stmt = (
            select(TemplateOverride)
            .where(TemplateOverride.tenant_id == tenant_id)
            .order_by(TemplateOverride.created_at.desc())
        )
        return list((await self._s.execute(stmt)).scalars().all())

    async def set_active(
        self, *, tenant_id: UUID, override_id: UUID, is_active: bool
    ) -> TemplateOverride | None:
        override = await self._s.get(TemplateOverride, override_id)
        if override is None or override.tenant_id != tenant_id:
            return None
        if is_active:
            stmt = select(TemplateOverride).where(
                TemplateOverride.tenant_id == tenant_id,
                TemplateOverride.template_id == override.template_id,
                TemplateOverride.is_active.is_(True),
                TemplateOverride.id != override.id,
            )
            for other in (await self._s.execute(stmt)).scalars().all():
                other.is_active = False
        override.is_active = is_active
        await self._s.flush()
        return override


def render_override(user_prompt_template: str, variables: dict[str, Any]) -> str:
    """Substitute ``{{ var }}`` placeholders with values from ``variables``."""

    def _sub(match: re.Match[str]) -> str:
        key = match.group(1)
        value = variables.get(key)
        return "" if value is None else str(value)

    return _VAR_RE.sub(_sub, user_prompt_template)
