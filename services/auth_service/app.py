from fastapi import Header, HTTPException
from pydantic import BaseModel

from shared.app import create_base_app, maybe_fail
from shared.logging import get_logger
from shared.metrics import MEMORY_PRESSURE, SECURITY_EVENTS

SERVICE_NAME = "auth-service"
SERVICE_PORT = 8001


class LoginRequest(BaseModel):
    username: str
    password: str
    client_id: str = "unknown"


class AuthSimulationRequest(BaseModel):
    latency_ms: int | None = None
    token_failure_multiplier: int | None = None
    failed_login_multiplier: int | None = None
    memory_pressure_enabled: int | None = None


def issue_token(username: str, client_id: str) -> str:
    return f"token-{username}-{client_id}"


def parse_token(token: str) -> tuple[str, str] | None:
    if not token.startswith("token-"):
        return None
    body = token.removeprefix("token-")
    if "-" not in body:
        return None
    username, client_id = body.split("-", 1)
    if not username or not client_id:
        return None
    return username, client_id


def record_security_event(event_type: str, reason: str, client_id: str, multiplier: int) -> None:
    for _ in range(max(1, multiplier)):
        SECURITY_EVENTS.labels(
            service=SERVICE_NAME,
            event_type=event_type,
            reason=reason,
            client_id=client_id,
        ).inc()


def create_app():
    app = create_base_app(SERVICE_NAME, SERVICE_PORT)
    logger = get_logger(SERVICE_NAME)
    app.state.memory_ballast = []

    @app.post("/login")
    async def login(payload: LoginRequest):
        if payload.password != "correct-password":
            record_security_event(
                "failed_login",
                "invalid_credentials",
                payload.client_id,
                app.state.settings.failed_login_spike_multiplier,
            )
            logger.info(
                "login_failed",
                username=payload.username,
                client_id=payload.client_id,
                reason="invalid_credentials",
            )
            raise HTTPException(status_code=401, detail="invalid_credentials")

        token = issue_token(payload.username, payload.client_id)
        logger.info("login_succeeded", username=payload.username, client_id=payload.client_id)
        return {
            "access_token": token,
            "token_type": "bearer",
            "expires_in": 300,
            "client_id": payload.client_id,
        }

    @app.post("/validate")
    async def validate(
        authorization: str | None = Header(default=None),
        x_fault_injection: str | None = Header(default=None),
    ):
        if x_fault_injection == "auth-5xx":
            logger.warning("auth_fault_injected", fault="auth-5xx")
            raise HTTPException(status_code=503, detail="synthetic_auth_failure")

        try:
            maybe_fail(app.state.settings)
        except RuntimeError as exc:
            logger.warning("auth_fault_randomized", error=str(exc))
            raise HTTPException(status_code=503, detail="synthetic_auth_failure") from exc

        if not authorization or not authorization.startswith("Bearer "):
            record_security_event(
                "invalid_auth_header",
                "invalid_authorization_header",
                "unknown",
                1,
            )
            logger.info("validate_failed", reason="invalid_authorization_header")
            raise HTTPException(status_code=401, detail="invalid_authorization_header")

        token = authorization.removeprefix("Bearer ").strip()
        parsed = parse_token(token)
        if parsed is None:
            record_security_event(
                "token_validation_failure",
                "invalid_token",
                "unknown",
                app.state.settings.token_failure_spike_multiplier,
            )
            logger.info("validate_failed", reason="invalid_token")
            raise HTTPException(status_code=401, detail="invalid_token")

        username, client_id = parsed
        logger.info("validate_succeeded", username=username, client_id=client_id)
        return {"active": True, "client_id": client_id, "subject": username}

    @app.post("/simulate")
    async def simulate_auth_state(request: AuthSimulationRequest):
        if request.latency_ms is not None:
            app.state.settings.default_latency_ms = request.latency_ms
        if request.token_failure_multiplier is not None:
            app.state.settings.token_failure_spike_multiplier = request.token_failure_multiplier
        if request.failed_login_multiplier is not None:
            app.state.settings.failed_login_spike_multiplier = request.failed_login_multiplier
        if request.memory_pressure_enabled is not None:
            app.state.settings.memory_pressure_enabled = request.memory_pressure_enabled
            MEMORY_PRESSURE.labels(service=SERVICE_NAME).set(request.memory_pressure_enabled)
            blocks = 256 * request.memory_pressure_enabled
            app.state.memory_ballast = [b"x" * 1024 * 1024 for _ in range(blocks)]
        logger.info("simulation_updated", **request.model_dump(exclude_none=True))
        return {"status": "updated", "settings": request.model_dump(exclude_none=True)}

    return app


app = create_app()
