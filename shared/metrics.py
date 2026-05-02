from time import time

from prometheus_client import Counter, Gauge, Histogram, Info

REQUEST_COUNT = Counter(
    "security_platform_requests_total",
    "Total HTTP requests handled by the service",
    ["service", "endpoint", "method", "status_code"],
)

REQUEST_LATENCY = Histogram(
    "security_platform_request_latency_seconds",
    "HTTP request latency in seconds",
    ["service", "endpoint", "method"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

ERROR_COUNT = Counter(
    "security_platform_errors_total",
    "Application errors by service and reason",
    ["service", "endpoint", "reason"],
)

SECURITY_EVENTS = Counter(
    "security_platform_security_events_total",
    "Security events emitted by the service",
    ["service", "event_type", "reason", "client_id"],
)

DEPENDENCY_HEALTH = Gauge(
    "security_platform_dependency_health",
    "Dependency health state where 1 is healthy and 0 is unhealthy",
    ["service", "dependency"],
)

QUEUE_DEPTH = Gauge(
    "security_platform_queue_depth",
    "Queue depth for queued workloads",
    ["service", "queue_name"],
)

SERVICE_UPTIME = Gauge(
    "security_platform_uptime_seconds",
    "Service uptime in seconds",
    ["service"],
)

SERVICE_INFO = Info(
    "security_platform_service",
    "Static service metadata",
)

MEMORY_PRESSURE = Gauge(
    "security_platform_memory_pressure",
    "Synthetic memory pressure toggle",
    ["service"],
)


def update_uptime(service_name: str, started_at: float) -> None:
    SERVICE_UPTIME.labels(service=service_name).set(max(0.0, time() - started_at))
