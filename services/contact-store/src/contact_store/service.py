"""Business logic for contact-store."""

from typing import Any
from uuid import UUID

import structlog

from common.errors import NotFoundError, ValidationError
from contact_store import events
from contact_store.fingerprint import company_fingerprint, contact_fingerprint
from contact_store.merger import merge_company_payload, merge_contact_payload
from contact_store.models import Company, Contact, ContactEmail, ContactPhone
from contact_store.normalization import (
    normalize_company_name,
    normalize_domain,
    normalize_email,
    normalize_inn,
    normalize_ogrn,
    normalize_person_name,
    normalize_phone,
)
from contact_store.repository import CompanyRepository, ContactRepository
from contact_store.stoplist import StopList
from nats_client.publisher import Publisher

logger = structlog.get_logger()


class CompanyService:
    def __init__(self, repo: CompanyRepository, publisher: Publisher) -> None:
        self._repo = repo
        self._publisher = publisher

    async def upsert(
        self,
        *,
        tenant_id: UUID,
        payload: dict[str, Any],
        status: str = "candidate",
        trace_id: str = "",
    ) -> tuple[Company, str]:
        """Upsert a company. Returns (company, action)."""
        normalized = self._normalize_payload(payload)
        fingerprint = company_fingerprint(
            name_normalized=normalized["name_normalized"],
            domain_normalized=normalized["domain_normalized"],
            inn=normalized["inn"],
        )

        existing = await self._repo.get_by_fingerprint(tenant_id, fingerprint)
        if existing is None:
            if normalized["inn"]:
                existing = await self._repo.get_by_inn(tenant_id, normalized["inn"])
            if existing is None and normalized["domain_normalized"]:
                existing = await self._repo.get_by_domain(
                    tenant_id, normalized["domain_normalized"]
                )

        if existing is None:
            company = Company(
                tenant_id=tenant_id,
                fingerprint=fingerprint,
                status=status,
                name_normalized=normalized["name_normalized"],
                domain_normalized=normalized["domain_normalized"],
                inn=normalized["inn"],
                ogrn=normalized["ogrn"],
                payload=payload,
            )
            await self._repo.add(company)
            await self._repo.session.refresh(company)
            await events.emit_company_created(self._publisher, company, trace_id=trace_id)
            return company, "created"

        merged_payload = merge_company_payload(existing.payload, payload)
        action = "merged" if merged_payload != existing.payload else "updated"

        existing.payload = merged_payload
        existing.name_normalized = normalized["name_normalized"] or existing.name_normalized
        existing.domain_normalized = normalized["domain_normalized"] or existing.domain_normalized
        existing.inn = normalized["inn"] or existing.inn
        existing.ogrn = normalized["ogrn"] or existing.ogrn
        if status and status != "candidate":
            existing.status = status
        await self._repo.session.flush()
        await self._repo.session.refresh(existing)

        if action == "merged":
            await events.emit_company_merged(self._publisher, existing, trace_id=trace_id)
        else:
            await events.emit_company_updated(self._publisher, existing, trace_id=trace_id)
        return existing, action

    async def bulk_upsert(
        self, *, tenant_id: UUID, items: list[dict[str, Any]], trace_id: str = ""
    ) -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        created = updated = merged = 0
        for i, item in enumerate(items):
            try:
                company, action = await self.upsert(
                    tenant_id=tenant_id,
                    payload=item["payload"],
                    status=item.get("status", "candidate"),
                    trace_id=trace_id,
                )
                results.append({"company": company, "action": action})
                if action == "created":
                    created += 1
                elif action == "updated":
                    updated += 1
                else:
                    merged += 1
            except Exception as e:
                logger.exception("bulk_upsert_item_failed", index=i)
                errors.append({"index": i, "error": str(e)})
        return {
            "created": created,
            "updated": updated,
            "merged": merged,
            "results": results,
            "errors": errors,
        }

    def _normalize_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        name_fact = payload.get("name") or {}
        name_value = name_fact.get("value") if isinstance(name_fact, dict) else None
        if not name_value:
            raise ValidationError("Company payload must have name.value")

        domain_fact = payload.get("domain") or {}
        domain_value = domain_fact.get("value") if isinstance(domain_fact, dict) else None

        registry = payload.get("registry_ids") or {}
        inn_raw = registry.get("ru_inn")
        ogrn_raw = registry.get("ru_ogrn")

        return {
            "name_normalized": normalize_company_name(name_value),
            "domain_normalized": normalize_domain(domain_value),
            "inn": normalize_inn(inn_raw),
            "ogrn": normalize_ogrn(ogrn_raw),
        }

    async def get(self, company_id: UUID) -> Company:
        company = await self._repo.get(company_id)
        if company is None:
            raise NotFoundError(f"Company {company_id} not found")
        return company

    async def list(
        self, *, tenant_id: UUID, status: str | None, limit: int, offset: int
    ) -> list[Company]:
        return await self._repo.list(tenant_id=tenant_id, status=status, limit=limit, offset=offset)


class ContactService:
    def __init__(
        self,
        repo: ContactRepository,
        company_repo: CompanyRepository,
        stoplist: StopList,
        publisher: Publisher,
    ) -> None:
        self._repo = repo
        self._company_repo = company_repo
        self._stoplist = stoplist
        self._publisher = publisher

    async def upsert(
        self,
        *,
        tenant_id: UUID,
        payload: dict[str, Any],
        status: str = "candidate",
        trace_id: str = "",
    ) -> tuple[Contact | None, str]:
        """Upsert a contact.

        Returns (contact, action) on success, or (None, "blocked:<reason>")
        when the email/phone is on the stop-list.
        """
        normalized = await self._normalize_payload(payload)

        blocked, reason = await self._stoplist.is_blocked(
            tenant_id=tenant_id,
            email=normalized["primary_email"],
            phone=normalized["primary_phone"],
        )
        if blocked:
            logger.info(
                "contact_blocked_by_stoplist",
                reason=reason,
                email=normalized["primary_email"],
            )
            return None, f"blocked:{reason}"

        fingerprint = contact_fingerprint(
            email=normalized["primary_email"],
            phone=normalized["primary_phone"],
            full_name_normalized=normalized["full_name_normalized"],
            company_domain=normalized["company_domain"],
        )

        existing = await self._repo.get_by_fingerprint(tenant_id, fingerprint)
        if existing is None:
            if normalized["primary_email"]:
                existing = await self._repo.get_by_email(tenant_id, normalized["primary_email"])
            if existing is None and normalized["primary_phone"]:
                existing = await self._repo.get_by_phone(tenant_id, normalized["primary_phone"])

        if existing is None:
            contact = Contact(
                tenant_id=tenant_id,
                company_id=normalized["company_id"],
                fingerprint=fingerprint,
                status=status,
                full_name_normalized=normalized["full_name_normalized"],
                primary_email=normalized["primary_email"],
                primary_phone=normalized["primary_phone"],
                role_category=normalized["role_category"],
                seniority=normalized["seniority"],
                payload=payload,
            )
            await self._repo.add(contact)
            await self._repo.session.refresh(contact)
            await self._sync_emails_phones(tenant_id, contact.id, payload)
            if normalized["company_id"]:
                await self._company_repo.update_contacts_count(normalized["company_id"])
            await events.emit_contact_created(self._publisher, contact, trace_id=trace_id)
            return contact, "created"

        merged_payload = merge_contact_payload(existing.payload, payload)
        action = "merged" if merged_payload != existing.payload else "updated"

        existing.payload = merged_payload
        existing.full_name_normalized = (
            normalized["full_name_normalized"] or existing.full_name_normalized
        )
        existing.primary_email = normalized["primary_email"] or existing.primary_email
        existing.primary_phone = normalized["primary_phone"] or existing.primary_phone
        if normalized["role_category"] != "unknown":
            existing.role_category = normalized["role_category"]
        if normalized["seniority"] != "unknown":
            existing.seniority = normalized["seniority"]
        if normalized["company_id"] and not existing.company_id:
            existing.company_id = normalized["company_id"]
        if status and status != "candidate":
            existing.status = status
        await self._repo.session.flush()
        await self._repo.session.refresh(existing)

        await self._sync_emails_phones(tenant_id, existing.id, merged_payload)
        if existing.company_id:
            await self._company_repo.update_contacts_count(existing.company_id)

        if action == "merged":
            await events.emit_contact_merged(self._publisher, existing, trace_id=trace_id)
        else:
            await events.emit_contact_updated(self._publisher, existing, trace_id=trace_id)
        return existing, action

    async def bulk_upsert(
        self, *, tenant_id: UUID, items: list[dict[str, Any]], trace_id: str = ""
    ) -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        created = updated = merged = blocked = 0
        for i, item in enumerate(items):
            try:
                contact, action = await self.upsert(
                    tenant_id=tenant_id,
                    payload=item["payload"],
                    status=item.get("status", "candidate"),
                    trace_id=trace_id,
                )
                if contact is None:
                    blocked += 1
                    continue
                results.append({"contact": contact, "action": action})
                if action == "created":
                    created += 1
                elif action == "updated":
                    updated += 1
                else:
                    merged += 1
            except Exception as e:
                logger.exception("bulk_upsert_contact_failed", index=i)
                errors.append({"index": i, "error": str(e)})
        return {
            "created": created,
            "updated": updated,
            "merged": merged,
            "blocked": blocked,
            "results": results,
            "errors": errors,
        }

    async def update_status(self, contact_id: UUID, *, status: str, trace_id: str = "") -> Contact:
        contact = await self.get(contact_id)
        contact.status = status
        await self._repo.session.flush()
        await self._repo.session.refresh(contact)
        if status == "unsubscribed":
            if contact.primary_email:
                await self._stoplist.add(
                    tenant_id=contact.tenant_id,
                    kind="email",
                    value=contact.primary_email,
                    reason="unsubscribed",
                )
            await events.emit_contact_unsubscribed(self._publisher, contact, trace_id=trace_id)
        else:
            await events.emit_contact_updated(self._publisher, contact, trace_id=trace_id)
        return contact

    async def update_outreach_history(
        self,
        contact_id: UUID,
        *,
        replied_positive: bool | None = None,
        last_reply_at: Any | None = None,
        last_contacted_at: Any | None = None,
    ) -> Contact:
        contact = await self.get(contact_id)
        if replied_positive is not None:
            contact.replied_positive = replied_positive
        if last_reply_at is not None:
            contact.last_reply_at = last_reply_at
        if last_contacted_at is not None:
            contact.last_contacted_at = last_contacted_at
        await self._repo.session.flush()
        await self._repo.session.refresh(contact)
        return contact

    async def get(self, contact_id: UUID) -> Contact:
        contact = await self._repo.get(contact_id)
        if contact is None:
            raise NotFoundError(f"Contact {contact_id} not found")
        return contact

    async def list(
        self,
        *,
        tenant_id: UUID,
        status: str | None,
        company_id: UUID | None,
        role_category: str | None,
        limit: int,
        offset: int,
    ) -> list[Contact]:
        return await self._repo.list(
            tenant_id=tenant_id,
            status=status,
            company_id=company_id,
            role_category=role_category,
            limit=limit,
            offset=offset,
        )

    async def _normalize_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        full_name_fact = payload.get("full_name") or {}
        full_name = full_name_fact.get("value") if isinstance(full_name_fact, dict) else None

        emails = payload.get("emails") or []
        primary_email = None
        for e in emails:
            v = normalize_email(e.get("value"))
            if v and (e.get("is_primary") or primary_email is None):
                primary_email = v

        phones = payload.get("phones") or []
        primary_phone = None
        for p in phones:
            v = normalize_phone(p.get("value"))
            if v and (p.get("is_primary") or primary_phone is None):
                primary_phone = v

        company_id_raw = payload.get("company_id")
        company_id = UUID(company_id_raw) if company_id_raw else None
        company_domain = None
        if company_id:
            company = await self._company_repo.get(company_id)
            if company is not None:
                company_domain = company.domain_normalized

        return {
            "full_name_normalized": normalize_person_name(full_name or ""),
            "primary_email": primary_email,
            "primary_phone": primary_phone,
            "role_category": payload.get("role_category") or "unknown",
            "seniority": payload.get("seniority") or "unknown",
            "company_id": company_id,
            "company_domain": company_domain,
        }

    async def _sync_emails_phones(
        self, tenant_id: UUID, contact_id: UUID, payload: dict[str, Any]
    ) -> None:
        await self._repo.delete_emails_phones(contact_id)

        for e in payload.get("emails", []) or []:
            if not e.get("value"):
                continue
            self._repo.session.add(
                ContactEmail(
                    tenant_id=tenant_id,
                    contact_id=contact_id,
                    value=normalize_email(e["value"]) or e["value"],
                    type=e.get("type", "unknown"),
                    is_primary=e.get("is_primary", False),
                    is_verified=e.get("is_verified", False),
                    confidence=e.get("confidence", 0.0),
                    evidence=e.get("evidence", []),
                )
            )
        for p in payload.get("phones", []) or []:
            if not p.get("value"):
                continue
            self._repo.session.add(
                ContactPhone(
                    tenant_id=tenant_id,
                    contact_id=contact_id,
                    value=normalize_phone(p["value"]) or p["value"],
                    type=p.get("type", "unknown"),
                    is_primary=p.get("is_primary", False),
                    is_whatsapp=p.get("is_whatsapp", False),
                    is_telegram=p.get("is_telegram", False),
                    confidence=p.get("confidence", 0.0),
                    evidence=p.get("evidence", []),
                )
            )
        await self._repo.session.flush()
