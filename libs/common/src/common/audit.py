"""Audit-event writer (schema ``audit``).

Audit is written in the same transaction as the action (consistency). For
actions that may roll back (e.g. failed login) use a separate transaction.
"""

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from uuid6 import uuid7


@dataclass
class AuditEvent:
    action: str
    resource_type: str
    resource_id: UUID | None = None
    tenant_id: UUID | None = None
    user_id: UUID | None = None
    actor_type: str = "user"  # user | system | agent
    result: str = "success"
    ip_address: str | None = None
    user_agent: str | None = None
    changes: dict[str, Any] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)


async def write_audit_event(session: AsyncSession, event: AuditEvent) -> None:
    await session.execute(
        text(
            """
            INSERT INTO audit.audit_events (
                id, tenant_id, user_id, actor_type, action, resource_type, resource_id,
                result, ip_address, user_agent, changes, context, occurred_at
            ) VALUES (
                :id, :tenant_id, :user_id, :actor_type, :action, :resource_type, :resource_id,
                :result, :ip_address, :user_agent, CAST(:changes AS jsonb), CAST(:context AS jsonb), :occurred_at
            )
            """
        ),
        {
            "id": str(uuid7()),
            "tenant_id": str(event.tenant_id) if event.tenant_id else None,
            "user_id": str(event.user_id) if event.user_id else None,
            "actor_type": event.actor_type,
            "action": event.action,
            "resource_type": event.resource_type,
            "resource_id": str(event.resource_id) if event.resource_id else None,
            "result": event.result,
            "ip_address": event.ip_address,
            "user_agent": event.user_agent,
            "changes": json.dumps(event.changes),
            "context": json.dumps(event.context),
            "occurred_at": datetime.now(UTC),
        },
    )
