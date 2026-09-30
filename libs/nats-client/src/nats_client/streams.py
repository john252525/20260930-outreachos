"""JetStream stream definitions."""

from dataclasses import dataclass


@dataclass(frozen=True)
class StreamConfig:
    name: str
    subjects: list[str]
    max_age_seconds: int
    max_bytes: int
    storage: str = "file"
    retention: str = "limits"


STREAMS: list[StreamConfig] = [
    StreamConfig(
        name="TENANTS",
        subjects=["tenant.>"],
        max_age_seconds=365 * 24 * 3600,
        max_bytes=256 * 1024 * 1024,
    ),
    StreamConfig(
        name="BRIEFS",
        subjects=[
            "brief.>",
            "icp.>",
            "contacts.>",
            "message.>",
            "reply.>",
            "experiment.>",
        ],
        max_age_seconds=365 * 24 * 3600,
        max_bytes=512 * 1024 * 1024,
    ),
    StreamConfig(
        name="LLM_CALLS",
        subjects=["llm.>", "cost.>"],
        max_age_seconds=7 * 24 * 3600,
        max_bytes=256 * 1024 * 1024,
    ),
    StreamConfig(
        name="SYSTEM",
        subjects=["system.>"],
        max_age_seconds=7 * 24 * 3600,
        max_bytes=64 * 1024 * 1024,
        retention="workqueue",
    ),
]
