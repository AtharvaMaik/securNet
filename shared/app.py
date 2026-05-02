import random
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from shared.config import get_settings
from shared.logging import configure_logging
from shared.metrics import MEMORY_PRESSURE, SERVICE_INFO, update_uptime
from shared.middleware import observability_middleware


def maybe_fail(settings) -> None:
    if settings.error_rate > 0 and random.random() < settings.error_rate:
        raise RuntimeError("synthetic_failure")


def create_base_app(service_name: str, port: int) -> FastAPI:
    settings = get_settings(service_name, port).model_copy(deep=True)
    started_at = time.time()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        configure_logging(service_name, settings.log_dir)
        app.state.settings = settings
        app.state.started_at = started_at
        SERVICE_INFO.info({"service_name": service_name, "port": str(port)})
        MEMORY_PRESSURE.labels(service=service_name).set(settings.memory_pressure_enabled)
        yield

    app = FastAPI(title=service_name, lifespan=lifespan)
    app.state.settings = settings
    app.state.started_at = started_at
    app.state.dependencies = {}
    app.middleware("http")(observability_middleware)

    @app.get("/health")
    async def health():
        update_uptime(service_name, started_at)
        dependencies = getattr(app.state, "dependencies", {})
        healthy = all(item.get("healthy", True) for item in dependencies.values())
        return {
            "service": service_name,
            "status": "ok" if healthy else "degraded",
            "dependencies": dependencies,
        }

    @app.get("/metrics")
    async def metrics():
        update_uptime(service_name, started_at)
        return PlainTextResponse(generate_latest().decode("utf-8"), media_type=CONTENT_TYPE_LATEST)

    return app
