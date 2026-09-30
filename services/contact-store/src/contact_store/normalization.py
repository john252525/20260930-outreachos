"""Pure normalization helpers for dedup fingerprints."""

import re
import unicodedata

from stdnum.ru import inn as ru_inn
from stdnum.ru import ogrn as ru_ogrn

_WS_RE = re.compile(r"\s+")
_NON_ALNUM_RE = re.compile(r"[^\w\s\-]", re.UNICODE)
_LEGAL_SUFFIXES = {
    "ооо",
    "оао",
    "зао",
    "пао",
    "ип",
    "нко",
    "ано",
    "ао",
    "llc",
    "ltd",
    "inc",
    "corp",
    "corporation",
    "co",
    "company",
    "gmbh",
    "ag",
    "sa",
    "sas",
    "sarl",
    "bv",
    "nv",
    "plc",
    "limited",
    "group",
    "holdings",
}


def normalize_whitespace(s: str) -> str:
    return _WS_RE.sub(" ", s.strip())


def normalize_company_name(name: str) -> str:
    """Normalize a company name for fingerprinting.

    - lowercase
    - strips legal suffixes (ООО/LLC/Inc...) at start and end
    - removes redundant punctuation
    - collapses whitespace
    """
    if not name:
        return ""
    s = unicodedata.normalize("NFKC", name).lower()
    s = s.replace("«", "").replace("»", "").replace('"', "").replace("'", "")
    s = _NON_ALNUM_RE.sub(" ", s)
    s = normalize_whitespace(s)

    tokens = s.split()
    while tokens and tokens[0] in _LEGAL_SUFFIXES:
        tokens.pop(0)
    while tokens and tokens[-1] in _LEGAL_SUFFIXES:
        tokens.pop()
    return " ".join(tokens)


def normalize_domain(domain: str | None) -> str | None:
    """example.com, www.example.com, https://example.com/path -> example.com."""
    if not domain:
        return None
    s = domain.strip().lower()
    for prefix in ("https://", "http://"):
        if s.startswith(prefix):
            s = s[len(prefix) :]
    s = s.split("/", 1)[0]
    if s.startswith("www."):
        s = s[4:]
    s = s.split(":", 1)[0]
    if not s or "." not in s:
        return None
    return s


def normalize_email(email: str | None) -> str | None:
    """lowercase, strip. Gmail-specific dot rules are NOT applied."""
    if not email:
        return None
    s = email.strip().lower()
    if "@" not in s:
        return None
    return s


def normalize_phone(phone: str | None, default_country: str = "RU") -> str | None:
    """Normalize to E.164. For RU: +7XXXXXXXXXX. Others get a leading +."""
    if not phone:
        return None
    digits = re.sub(r"\D", "", phone)
    if not digits:
        return None

    if default_country == "RU":
        if len(digits) == 11 and digits[0] in ("7", "8"):
            return "+7" + digits[1:]
        if len(digits) == 10:
            return "+7" + digits

    return "+" + digits


def normalize_person_name(name: str) -> str:
    """lowercase, collapse whitespace, replace dots (initials)."""
    if not name:
        return ""
    s = unicodedata.normalize("NFKC", name).lower()
    s = s.replace(".", " ")
    s = _NON_ALNUM_RE.sub(" ", s)
    return normalize_whitespace(s)


def normalize_inn(value: str | None) -> str | None:
    if not value:
        return None
    digits = re.sub(r"\D", "", value)
    if not digits:
        return None
    if ru_inn.is_valid(digits):
        return digits
    return None


def normalize_ogrn(value: str | None) -> str | None:
    if not value:
        return None
    digits = re.sub(r"\D", "", value)
    if not digits:
        return None
    if ru_ogrn.is_valid(digits):
        return digits
    return None
