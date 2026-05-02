from prometheus_client import Counter

SUSPICIOUS_REQUEST_SPIKES = Counter(
    "security_platform_gateway_suspicious_request_spikes_total",
    "Suspicious request spikes detected by the API gateway",
    ["service", "client_id"],
)

RATE_LIMITED_REQUESTS = Counter(
    "security_platform_gateway_rate_limited_requests_total",
    "Requests rejected by the API gateway rate limiter",
    ["service", "client_id"],
)

BURST_TRAFFIC = Counter(
    "security_platform_gateway_burst_traffic_total",
    "Burst traffic detected by IP and client identity",
    ["service", "client_id", "ip_address"],
)
