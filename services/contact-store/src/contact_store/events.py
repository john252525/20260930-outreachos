"""Event emission helpers for contact-store."""

from contact_store.models import Company, Contact
from nats_client.publisher import Publisher
from nats_client.subjects import Subjects


async def emit_company_created(publisher: Publisher, company: Company, *, trace_id: str) -> None:
    await publisher.publish(
        Subjects.COMPANY_CREATED,
        tenant_id=company.tenant_id,
        payload={
            "company": {
                "id": str(company.id),
                "fingerprint": company.fingerprint,
                "status": company.status,
            }
        },
        trace_id=trace_id,
        correlation_id=company.id,
    )


async def emit_company_updated(publisher: Publisher, company: Company, *, trace_id: str) -> None:
    await publisher.publish(
        Subjects.COMPANY_UPDATED,
        tenant_id=company.tenant_id,
        payload={
            "company": {
                "id": str(company.id),
                "fingerprint": company.fingerprint,
                "status": company.status,
            }
        },
        trace_id=trace_id,
        correlation_id=company.id,
    )


async def emit_company_merged(publisher: Publisher, company: Company, *, trace_id: str) -> None:
    await publisher.publish(
        Subjects.COMPANY_MERGED,
        tenant_id=company.tenant_id,
        payload={
            "company": {
                "id": str(company.id),
                "fingerprint": company.fingerprint,
                "status": company.status,
            }
        },
        trace_id=trace_id,
        correlation_id=company.id,
    )


async def emit_contact_created(publisher: Publisher, contact: Contact, *, trace_id: str) -> None:
    await publisher.publish(
        Subjects.CONTACT_CREATED,
        tenant_id=contact.tenant_id,
        payload={
            "contact": {
                "id": str(contact.id),
                "fingerprint": contact.fingerprint,
                "status": contact.status,
                "company_id": str(contact.company_id) if contact.company_id else None,
            }
        },
        trace_id=trace_id,
        correlation_id=contact.id,
    )


async def emit_contact_updated(publisher: Publisher, contact: Contact, *, trace_id: str) -> None:
    await publisher.publish(
        Subjects.CONTACT_UPDATED,
        tenant_id=contact.tenant_id,
        payload={
            "contact": {
                "id": str(contact.id),
                "fingerprint": contact.fingerprint,
                "status": contact.status,
                "company_id": str(contact.company_id) if contact.company_id else None,
            }
        },
        trace_id=trace_id,
        correlation_id=contact.id,
    )


async def emit_contact_merged(publisher: Publisher, contact: Contact, *, trace_id: str) -> None:
    await publisher.publish(
        Subjects.CONTACT_MERGED,
        tenant_id=contact.tenant_id,
        payload={
            "contact": {
                "id": str(contact.id),
                "fingerprint": contact.fingerprint,
                "status": contact.status,
                "company_id": str(contact.company_id) if contact.company_id else None,
            }
        },
        trace_id=trace_id,
        correlation_id=contact.id,
    )


async def emit_contact_unsubscribed(
    publisher: Publisher, contact: Contact, *, trace_id: str
) -> None:
    await publisher.publish(
        Subjects.CONTACT_UNSUBSCRIBED,
        tenant_id=contact.tenant_id,
        payload={
            "contact": {
                "id": str(contact.id),
                "fingerprint": contact.fingerprint,
                "status": contact.status,
                "company_id": str(contact.company_id) if contact.company_id else None,
            }
        },
        trace_id=trace_id,
        correlation_id=contact.id,
    )
