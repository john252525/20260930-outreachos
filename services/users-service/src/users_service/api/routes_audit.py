"""Audit log read API."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text

from common.context import get_tenant_id
from common.errors import ValidationError
from db.rls import set_tenant_context
from db.session import async_session_factory
from users_service.auth.deps import require_role
from users_service.schemas import AuditEventRead

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/events", response_model=list[AuditEventRead])
async def list_audit_events(
    action: str | None = Query(None),
    resource_type: str | None = Query(None),
    resource_id: UUID | None = Query(None),
    user_id: UUID | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    _: dict[str, Any] = Depends(require_role("admin", "manager")),
) -> list[AuditEventRead]:
    tenant_id = get_tenant_id()
    if tenant_id is None:
        raise ValidationError("X-Tenant-ID required")

    sql = "SELECT * FROM audit.audit_events WHERE tenant_id = :tid"
    params: dict[str, object] = {"tid": str(tenant_id), "limit": limit, "offset": offset}
    if action:
        sql += " AND action = :action"
        params["action"] = action
    if resource_type:
        sql += " AND resource_type = :resource_type"
        params["resource_type"] = resource_type
    if resource_id:
        sql += " AND resource_id = :resource_id"
        params["resource_id"] = str(resource_id)
    if user_id:
        sql += " AND user_id = :user_id"
        params["user_id"] = str(user_id)
    sql += " ORDER BY occurred_at DESC LIMIT :limit OFFSET :offset"

    async with async_session_factory() as session, session.begin():
        await set_tenant_context(session, tenant_id)
        result = await session.execute(text(sql), params)
        rows = result.mappings().all()
    return [AuditEventRead.model_validate(dict(r)) for r in rows]
