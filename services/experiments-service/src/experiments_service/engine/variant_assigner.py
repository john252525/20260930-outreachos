"""Deterministic variant assignment.

The same ``(experiment_id, contact_id)`` pair always maps to the same variant,
which keeps a contact in a single arm of an experiment.
"""

import hashlib
from typing import Any


class VariantAssigner:
    def assign(
        self,
        *,
        experiment_id: str,
        contact_id: str,
        variants: list[dict[str, Any]],
    ) -> str | None:
        """Return a variant id, or ``None`` when there are no variants."""
        if not variants:
            return None

        key = f"{experiment_id}:{contact_id}"
        digest = hashlib.sha256(key.encode()).hexdigest()
        bucket = int(digest[:8], 16) / 0xFFFFFFFF

        cumulative = 0.0
        for v in variants:
            cumulative += float(v.get("weight", 0.0) or 0.0)
            if bucket < cumulative:
                return str(v["id"])
        return str(variants[-1]["id"])
