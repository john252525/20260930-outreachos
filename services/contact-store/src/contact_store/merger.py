"""Merge logic for companies and contacts (pure, no DB)."""

from copy import deepcopy
from typing import Any


def _merge_fact(
    existing: dict[str, Any] | None, incoming: dict[str, Any] | None
) -> dict[str, Any] | None:
    """Merge two fact objects {value, confidence, evidence}.

    Rules:
    - if one is None, return the other;
    - higher confidence wins; on tie the existing one wins (stability);
    - evidence is merged (unique by source_url).
    """
    if existing is None:
        return deepcopy(incoming) if incoming else None
    if incoming is None:
        return existing

    existing_conf = existing.get("confidence", 0.0)
    incoming_conf = incoming.get("confidence", 0.0)

    existing_evidence = existing.get("evidence", []) or []
    incoming_evidence = incoming.get("evidence", []) or []
    seen_urls = {e.get("source_url") for e in existing_evidence if e.get("source_url")}
    merged_evidence = list(existing_evidence)
    for e in incoming_evidence:
        if e.get("source_url") and e["source_url"] in seen_urls:
            continue
        merged_evidence.append(e)

    base = deepcopy(incoming) if incoming_conf > existing_conf else deepcopy(existing)
    base["evidence"] = merged_evidence
    return base


def _merge_list_of_strings(a: list[str] | None, b: list[str] | None) -> list[str]:
    """Merge string lists, preserving order, removing duplicates."""
    result: list[str] = []
    seen: set[str] = set()
    for item in (a or []) + (b or []):
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _merge_list_of_facts(
    a: list[dict[str, Any]] | None, b: list[dict[str, Any]] | None
) -> list[dict[str, Any]]:
    """Merge fact lists (e.g. signals). Dedup by (type, source_url)."""
    result: list[dict[str, Any]] = []
    seen: set[tuple[object, ...]] = set()
    for item in (a or []) + (b or []):
        key = (item.get("type"), item.get("source_url"))
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _merge_locations(
    a: list[dict[str, Any]] | None, b: list[dict[str, Any]] | None
) -> list[dict[str, Any]]:
    """Merge locations. Dedup by (country, city, address)."""
    result: list[dict[str, Any]] = []
    seen: set[tuple[object, ...]] = set()
    for loc in (a or []) + (b or []):
        key = (
            (loc.get("country") or {}).get("value"),
            (loc.get("city") or {}).get("value"),
            (loc.get("address") or {}).get("value"),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(loc)
    return result


def _merge_tech_stack(
    a: list[dict[str, Any]] | None, b: list[dict[str, Any]] | None
) -> list[dict[str, Any]]:
    """Merge tech_stack by value, combining evidence."""
    by_value: dict[str, dict[str, Any]] = {}
    for item in (a or []) + (b or []):
        value = item.get("value")
        if not value:
            continue
        if value not in by_value:
            by_value[value] = deepcopy(item)
        else:
            by_value[value]["confidence"] = max(
                by_value[value].get("confidence", 0.0),
                item.get("confidence", 0.0),
            )
            existing_ev = by_value[value].get("evidence", []) or []
            seen_urls = {e.get("source_url") for e in existing_ev if e.get("source_url")}
            for e in item.get("evidence", []) or []:
                if e.get("source_url") and e["source_url"] in seen_urls:
                    continue
                existing_ev.append(e)
            by_value[value]["evidence"] = existing_ev
    return list(by_value.values())


def _max_datetime(a: str | None, b: str | None) -> str | None:
    """Return the max of two ISO datetime strings."""
    if not a:
        return b
    if not b:
        return a
    return max(a, b)


def _merge_notes(a: str | None, b: str | None) -> str | None:
    if not a:
        return b
    if not b:
        return a
    if a == b:
        return a
    return f"{a}\n---\n{b}"


def merge_company_payload(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    """Merge two company payloads per docs/contracts.md."""
    result = deepcopy(existing)

    for field in ("name", "legal_name", "domain", "website", "industry", "sub_industry"):
        result[field] = _merge_fact(result.get(field), incoming.get(field))

    existing_size = result.get("size_estimate", {}) or {}
    incoming_size = incoming.get("size_estimate", {}) or {}
    incoming_range = incoming_size.get("employee_range")
    result["size_estimate"] = {
        "employee_count": _merge_fact(
            existing_size.get("employee_count"), incoming_size.get("employee_count")
        ),
        "employee_range": (
            incoming_range
            if incoming_range and incoming_range != "unknown"
            else existing_size.get("employee_range", "unknown")
        ),
        "revenue_estimate": _merge_fact(
            existing_size.get("revenue_estimate"), incoming_size.get("revenue_estimate")
        ),
        "revenue_currency": existing_size.get("revenue_currency")
        or incoming_size.get("revenue_currency"),
    }

    result["locations"] = _merge_locations(result.get("locations"), incoming.get("locations"))

    result["registry_ids"] = {
        **(result.get("registry_ids") or {}),
        **(incoming.get("registry_ids") or {}),
    }
    result["social_profiles"] = {
        **(result.get("social_profiles") or {}),
        **(incoming.get("social_profiles") or {}),
    }

    result["tech_stack"] = _merge_tech_stack(result.get("tech_stack"), incoming.get("tech_stack"))
    result["signals"] = _merge_list_of_facts(result.get("signals"), incoming.get("signals"))

    existing_match = result.get("match") or {}
    incoming_match = incoming.get("match") or {}
    if (incoming_match.get("score") or 0) > (existing_match.get("score") or 0):
        result["match"] = incoming_match
    else:
        result["match"] = existing_match

    result["tags"] = _merge_list_of_strings(result.get("tags"), incoming.get("tags"))

    eh = result.get("outreach_history") or {}
    ih = incoming.get("outreach_history") or {}
    result["outreach_history"] = {
        "total_contacts": (eh.get("total_contacts") or 0) + (ih.get("total_contacts") or 0),
        "total_messages": (eh.get("total_messages") or 0) + (ih.get("total_messages") or 0),
        "last_contacted_at": _max_datetime(
            eh.get("last_contacted_at"), ih.get("last_contacted_at")
        ),
    }

    result["notes"] = _merge_notes(result.get("notes"), incoming.get("notes"))
    return result


def _merge_emails(
    a: list[dict[str, Any]] | None, b: list[dict[str, Any]] | None
) -> list[dict[str, Any]]:
    by_value: dict[str, dict[str, Any]] = {}
    for e in (a or []) + (b or []):
        v = e.get("value")
        if not v:
            continue
        if v not in by_value:
            by_value[v] = deepcopy(e)
        else:
            by_value[v]["confidence"] = max(
                by_value[v].get("confidence", 0.0), e.get("confidence", 0.0)
            )
            by_value[v]["is_verified"] = bool(
                by_value[v].get("is_verified") or e.get("is_verified")
            )
            if by_value[v].get("type") in (None, "unknown"):
                by_value[v]["type"] = e.get("type", "unknown")
    result = list(by_value.values())
    if result:
        best = max(result, key=lambda x: x.get("confidence", 0.0))
        for e in result:
            e["is_primary"] = e["value"] == best["value"]
    return result


def _merge_phones(
    a: list[dict[str, Any]] | None, b: list[dict[str, Any]] | None
) -> list[dict[str, Any]]:
    by_value: dict[str, dict[str, Any]] = {}
    for p in (a or []) + (b or []):
        v = p.get("value")
        if not v:
            continue
        if v not in by_value:
            by_value[v] = deepcopy(p)
        else:
            by_value[v]["confidence"] = max(
                by_value[v].get("confidence", 0.0), p.get("confidence", 0.0)
            )
            by_value[v]["is_whatsapp"] = bool(
                by_value[v].get("is_whatsapp") or p.get("is_whatsapp")
            )
            by_value[v]["is_telegram"] = bool(
                by_value[v].get("is_telegram") or p.get("is_telegram")
            )
    result = list(by_value.values())
    if result:
        best = max(result, key=lambda x: x.get("confidence", 0.0))
        for p in result:
            p["is_primary"] = p["value"] == best["value"]
    return result


def _merge_messengers(
    a: list[dict[str, Any]] | None, b: list[dict[str, Any]] | None
) -> list[dict[str, Any]]:
    by_key: dict[tuple[object, ...], dict[str, Any]] = {}
    for m in (a or []) + (b or []):
        key = (m.get("channel"), m.get("handle"))
        if not all(key):
            continue
        if key not in by_key:
            by_key[key] = deepcopy(m)
        else:
            by_key[key]["confidence"] = max(
                by_key[key].get("confidence", 0.0), m.get("confidence", 0.0)
            )
    return list(by_key.values())


def _merge_consent(a: dict[str, Any] | None, b: dict[str, Any] | None) -> dict[str, Any]:
    a = a or {}
    b = b or {}
    rank = {"denied": 3, "granted": 2, "not_required": 1, "unknown": 0}
    result = deepcopy(a)
    for field in ("email_opt_in", "messenger_opt_in"):
        av = a.get(field, "unknown")
        bv = b.get(field, "unknown")
        result[field] = av if rank.get(av, 0) >= rank.get(bv, 0) else bv
    result["email_opt_in_source"] = a.get("email_opt_in_source") or b.get("email_opt_in_source")
    result["email_opt_in_at"] = a.get("email_opt_in_at") or b.get("email_opt_in_at")
    result["gdpr_lawful_basis"] = (
        a.get("gdpr_lawful_basis") or b.get("gdpr_lawful_basis") or "unknown"
    )
    result["notes"] = _merge_notes(a.get("notes"), b.get("notes"))
    return result


def merge_contact_payload(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    """Merge two contact payloads."""
    result = deepcopy(existing)

    for field in ("full_name", "first_name", "last_name", "patronymic", "position"):
        result[field] = _merge_fact(result.get(field), incoming.get(field))

    for field in ("role_category", "seniority"):
        ev = result.get(field)
        iv = incoming.get(field)
        if ev in (None, "unknown") and iv not in (None, "unknown"):
            result[field] = iv
        else:
            result[field] = ev or iv or "unknown"

    result["emails"] = _merge_emails(result.get("emails"), incoming.get("emails"))
    result["phones"] = _merge_phones(result.get("phones"), incoming.get("phones"))
    result["messengers"] = _merge_messengers(result.get("messengers"), incoming.get("messengers"))

    result["social_profiles"] = {
        **(result.get("social_profiles") or {}),
        **(incoming.get("social_profiles") or {}),
    }

    existing_loc = result.get("location") or {}
    incoming_loc = incoming.get("location") or {}
    result["location"] = {
        "country": _merge_fact(existing_loc.get("country"), incoming_loc.get("country")),
        "city": _merge_fact(existing_loc.get("city"), incoming_loc.get("city")),
        "timezone": existing_loc.get("timezone") or incoming_loc.get("timezone"),
    }

    result["language_preference"] = result.get("language_preference") or incoming.get(
        "language_preference"
    )

    em = result.get("match") or {}
    im = incoming.get("match") or {}
    if (im.get("role_match_score") or 0) > (em.get("role_match_score") or 0):
        result["match"] = im
    else:
        result["match"] = em

    result["consent"] = _merge_consent(result.get("consent"), incoming.get("consent"))

    eh = result.get("outreach_history") or {}
    ih = incoming.get("outreach_history") or {}
    result["outreach_history"] = {
        "total_messages": (eh.get("total_messages") or 0) + (ih.get("total_messages") or 0),
        "last_contacted_at": _max_datetime(
            eh.get("last_contacted_at"), ih.get("last_contacted_at")
        ),
        "last_reply_at": _max_datetime(eh.get("last_reply_at"), ih.get("last_reply_at")),
        "replied_positive": bool(eh.get("replied_positive") or ih.get("replied_positive")),
    }

    result["tags"] = _merge_list_of_strings(result.get("tags"), incoming.get("tags"))
    result["notes"] = _merge_notes(result.get("notes"), incoming.get("notes"))
    return result
