# Architecture

## Overview

The platform simulates a security infrastructure control plane with four services:

- `api-gateway` receives user traffic, validates tokens with `auth-service`, and proxies requests to `vault-service` and `scan-service`.
- `auth-service` simulates login and token validation, including invalid auth headers, token validation failures, and failed login spikes.
- `vault-service` simulates a secrets backend and surfaces dependency health changes and secrets access errors.
- `scan-service` simulates queued scan jobs and exposes backlog, queue depth, job duration, and failure metrics.

## Observability path

1. Each FastAPI service exposes `/metrics` and `/health`.
2. Prometheus scrapes all services, Node Exporter, and cAdvisor.
3. Recording rules calculate p95 latency, 5xx rate, security event rates, and queue depth signals.
4. Alert rules classify issues into `critical`, `warning`, and `info`, and Alertmanager forwards them to a local webhook receiver.
5. Grafana visualizes service health, infrastructure state, security events, and incident triage views.
6. Services write structured JSON logs to `/var/log/security-platform`, and Promtail ships those files to Loki for triage queries.

## Security-specific signals

This project intentionally emphasizes security infrastructure telemetry:

- failed token validations
- invalid authorization headers
- failed login spikes
- suspicious request bursts by IP and client ID
- rate-limited requests
- secrets access errors
- scan backlog depth
- dependency health state

## Local and EC2 parity

The same Docker Compose stack runs locally and on EC2. Environment differences are limited to external host details, persistent volume placement, and optional CloudWatch agent setup. This keeps screenshots, alerts, and dashboards consistent across local demos and cloud deployment.
