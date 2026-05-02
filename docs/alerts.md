# Alerts

## Severity model

- `critical`: immediate outage or high-confidence user-impacting issue
- `warning`: sustained reliability or security degradation that needs triage
- `info`: early signal or noisy event worth watching but not paging immediately

## Alert catalog

### `SecurityServiceDown` (`critical`)
- Meaning: Prometheus cannot scrape a core service for at least 1 minute.
- Threshold reasoning: a 30-second hold keeps the local lab responsive while still filtering brief restarts.
- Likely causes: container crash, networking issue, compose service stopped, bad bind port.
- False-positive notes: deployment restarts or local rebuilds can briefly trigger this.
- First steps: check `docker compose ps`, open the service logs in Loki, inspect `/health` once the service responds again.

### `SecurityDependencyUnhealthy` (`critical`)
- Meaning: a service explicitly reported an unhealthy dependency.
- Threshold reasoning: dependency health is application-aware, so a 30-second sustained zero is enough in this lab.
- Likely causes: vault backend simulation enabled, token validation failures, scan worker backlog state.
- False-positive notes: expected during intentional incident simulations.
- First steps: use the Incident Triage dashboard, then the service-specific runbook section.

### `HighErrorRate` (`warning`)
- Meaning: 5xx responses are above 0.05 requests per second over five minutes.
- Threshold reasoning: the rate still uses a 5-minute lookback, but the alert only waits 30 seconds to fire in demos.
- Likely causes: injected service failures, upstream proxy issues, dependency loss.
- Noise reduction: leave the threshold low for demos, but raise it if the traffic generator is extremely sparse.

### `HighP95Latency` (`warning`)
- Meaning: p95 request latency exceeds 750ms.
- Threshold reasoning: much higher than the normal synthetic latency baseline, with a 30-second hold for quicker verification.
- Likely causes: auth latency incident, overloaded container, upstream queue pressure.
- Noise reduction: if you intentionally raise the default baseline latency, adjust this threshold too.

### `ContainerCpuPressure` (`warning`)
- Meaning: container CPU is high over 10 minutes.
- Threshold reasoning: CPU keeps a longer 2-minute hold because short bursts are common and noisy.
- Likely causes: traffic replay, log storms, tight loops in services.
- Noise reduction: use longer `for` windows than the memory alerts.

### `ContainerMemoryPressure` (`critical`)
- Meaning: a container working set exceeds 400MB for 5 minutes.
- Threshold reasoning: useful for a demo host while still meaningfully above steady state, with a 30-second hold for labs.
- Likely causes: intentional memory pressure simulation, runaway buffering, container leak.
- Noise reduction: if running on a very large host, adjust upward to preserve signal.

### `HostDiskPressure` (`warning`)
- Meaning: filesystem free space is below 15%.
- Threshold reasoning: conservative enough to act before log growth or TSDB writes fail, but still held for 2 minutes to reduce noise.
- Likely causes: Loki chunks, Prometheus data growth, Docker volumes.
- Noise reduction: exclude transient filesystems from the query as already configured, including Docker Desktop `9p` mounts on Windows/WSL.

### `FailedLoginSpike` (`warning`)
- Meaning: failed login event rate is elevated over 5 minutes.
- Threshold reasoning: small enough to show during demos, high enough to avoid one-off typos, with a 30-second hold.
- Likely causes: brute-force simulation, bad credentials in a client, auth misuse.
- Noise reduction: pair with client ID and burst panels to avoid overreacting to one noisy test client.

### `TokenValidationSpike` (`warning`)
- Meaning: invalid bearer tokens are being presented repeatedly.
- Threshold reasoning: token misuse should show quickly because it often points to abuse or broken clients, so it uses a 30-second hold.
- Likely causes: malformed tokens, replay attempts, gateway misuse.
- Noise reduction: if running scripted tests, reset the incident after verification.

### `ScanQueueBacklogHigh` (`warning`)
- Meaning: scan queue depth exceeds four jobs.
- Threshold reasoning: the scan worker is intentionally small, so queue growth should show early, with a 30-second hold.
- Likely causes: backlog simulation, slower worker processing, sudden demand surge.
- Noise reduction: queue depth alone is not enough; also inspect worker health and job durations.

### `SecretsAccessErrorSurge` (`warning`)
- Meaning: vault-service is emitting elevated secret access security events.
- Threshold reasoning: secrets access failures are lower volume but high-interest in security infrastructure, so they use a 30-second hold here.
- Likely causes: dependency loss, missing secret requests, bad access flow.
- Noise reduction: split `not_found` from dependency failures during tuning if you want sharper paging.

### `SuspiciousTrafficSpike` (`info`)
- Meaning: burst traffic or rate-limited request behavior exceeded a low threshold.
- Threshold reasoning: designed as an investigation nudge, not a pager, with a short 30-second hold for demos.
- Likely causes: scripted traffic spike, abusive client, load-testing behavior.
- Noise reduction: keep this `info` unless you see a pattern that correlates with user-facing impact.
