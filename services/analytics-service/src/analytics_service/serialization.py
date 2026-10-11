"""JSON helpers for caching metric payloads (Decimal/date aware)."""

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID


def _default(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, UUID):
        return str(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def dumps(value: Any) -> str:
    return json.dumps(value, default=_default)


def loads(raw: str) -> Any:
    return json.loads(raw)
