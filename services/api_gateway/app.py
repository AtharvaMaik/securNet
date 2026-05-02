from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

import httpx
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

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
