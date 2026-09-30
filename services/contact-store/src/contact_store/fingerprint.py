"""Deterministic fingerprints for companies and contacts."""

import hashlib


def _hash(parts: list[str]) -> str:
    payload = "|".join(p or "" for p in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def company_fingerprint(
    *,
    name_normalized: str,
    domain_normalized: str | None,
    inn: str | None = None,
) -> str:
    """Company fingerprint. Priority: INN -> domain -> normalized name."""
    if inn:
        return _hash(["inn", inn])
    if domain_normalized:
        return _hash(["domain", domain_normalized])
    if name_normalized:
        return _hash(["name", name_normalized])
    raise ValueError("Cannot compute fingerprint: no inn, domain, or name")


def contact_fingerprint(
    *,
    email: str | None,
    phone: str | None,
    full_name_normalized: str,
    company_domain: str | None,
) -> str:
    """Contact fingerprint. Priority: email -> phone -> name+company domain."""
    if email:
        return _hash(["email", email])
    if phone:
        return _hash(["phone", phone])
    if full_name_normalized and company_domain:
        return _hash(["name+domain", full_name_normalized, company_domain])
    if full_name_normalized:
        raise ValueError(
            "Cannot compute contact fingerprint: name without company domain is too weak"
        )
    raise ValueError("Cannot compute fingerprint: no email, phone, or name+domain")
