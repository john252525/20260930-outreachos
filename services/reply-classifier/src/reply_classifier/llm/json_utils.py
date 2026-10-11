"""Robust JSON parsing for LLM output."""

import json
import re

_FENCE_RE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)


class LLMJSONError(Exception):
    """Raised when the LLM output cannot be parsed as JSON."""


def parse_json_strict(raw: str) -> dict[str, object]:
    """Parse JSON from an LLM response, stripping markdown fences if present."""
    text = raw.strip()

    m = _FENCE_RE.match(text)
    if m:
        text = m.group(1).strip()

    first = text.find("{")
    last = text.rfind("}")
    if first != -1 and last != -1 and last > first:
        text = text[first : last + 1]

    try:
        parsed = json.loads(text, strict=False)
    except json.JSONDecodeError as e:
        raise LLMJSONError(f"LLM returned invalid JSON: {e}") from e

    if not isinstance(parsed, dict):
        raise LLMJSONError("LLM returned JSON that is not an object")
    return parsed
