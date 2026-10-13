"""Thompson Sampling for multi-armed bandits.

For each arm we model the success rate with a Beta(alpha, beta) posterior,
where alpha = successes + 1 and beta = failures + 1 (uniform prior). We draw a
sample from each arm's posterior and pick the arm with the highest sample.
"""

import random
from typing import Any


class ThompsonSampling:
    @staticmethod
    def choose_variant(variants_stats: list[dict[str, Any]]) -> str | None:
        """variants_stats: [{variant_id, sent, positive_replied}]."""
        if not variants_stats:
            return None
        best_id: str | None = None
        best_sample = -1.0
        for v in variants_stats:
            sent = int(v.get("sent", 0) or 0)
            positives = int(v.get("positive_replied", 0) or 0)
            positives = min(positives, sent)
            alpha = positives + 1
            beta = (sent - positives) + 1
            sample = random.betavariate(alpha, beta)
            if sample > best_sample:
                best_sample = sample
                best_id = str(v["variant_id"])
        return best_id
