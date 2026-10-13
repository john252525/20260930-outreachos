"""Data access layer for users-service."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from users_service.models import Invitation, User, UserTenant


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    @property
    def session(self) -> AsyncSession:
        return self._s

    async def get_user(self, user_id: UUID) -> User | None:
        return await self._s.get(User, user_id)

    async def get_user_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email.lower())
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def add_user(self, user: User) -> User:
        self._s.add(user)
        await self._s.flush()
        return user

    async def list_memberships(self, user_id: UUID) -> list[UserTenant]:
        stmt = select(UserTenant).where(
            UserTenant.user_id == user_id, UserTenant.is_active.is_(True)
        )
        return list((await self._s.execute(stmt)).scalars().all())

    async def get_membership(self, tenant_id: UUID, user_id: UUID) -> UserTenant | None:
        stmt = select(UserTenant).where(
            UserTenant.tenant_id == tenant_id, UserTenant.user_id == user_id
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def add_membership(self, membership: UserTenant) -> UserTenant:
        self._s.add(membership)
        await self._s.flush()
        return membership

    async def list_tenant_users(self, tenant_id: UUID) -> list[UserTenant]:
        stmt = select(UserTenant).where(UserTenant.tenant_id == tenant_id)
        return list((await self._s.execute(stmt)).scalars().all())

    async def add_invitation(self, invitation: Invitation) -> Invitation:
        self._s.add(invitation)
        await self._s.flush()
        return invitation

    async def get_invitation_by_token(self, token: str) -> Invitation | None:
        stmt = select(Invitation).where(Invitation.token == token)
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def list_invitations(self, tenant_id: UUID) -> list[Invitation]:
        stmt = select(Invitation).where(Invitation.tenant_id == tenant_id)
        return list((await self._s.execute(stmt)).scalars().all())
