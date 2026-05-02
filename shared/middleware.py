import asyncio
import random
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response

from shared.logging import correlation_id_var, get_logger
from shared.metrics import ERROR_COUNT, REQUEST_COUNT, REQUEST_LATENCY


async def observability_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    settings = request.app.state.settings
    correlation_id = request.headers.get("x-correlation-id", str(uuid.uuid4()))
    correlation_id_var.set(correlation_id)
    logger = get_logger(settings.service_name)
    start = time.perf_counter()

    base_latency = settings.default_latency_ms / 1000
    jitter = random.randint(0, settings.latency_jitter_ms) / 1000
    await asyncio.sleep(base_latency + jitter)

    try:
        response = await call_next(request)
    except Exception as exc:  # pragma: no cover - defensive
        ERROR_COUNT.labels(
            service=settings.service_name,
            endpoint=request.url.path,
            reason=type(exc).__name__,
        ).inc()
        logger.exception("request_failed", path=request.url.path, error=str(exc))
        raise

    elapsed = time.perf_counter() - start
    REQUEST_LATENCY.labels(
        service=settings.service_name,
        endpoint=request.url.path,
        method=request.method,
    ).observe(elapsed)
    REQUEST_COUNT.labels(
        service=settings.service_name,
        endpoint=request.url.path,
        method=request.method,
        status_code=str(response.status_code),
    ).inc()
    response.headers["x-correlation-id"] = correlation_id
    logger.info(
        "request_complete",
        path=request.url.path,
        method=request.method,
        status_code=response.status_code,
        latency_seconds=round(elapsed, 4),
    )
    if response.status_code >= 500:
        ERROR_COUNT.labels(
            service=settings.service_name,
            endpoint=request.url.path,
            reason="http_5xx",
        ).inc()
    return response
