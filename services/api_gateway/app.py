from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

import httpx
from fastapi import Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from services.api_gateway.metrics import (
    BURST_TRAFFIC,
    RATE_LIMITED_REQUESTS,
    SUSPICIOUS_REQUEST_SPIKES,
)
from shared.app import create_base_app
from shared.logging import correlation_id_var, get_logger
from shared.metrics import DEPENDENCY_HEALTH, SECURITY_EVENTS

SERVICE_NAME = "api-gateway"
SERVICE_PORT = 8000
BURST_THRESHOLD = 3
RATE_LIMIT_THRESHOLD = 4


@dataclass
class GatewayDependencies:
    auth_client: httpx.AsyncClient
    vault_client: httpx.AsyncClient
    scan_client: httpx.AsyncClient


def create_default_dependencies(settings) -> GatewayDependencies:
    return GatewayDependencies(
        auth_client=httpx.AsyncClient(base_url=settings.auth_service_url),
        vault_client=httpx.AsyncClient(base_url=settings.vault_service_url),
        scan_client=httpx.AsyncClient(base_url=settings.scan_service_url),
    )


async def fetch_json(client: httpx.AsyncClient, path: str) -> dict[str, Any] | None:
    try:
        response = await client.get(path)
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError):
        return None


async def gather_console_snapshot(app) -> dict[str, Any]:
    dependencies: GatewayDependencies = app.state.gateway_dependencies
    auth_health = await fetch_json(dependencies.auth_client, "/health")
    vault_health = await fetch_json(dependencies.vault_client, "/health")
    scan_health = await fetch_json(dependencies.scan_client, "/health")
    scan_queue = await fetch_json(dependencies.scan_client, "/queue")

    services = [
        {
            "name": "api-gateway",
            "status": "ok",
            "detail": "public edge, auth broker, and observability console",
        },
        {
            "name": "auth-service",
            "status": (auth_health or {}).get("status", "unknown"),
            "detail": "login, validate, auth anomaly counters",
        },
        {
            "name": "vault-service",
            "status": (vault_health or {}).get("status", "unknown"),
            "detail": "secrets access and dependency health",
        },
        {
            "name": "scan-service",
            "status": (scan_health or {}).get("status", "unknown"),
            "detail": "queue-backed scan execution",
        },
    ]

    queue_depth = (scan_queue or {}).get("depth", "unknown")
    active_alerts = len(
        [dep for dep in app.state.dependencies.values() if not dep.get("healthy", True)]
    )
    return {
        "services": services,
        "queue_depth": queue_depth,
        "active_dependency_issues": active_alerts,
        "links": {
            "grafana": "http://localhost:3000/d/security-service-health/service-health",
            "grafana_security": "http://localhost:3000/d/security-events/security-events",
            "grafana_triage": "http://localhost:3000/d/incident-triage/incident-triage",
            "grafana_infra": "http://localhost:3000/d/security-infrastructure/infrastructure",
            "prometheus": "http://localhost:9090",
            "alertmanager": "http://localhost:9093",
            "loki": "http://localhost:3100",
        },
    }


def render_console(snapshot: dict[str, Any], message: str | None = None) -> str:
    def incident_controls(slug: str) -> str:
        return (
            f'<form method="post" action="/ui/incidents/{slug}">'
            '<input type="hidden" name="mode" value="apply" />'
            "<button>Apply</button></form>"
            f'<form method="post" action="/ui/incidents/{slug}">'
            '<input type="hidden" name="mode" value="reset" />'
            '<button class="secondary">Reset</button></form>'
        )

    cards = "\n".join(
        f"""
        <article class=\"service-card status-{service['status']}\">
          <div class=\"service-meta\">{service['name']}</div>
          <h3>{service['status'].upper()}</h3>
          <p>{service['detail']}</p>
        </article>
        """
        for service in snapshot["services"]
    )
    notice = (
        f"<div class='notice'>{message}</div>"
        if message
        else (
            "<div class='notice muted'>Use this console to jump into Grafana and trigger "
            "demo incidents.</div>"
        )
    )
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <title>Security Observability Platform</title>
      <style>
        :root {{
          --ink: #13222e;
          --sand: #f2ebdc;
          --panel: #fff9ef;
          --accent: #0f766e;
          --danger: #b42318;
          --muted: #6c7a86;
          --line: #d9cfbf;
        }}
        * {{ box-sizing: border-box; }}
        body {{
          margin: 0;
          font-family: Georgia, "Times New Roman", serif;
          color: var(--ink);
          background:
            radial-gradient(circle at top left, rgba(15,118,110,0.14), transparent 30%),
            linear-gradient(135deg, #f9f4ea, #efe3d0 55%, #e3d6c3);
        }}
        main {{
          max-width: 1180px;
          margin: 0 auto;
          padding: 32px 20px 48px;
        }}
        .hero {{
          display: grid;
          grid-template-columns: 1.3fr 0.9fr;
          gap: 24px;
          align-items: start;
        }}
        .hero-card, .panel {{
          background: rgba(255, 249, 239, 0.92);
          border: 1px solid var(--line);
          border-radius: 22px;
          padding: 24px;
          box-shadow: 0 18px 40px rgba(19, 34, 46, 0.08);
        }}
        h1 {{
          margin: 0 0 12px;
          font-size: clamp(2.2rem, 4vw, 4.4rem);
          line-height: 0.95;
          letter-spacing: -0.04em;
        }}
        h2 {{
          margin: 0 0 14px;
          font-size: 1.25rem;
        }}
        p {{
          margin: 0 0 12px;
          line-height: 1.55;
        }}
        .kpis {{
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 12px;
          margin-top: 18px;
        }}
        .kpi {{
          padding: 16px;
          border-radius: 16px;
          background: #fff;
          border: 1px solid var(--line);
        }}
        .kpi strong {{
          display: block;
          font-size: 1.7rem;
          margin-top: 6px;
        }}
        .links {{
          display: flex;
          flex-wrap: wrap;
          gap: 10px;
          margin-top: 18px;
        }}
        .links a, button {{
          appearance: none;
          border: 0;
          border-radius: 999px;
          background: var(--ink);
          color: #fff;
          text-decoration: none;
          font-size: 0.95rem;
          padding: 11px 16px;
          cursor: pointer;
        }}
        .links a.secondary, button.secondary {{
          background: #dfe9e7;
          color: var(--ink);
        }}
        .layout {{
          display: grid;
          grid-template-columns: 1.2fr 0.8fr;
          gap: 24px;
          margin-top: 24px;
        }}
        .service-grid {{
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 14px;
        }}
        .service-card {{
          background: #fff;
          border-radius: 18px;
          padding: 18px;
          border: 1px solid var(--line);
        }}
        .service-meta {{
          font-size: 0.85rem;
          text-transform: uppercase;
          letter-spacing: 0.08em;
          color: var(--muted);
        }}
        .status-ok h3 {{ color: var(--accent); }}
        .status-degraded h3, .status-unknown h3 {{ color: #b76e00; }}
        .notice {{
          margin: 0 0 16px;
          padding: 12px 14px;
          border-radius: 14px;
          background: #fff;
          border: 1px solid var(--line);
        }}
        .muted {{ color: var(--muted); }}
        .incident {{
          display: grid;
          grid-template-columns: 1fr auto auto;
          gap: 10px;
          align-items: center;
          padding: 14px 0;
          border-top: 1px solid var(--line);
        }}
        .incident:first-of-type {{ border-top: 0; }}
        .incident small {{
          color: var(--muted);
          display: block;
          margin-top: 4px;
        }}
        @media (max-width: 900px) {{
          .hero, .layout {{ grid-template-columns: 1fr; }}
          .service-grid {{ grid-template-columns: 1fr; }}
          .incident {{ grid-template-columns: 1fr; }}
        }}
      </style>
    </head>
    <body>
      <main>
        <section class="hero">
          <div class="hero-card">
            <div class="service-meta">Hybrid Demo + Operator Console</div>
            <h1>Security Observability Platform</h1>
            <p>
              Operate the simulated security stack from the same public edge that fronts
              the services. Jump into Grafana when you want the deep dashboards, or use
              this console to drive incidents and narrate the platform story.
            </p>
            <div class="links">
              <a href="{snapshot['links']['grafana']}" target="_blank" rel="noreferrer">
                Service Health Dashboard
              </a>
              <a
                href="{snapshot['links']['grafana_security']}"
                target="_blank"
                rel="noreferrer"
              >
                Security Events
              </a>
              <a
                href="{snapshot['links']['grafana_triage']}"
                class="secondary"
                target="_blank"
                rel="noreferrer"
              >
                Incident Triage
              </a>
              <a
                href="{snapshot['links']['grafana_infra']}"
                class="secondary"
                target="_blank"
                rel="noreferrer"
              >
                Infrastructure
              </a>
              <a
                href="{snapshot['links']['prometheus']}"
                class="secondary"
                target="_blank"
                rel="noreferrer"
              >
                Prometheus
              </a>
              <a
                href="{snapshot['links']['alertmanager']}"
                class="secondary"
                target="_blank"
                rel="noreferrer"
              >
                Alertmanager
              </a>
              <a
                href="{snapshot['links']['loki']}"
                class="secondary"
                target="_blank"
                rel="noreferrer"
              >
                Loki
              </a>
            </div>
          </div>
          <div class="hero-card">
            <h2>Operator Snapshot</h2>
            <div class="kpis">
              <div class="kpi">
                <span>Services in view</span>
                <strong>{len(snapshot['services'])}</strong>
              </div>
              <div class="kpi">
                <span>Queue depth</span>
                <strong>{snapshot['queue_depth']}</strong>
              </div>
              <div class="kpi">
                <span>Dependency issues</span>
                <strong>{snapshot['active_dependency_issues']}</strong>
              </div>
              <div class="kpi">
                <span>Best next step</span>
                <strong>Grafana</strong>
              </div>
            </div>
          </div>
        </section>

        <section class="layout">
          <div class="panel">
            <h2>Service Status</h2>
            {notice}
            <p class="muted">
              This page keeps the quick operational summary close at hand and hands off to
              Grafana for deeper dashboard analysis.
            </p>
            <div class="service-grid">
              {cards}
            </div>
          </div>
          <div class="panel">
            <h2>Incident Controls</h2>
            <p class="muted">
              Run incident simulations to watch dashboards, logs, and alerts react.
            </p>
            <div class="incident">
              <div>
                <strong>Auth latency spike</strong>
                <small>Drive p95 latency up in auth-service.</small>
              </div>
              {incident_controls("auth-latency")}
            </div>
            <div class="incident">
              <div>
                <strong>Scan backlog</strong>
                <small>Grow the queue to trigger backlog and worker-health signals.</small>
              </div>
              {incident_controls("scan-backlog")}
            </div>
            <div class="incident">
              <div>
                <strong>Vault dependency failure</strong>
                <small>Flip the secrets backend unhealthy.</small>
              </div>
              {incident_controls("vault-dependency")}
            </div>
            <div class="incident">
              <div>
                <strong>Token validation spike</strong>
                <small>Generate repeated invalid token validations in auth-service.</small>
              </div>
              {incident_controls("token-spike")}
            </div>
            <div class="incident">
              <div>
                <strong>Memory pressure</strong>
                <small>Allocate ballast in scan-service to light up container memory alerts.</small>
              </div>
              {incident_controls("memory-pressure")}
            </div>
          </div>
        </section>
      </main>
    </body>
    </html>
    """


async def trigger_incident(
    incident_name: str,
    mode: str,
    dependencies: GatewayDependencies,
) -> str:
    if incident_name == "auth-latency":
        latency = 900 if mode == "apply" else 15
        await dependencies.auth_client.post("/simulate", json={"latency_ms": latency})
        return f"Auth latency incident set to {latency}ms."

    if incident_name == "scan-backlog":
        if mode == "apply":
            await dependencies.scan_client.post(
                "/simulate/backlog",
                json={"multiplier": 3, "jobs": 3},
            )
            return "Scan backlog incident applied."
        await dependencies.scan_client.post("/simulate/clear-queue")
        await dependencies.scan_client.post("/simulate/backlog", json={"multiplier": 1, "jobs": 0})
        return "Scan backlog reset."

    if incident_name == "vault-dependency":
        dependency_failure = 1 if mode == "apply" else 0
        await dependencies.vault_client.post(
            "/simulate/dependency",
            json={"dependency_failure": dependency_failure},
        )
        return f"Vault dependency failure set to {dependency_failure}."

    if incident_name == "token-spike":
        if mode == "reset":
            return (
                "Token spike is traffic-based. Restart Prometheus or wait for the rate window "
                "to age out."
            )
        for _ in range(200):
            await dependencies.auth_client.post(
                "/validate",
                headers={"authorization": "Bearer invalid-token"},
            )
        return "Token validation spike generated."

    if incident_name == "memory-pressure":
        enabled = 1 if mode == "apply" else 0
        await dependencies.scan_client.post("/simulate/memory-pressure", json={"enabled": enabled})
        return f"Memory pressure set to {enabled}."

    raise HTTPException(status_code=404, detail="unknown_incident")


def mark_dependency(app, dependency: str, healthy: bool, detail: str | None = None) -> None:
    app.state.dependencies[dependency] = {"healthy": healthy, "detail": detail or "ok"}
    DEPENDENCY_HEALTH.labels(service=SERVICE_NAME, dependency=dependency).set(1 if healthy else 0)


async def validate_token(request: Request, dependencies: GatewayDependencies) -> dict[str, Any]:
    logger = get_logger(SERVICE_NAME)
    correlation_id = correlation_id_var.get()
    auth_header = request.headers.get("authorization", "")
    response = await dependencies.auth_client.post(
        "/validate",
        headers={
            "authorization": auth_header,
            "x-correlation-id": correlation_id,
        },
    )

    if response.status_code != 200:
        healthy = response.status_code < 500
        detail = "token_validation_failed" if healthy else "auth_service_error"
        mark_dependency(request.app, "auth-service", healthy, detail)
        logger.info("auth_validation_failed", status_code=response.status_code)
        raise HTTPException(status_code=response.status_code, detail=response.json()["detail"])

    mark_dependency(request.app, "auth-service", True)
    return response.json()


def track_request_anomalies(request: Request, client_id: str) -> None:
    default_ip = request.client.host if request.client else "unknown"
    ip_address = request.headers.get("x-forwarded-for", default_ip)
    key = (client_id, ip_address)
    current = request.app.state.request_counts.get(key, 0) + 1
    request.app.state.request_counts[key] = current

    if current == BURST_THRESHOLD:
        BURST_TRAFFIC.labels(
            service=SERVICE_NAME,
            client_id=client_id,
            ip_address=ip_address,
        ).inc()
        SUSPICIOUS_REQUEST_SPIKES.labels(service=SERVICE_NAME, client_id=client_id).inc()
        SECURITY_EVENTS.labels(
            service=SERVICE_NAME,
            event_type="burst_traffic",
            reason="threshold_reached",
            client_id=client_id,
        ).inc()

    if current >= RATE_LIMIT_THRESHOLD:
        RATE_LIMITED_REQUESTS.labels(service=SERVICE_NAME, client_id=client_id).inc()
        SECURITY_EVENTS.labels(
            service=SERVICE_NAME,
            event_type="rate_limited",
            reason="threshold_exceeded",
            client_id=client_id,
        ).inc()
        raise HTTPException(status_code=429, detail="rate_limited")


async def proxy_request(
    request: Request,
    upstream_name: str,
    client: httpx.AsyncClient,
    path: str,
    client_id: str,
):
    logger = get_logger(SERVICE_NAME)
    correlation_id = correlation_id_var.get()
    json_payload = await request.json() if request.method == "POST" else None

    try:
        upstream_response = await client.request(
            request.method,
            f"/{path}",
            json=json_payload,
            headers={
                "x-correlation-id": correlation_id,
                "x-client-id": client_id,
            },
        )
    except httpx.HTTPError as exc:
        mark_dependency(request.app, upstream_name, False, "upstream_unavailable")
        logger.warning("upstream_unavailable", upstream=upstream_name, error=str(exc))
        raise HTTPException(status_code=502, detail="upstream_unavailable") from exc

    mark_dependency(
        request.app,
        upstream_name,
        upstream_response.status_code < 500,
        f"http_{upstream_response.status_code}",
    )
    return JSONResponse(status_code=upstream_response.status_code, content=upstream_response.json())


def create_app(dependencies: GatewayDependencies | None = None):
    app = create_base_app(SERVICE_NAME, SERVICE_PORT)
    app.state.gateway_dependencies = dependencies or create_default_dependencies(app.state.settings)
    app.state.request_counts = {}

    base_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def gateway_lifespan(inner_app):
        async with base_lifespan(inner_app):
            yield
        gateway_dependencies: GatewayDependencies = app.state.gateway_dependencies
        await gateway_dependencies.auth_client.aclose()
        await gateway_dependencies.vault_client.aclose()
        await gateway_dependencies.scan_client.aclose()

    app.router.lifespan_context = gateway_lifespan

    @app.get("/", response_class=HTMLResponse)
    async def homepage(message: str | None = None):
        snapshot = await gather_console_snapshot(app)
        return HTMLResponse(render_console(snapshot, message))

    @app.post("/ui/incidents/{incident_name}")
    async def control_incident(incident_name: str, mode: str = Form(...)):
        message = await trigger_incident(incident_name, mode, app.state.gateway_dependencies)
        return RedirectResponse(url=f"/?message={message}", status_code=303)

    @app.api_route("/vault/{path:path}", methods=["GET", "POST"])
    async def proxy_vault(path: str, request: Request):
        auth_payload = await validate_token(request, app.state.gateway_dependencies)
        client_id = auth_payload["client_id"]
        track_request_anomalies(request, client_id)
        return await proxy_request(
            request,
            "vault-service",
            app.state.gateway_dependencies.vault_client,
            path,
            client_id,
        )

    @app.api_route("/scan/{path:path}", methods=["GET", "POST"])
    async def proxy_scan(path: str, request: Request):
        auth_payload = await validate_token(request, app.state.gateway_dependencies)
        client_id = auth_payload["client_id"]
        track_request_anomalies(request, client_id)
        return await proxy_request(
            request,
            "scan-service",
            app.state.gateway_dependencies.scan_client,
            path,
            client_id,
        )

    return app


app = create_app()
