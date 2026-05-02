# Runbook

## Auth-service latency spike

- Trigger: `python -m scripts.incidents.auth_latency --mode apply`
- Expected signals: `HighP95Latency` on `auth-service`, rising gateway latency, auth logs showing updated simulation state.
- Triage:
  - open Service Health and compare `auth-service` p95 against peers
  - confirm `auth-service` is still up but slower
  - inspect Loki for `simulation_updated`
- Mitigation:
  - reset simulation
  - if real, reduce load or scale the service
- Recovery check: latency falls back below threshold and alert resolves

## Scan-service queue backlog

- Trigger: `python -m scripts.incidents.scan_backlog --mode apply`
- Expected signals: queue depth growth, `ScanQueueBacklogHigh`, scan worker dependency marked backlogged.
- Triage:
  - open Security Events and Incident Triage
  - verify `security_platform_queue_depth`
  - review scan worker status from `/queue`
- Mitigation:
  - process jobs or reduce synthetic multiplier
  - investigate worker throughput
- Recovery check: queue depth returns toward zero and dependency health flips back to healthy

## Vault dependency failure

- Trigger: `python -m scripts.incidents.vault_dependency_failure --mode apply`
- Expected signals: `SecurityDependencyUnhealthy`, secrets access errors, degraded `/health`.
- Triage:
  - inspect dependency health panel
  - query Loki for vault logs
  - confirm secret reads return `503`
- Mitigation:
  - reset dependency simulation
  - verify the backend recovers and health returns to `ok`

## API gateway token validation spike

- Trigger: `python -m scripts.incidents.gateway_token_spike --mode apply`
- Expected signals: `TokenValidationSpike`, `SuspiciousTrafficSpike`, increased invalid token events.
- Triage:
  - use Security Events to identify the failing client IDs
  - confirm the gateway is still serving valid traffic
  - inspect auth logs for invalid token patterns
- Mitigation:
  - stop the traffic generator
  - verify the source client or IP
- Recovery check: token failure rate declines and alert resolves

## Container memory pressure

- Trigger: `python -m scripts.incidents.container_memory_pressure --mode apply`
- Expected signals: `ContainerMemoryPressure`, elevated cAdvisor working set, memory pressure gauge set to `1`.
- Triage:
  - inspect Infrastructure dashboard
  - confirm which container crossed the threshold
  - look for recent simulation updates in service logs
- Mitigation:
  - reset the simulation
  - if real, restart the container or investigate leaks
- Recovery check: memory drops below threshold and the alert clears
