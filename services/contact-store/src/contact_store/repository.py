"""Data access layer for contact-store."""

from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from contact_store.models import Company, Contact, ContactEmail, ContactPhone


class CompanyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    @property
    def session(self) -> AsyncSession:
        return self._s

    async def get(self, company_id: UUID) -> Company | None:
        return await self._s.get(Company, company_id)

    async def get_by_fingerprint(self, tenant_id: UUID, fingerprint: str) -> Company | None:
        stmt = select(Company).where(
            Company.tenant_id == tenant_id,
            Company.fingerprint == fingerprint,
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def get_by_domain(self, tenant_id: UUID, domain: str) -> Company | None:
        stmt = select(Company).where(
            Company.tenant_id == tenant_id,
            Company.domain_normalized == domain,
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def get_by_inn(self, tenant_id: UUID, inn: str) -> Company | None:
        stmt = select(Company).where(
            Company.tenant_id == tenant_id,
            Company.inn == inn,
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def list(
        self,
        *,
        tenant_id: UUID,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Company]:
        stmt = select(Company).where(Company.tenant_id == tenant_id)
        if status:
            stmt = stmt.where(Company.status == status)
        stmt = stmt.order_by(Company.created_at.desc()).limit(limit).offset(offset)
        return list((await self._s.execute(stmt)).scalars().all())

    async def add(self, company: Company) -> Company:
        self._s.add(company)
        await self._s.flush()
        return company

    async def update_contacts_count(self, company_id: UUID) -> None:
        stmt = select(func.count(Contact.id)).where(Contact.company_id == company_id)
        count = (await self._s.execute(stmt)).scalar_one()
        company = await self._s.get(Company, company_id)
        if company is not None:
            company.contacts_count = count


class ContactRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    @property
    def session(self) -> AsyncSession:
        return self._s

    async def get(self, contact_id: UUID) -> Contact | None:
        return await self._s.get(Contact, contact_id)

    async def get_by_fingerprint(self, tenant_id: UUID, fingerprint: str) -> Contact | None:
        stmt = select(Contact).where(
            Contact.tenant_id == tenant_id,
            Contact.fingerprint == fingerprint,
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def get_by_email(self, tenant_id: UUID, email: str) -> Contact | None:
        stmt = (
            select(Contact)
            .join(ContactEmail, ContactEmail.contact_id == Contact.id)
            .where(ContactEmail.tenant_id == tenant_id, ContactEmail.value == email)
        )
        return (await self._s.execute(stmt)).scalars().first()

    async def get_by_phone(self, tenant_id: UUID, phone: str) -> Contact | None:
        stmt = (
            select(Contact)
            .join(ContactPhone, ContactPhone.contact_id == Contact.id)
            .where(ContactPhone.tenant_id == tenant_id, ContactPhone.value == phone)
        )
        return (await self._s.execute(stmt)).scalars().first()

    async def list_by_company(self, company_id: UUID, limit: int = 200) -> list[Contact]:
        stmt = select(Contact).where(Contact.company_id == company_id).limit(limit)
        return list((await self._s.execute(stmt)).scalars().all())

    async def list(
        self,
        *,
        tenant_id: UUID,
        status: str | None = None,
        company_id: UUID | None = None,
        role_category: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Contact]:
        stmt = select(Contact).where(Contact.tenant_id == tenant_id)
        if status:
            stmt = stmt.where(Contact.status == status)
        if company_id:
            stmt = stmt.where(Contact.company_id == company_id)
        if role_category:
            stmt = stmt.where(Contact.role_category == role_category)
        stmt = stmt.order_by(Contact.created_at.desc()).limit(limit).offset(offset)
        return list((await self._s.execute(stmt)).scalars().all())

    async def add(self, contact: Contact) -> Contact:
        self._s.add(contact)
        await self._s.flush()
        return contact

    async def delete_emails_phones(self, contact_id: UUID) -> None:
        await self._s.execute(delete(ContactEmail).where(ContactEmail.contact_id == contact_id))
        await self._s.execute(delete(ContactPhone).where(ContactPhone.contact_id == contact_id))
