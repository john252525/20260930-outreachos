"""Business logic for users-service."""

import re
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

import structlog
from sqlalchemy import select

from common.audit import AuditEvent, write_audit_event
from common.errors import AppError, ConflictError, NotFoundError, ValidationError
from db.rls import set_tenant_context
from db.types import generate_uuid7
from nats_client.publisher import Publisher
from users_service.auth.password import (
    hash_password,
    needs_rehash,
    verify_dummy,
    verify_password,
)
from users_service.clients_tenant import TenantClient
from users_service.config import Settings
from users_service.db_admin import admin_session_factory
from users_service.models import Invitation, User, UserTenant
from users_service.repository import UserRepository

logger = structlog.get_logger()


class UserService:
    def __init__(
        self,
        *,
        repo: UserRepository,
        tenant_client: TenantClient,
        publisher: Publisher,
        settings: Settings,
    ) -> None:
        self._repo = repo
        self._tenant_client = tenant_client
        self._publisher = publisher
        self._settings = settings

    @staticmethod
    def _slugify(name: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        slug = slug[:40] or "tenant"
        return f"{slug}-{secrets.token_hex(3)}"

    async def register(
        self, *, email: str, password: str, display_name: str, company_name: str, ip: str | None
    ) -> tuple[User, UUID]:
        email = email.lower()
        existing = await self._repo.get_user_by_email(email)
        if existing is not None:
            raise ConflictError("Email already registered")

        user = User(
            id=generate_uuid7(),
            email=email,
            password_hash=hash_password(password),
            display_name=display_name,
            status="active",
            email_verified=False,
        )
        await self._repo.add_user(user)

        tenant = await self._tenant_client.create_tenant(
            name=company_name,
            slug=self._slugify(company_name),
            idempotency_key=f"register:{user.id}",
        )
        tenant_id = UUID(str(tenant["id"]))

        # RLS: membership/audit inserts are tenant-scoped — set context to the
        # freshly created tenant (which is allowed to see itself, cf. ADR-004).
        await set_tenant_context(self._repo.session, tenant_id)

        await self._repo.add_membership(
            UserTenant(
                id=generate_uuid7(),
                tenant_id=tenant_id,
                user_id=user.id,
                role="admin",
                is_owner=True,
                is_active=True,
                accepted_at=datetime.now(UTC),
            )
        )

        await write_audit_event(
            self._repo.session,
            AuditEvent(
                action="user.registered",
                resource_type="user",
                resource_id=user.id,
                tenant_id=tenant_id,
                user_id=user.id,
                ip_address=ip,
            ),
        )
        logger.info("user_registered", user_id=str(user.id), tenant_id=str(tenant_id))
        return user, tenant_id

    async def authenticate(self, *, email: str, password: str, ip: str | None) -> User | None:
        user = await self._repo.get_user_by_email(email.lower())
        if user is None:
            # Constant-time: run a dummy verification so timing doesn't leak.
            verify_dummy(password)
            return None

        if user.locked_until and user.locked_until > datetime.now(UTC):
            raise AppError("Account locked. Try later.", code="account_locked", status_code=403)

        if not verify_password(password, user.password_hash):
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= self._settings.max_failed_logins:
                user.locked_until = datetime.now(UTC) + timedelta(
                    minutes=self._settings.lock_minutes
                )
            await self._repo.session.flush()
            return None

        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login_at = datetime.now(UTC)
        user.last_login_ip = ip
        if needs_rehash(user.password_hash):
            user.password_hash = hash_password(password)
        await self._repo.session.flush()
        return user

    async def list_memberships(self, user_id: UUID) -> list[UserTenant]:
        # Cross-tenant read (login) — user_tenants is RLS-protected, so use the
        # owner session (ADR-017).
        try:
            factory = admin_session_factory()
        except RuntimeError:
            return await self._repo.list_memberships(user_id)
        async with factory() as session:
            stmt = select(UserTenant).where(
                UserTenant.user_id == user_id, UserTenant.is_active.is_(True)
            )
            return list((await session.execute(stmt)).scalars().all())

    async def get_membership(self, tenant_id: UUID, user_id: UUID) -> UserTenant:
        m = await self._repo.get_membership(tenant_id, user_id)
        if m is None:
            raise NotFoundError("Membership not found")
        return m

    async def list_tenant_users(self, tenant_id: UUID) -> list[UserTenant]:
        return await self._repo.list_tenant_users(tenant_id)

    async def get_user(self, user_id: UUID) -> User:
        user = await self._repo.get_user(user_id)
        if user is None:
            raise NotFoundError(f"User {user_id} not found")
        return user

    async def invite(
        self,
        *,
        tenant_id: UUID,
        invited_by: UUID,
        email: str,
        role: str,
    ) -> Invitation:
        token = secrets.token_urlsafe(32)
        invitation = Invitation(
            id=generate_uuid7(),
            tenant_id=tenant_id,
            email=email.lower(),
            role=role,
            token=token,
            invited_by=invited_by,
            expires_at=datetime.now(UTC) + timedelta(days=7),
            status="pending",
        )
        await self._repo.add_invitation(invitation)
        await write_audit_event(
            self._repo.session,
            AuditEvent(
                action="user.invited",
                resource_type="invitation",
                resource_id=invitation.id,
                tenant_id=tenant_id,
                user_id=invited_by,
                changes={"after": {"email": email, "role": role}},
            ),
        )
        return invitation

    async def list_invitations(self, tenant_id: UUID) -> list[Invitation]:
        return await self._repo.list_invitations(tenant_id)

    async def accept_invitation(self, *, token: str, user_id: UUID) -> UserTenant:
        invitation = await self._repo.get_invitation_by_token(token)
        if invitation is None:
            raise NotFoundError("Invitation not found")
        if invitation.status != "pending":
            raise ValidationError(f"Invitation is {invitation.status}")
        if invitation.expires_at < datetime.now(UTC):
            invitation.status = "expired"
            await self._repo.session.flush()
            raise ValidationError("Invitation expired")

        existing = await self._repo.get_membership(invitation.tenant_id, user_id)
        if existing is not None:
            existing.is_active = True
            await self._repo.session.flush()
            membership = existing
        else:
            membership = await self._repo.add_membership(
                UserTenant(
                    id=generate_uuid7(),
                    tenant_id=invitation.tenant_id,
                    user_id=user_id,
                    role=invitation.role,
                    is_owner=False,
                    is_active=True,
                    invited_by=invitation.invited_by,
                    invited_at=invitation.created_at,
                    accepted_at=datetime.now(UTC),
                )
            )

        invitation.status = "accepted"
        invitation.accepted_at = datetime.now(UTC)
        invitation.accepted_by = user_id
        await self._repo.session.flush()
        return membership

    async def update_role(
        self, *, tenant_id: UUID, user_id: UUID, role: str, actor_id: UUID
    ) -> UserTenant:
        membership = await self._repo.get_membership(tenant_id, user_id)
        if membership is None:
            raise NotFoundError("Membership not found")
        if membership.is_owner and role != "admin":
            raise ValidationError("Cannot demote the tenant owner")
        before = membership.role
        membership.role = role
        await self._repo.session.flush()
        await write_audit_event(
            self._repo.session,
            AuditEvent(
                action="user.role_changed",
                resource_type="membership",
                resource_id=membership.id,
                tenant_id=tenant_id,
                user_id=actor_id,
                changes={"before": {"role": before}, "after": {"role": role}},
            ),
        )
        return membership
