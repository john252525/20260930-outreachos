"""Prometheus metrics for orchestrator observability."""

from prometheus_client import Counter, Histogram

FLOWS_TOTAL = Counter(
    "orchestrator_flows_total",
    "Total flows created",
    ["status", "flow_type"],
)

FLOW_STEPS_TOTAL = Counter(
    "orchestrator_flow_steps_total",
    "Total flow steps processed",
    ["step_name", "status"],
)

FLOW_STEP_DURATION = Histogram(
    "orchestrator_flow_step_duration_seconds",
    "Flow step duration in seconds",
    ["step_name"],
    buckets=[0.1, 0.5, 1, 5, 10, 30, 60, 300, 900, 3600],
)

FLOW_STEP_RETRIES = Counter(
    "orchestrator_flow_step_retries_total",
    "Flow step retries",
    ["step_name"],
)
