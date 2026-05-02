# Dashboards

## Service Health

Use this dashboard first to answer:

- Which service is down or degraded?
- Is the issue latency, error rate, or total request loss?
- Which dependency flipped unhealthy?

Primary panels:

- service up/down status
- requests per second
- 5xx error rate
- p95 latency
- dependency health

## Infrastructure

Use this dashboard to confirm whether the incident is service logic or host/container pressure.

Primary panels:

- host CPU and memory
- container CPU and working set memory
- disk availability
- network receive rate

## Security Events

Use this dashboard to triage suspicious auth or traffic behavior.

Primary panels:

- failed logins
- token validation failures
- burst traffic by IP and client ID
- rate-limited requests
- secrets access errors
- scan backlog depth

## Incident Triage

Use this dashboard once an alert fires.

Primary panels:

- alert-driving metrics on one screen
- dependency state by service
- recent logs from Loki

This dashboard is meant to shorten the jump between alert notification and root-cause confirmation.
