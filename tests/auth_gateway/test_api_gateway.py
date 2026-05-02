import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from shared.config import get_settings


@pytest.fixture(autouse=True)
def clear_settings_cache(monkeypatch):
    for key, value in {
        "DEFAULT_LATENCY_MS": "0",
        "LATENCY_JITTER_MS": "0",
        "ERROR_RATE": "0",
    }.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def build_auth_app():
    app = FastAPI()

    @app.get("/health")
    async def health():
        return {"service": "auth", "status": "ok", "dependencies": {}}

    @app.post("/validate")
    async def validate(request: Request):
        auth_header = request.headers.get("authorization")
        correlation_id = request.headers.get("x-correlation-id")
        if auth_header != "Bearer token-analyst-soc-1":
            return JSONResponse({"detail": "invalid_token"}, status_code=401)
        return {
            "active": True,
            "client_id": "soc-1",
            "subject": "analyst",
            "correlation_id": correlation_id,
        }

    return app


def build_upstream_app(name: str):
    app = FastAPI()
    app.state.simulation_calls = []

    @app.api_route("/{path:path}", methods=["GET", "POST"])
    async def handle(path: str, request: Request):
        payload = await request.json() if request.method == "POST" else None
        if path == "health":
            return {"service": name, "status": "ok", "dependencies": {}}
        if path.startswith("simulate"):
            app.state.simulation_calls.append({"path": path, "payload": payload})
            return {"status": "updated", "path": path, "payload": payload}
        return {
            "service": name,
            "path": path,
            "method": request.method,
            "client_id": request.headers.get("x-client-id"),
            "correlation_id": request.headers.get("x-correlation-id"),
            "payload": payload,
        }

    return app


def create_gateway_client():
    from services.api_gateway.app import GatewayDependencies, create_app

    auth_client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=build_auth_app()),
        base_url="http://auth-service",
    )
    vault_client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=build_upstream_app("vault")),
        base_url="http://vault-service",
    )
    scan_client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=build_upstream_app("scan")),
        base_url="http://scan-service",
    )

    app = create_app(
        dependencies=GatewayDependencies(
            auth_client=auth_client,
            vault_client=vault_client,
            scan_client=scan_client,
        )
    )
    return TestClient(app)


def test_gateway_proxies_to_vault_after_token_validation():
    with create_gateway_client() as client:
        response = client.post(
            "/vault/secrets/current",
            json={"record": "vault-17"},
            headers={"authorization": "Bearer token-analyst-soc-1", "x-correlation-id": "corr-123"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "service": "vault",
        "path": "secrets/current",
        "method": "POST",
        "client_id": "soc-1",
        "correlation_id": "corr-123",
        "payload": {"record": "vault-17"},
    }


def test_gateway_rejects_invalid_tokens_and_tracks_auth_dependency_health():
    with create_gateway_client() as client:
        response = client.get("/scan/jobs/recent", headers={"authorization": "Bearer nope"})
        health = client.get("/health")
        metrics = client.get("/metrics")

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid_token"
    assert health.json()["dependencies"]["auth-service"]["healthy"] is True
    assert (
        'security_platform_dependency_health{dependency="auth-service",service="api-gateway"} 1.0'
        in metrics.text
    )


def test_gateway_emits_rate_limit_and_burst_metrics():
    with create_gateway_client() as client:
        headers = {"authorization": "Bearer token-analyst-soc-1", "x-forwarded-for": "203.0.113.10"}
        for _ in range(4):
            response = client.get("/scan/jobs/recent", headers=headers)

        metrics = client.get("/metrics")

    assert response.status_code == 429
    assert (
        'security_platform_gateway_rate_limited_requests_total{'
        'client_id="soc-1",service="api-gateway"} 1.0'
        in metrics.text
    )
    assert (
        'security_platform_gateway_burst_traffic_total{client_id="soc-1",'
        'ip_address="203.0.113.10",service="api-gateway"} 1.0'
        in metrics.text
    )


def test_gateway_homepage_renders_hybrid_console():
    with create_gateway_client() as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "Security Observability Platform" in response.text
    assert "Operator Console" in response.text
    assert "Grafana" in response.text
    assert "Service Status" in response.text


def test_gateway_incident_control_proxies_simulation_request():
    auth_app = build_auth_app()
    vault_app = build_upstream_app("vault")
    scan_app = build_upstream_app("scan")

    from services.api_gateway.app import GatewayDependencies, create_app

    auth_client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=auth_app),
        base_url="http://auth-service",
    )
    vault_client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=vault_app),
        base_url="http://vault-service",
    )
    scan_client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=scan_app),
        base_url="http://scan-service",
    )

    app = create_app(
        dependencies=GatewayDependencies(
            auth_client=auth_client,
            vault_client=vault_client,
            scan_client=scan_client,
        )
    )

    with TestClient(app) as client:
        response = client.post(
            "/ui/incidents/vault-dependency",
            data={"mode": "apply"},
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert vault_app.state.simulation_calls == [
        {
            "path": "simulate/dependency",
            "payload": {"dependency_failure": 1},
        }
    ]
