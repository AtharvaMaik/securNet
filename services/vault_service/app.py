from fastapi import HTTPException
from pydantic import BaseModel

from shared.app import create_base_app
from shared.metrics import DEPENDENCY_HEALTH, SECURITY_EVENTS


class VaultRuntime:
    def __init__(self, service_name: str, settings) -> None:
        self.service_name = service_name
        self.settings = settings
        self.secrets = {
            "db-password": "super-secret-password",
            "api-token": "token-1234",
        }

    def dependency_healthy(self) -> bool:
        return self.settings.vault_dependency_failure == 0

    def sync_dependency_state(self, app) -> None:
        healthy = self.dependency_healthy()
        app.state.dependencies["vault-backend"] = {
            "healthy": healthy,
            "status": "ok" if healthy else "degraded",
        }
        DEPENDENCY_HEALTH.labels(
            service=self.service_name,
            dependency="vault-backend",
        ).set(1 if healthy else 0)

    def read_secret(self, app, secret_name: str, client_id: str) -> dict[str, str]:
        self.sync_dependency_state(app)
        if not self.dependency_healthy():
            SECURITY_EVENTS.labels(
                service=self.service_name,
                event_type="secret_access",
                reason="dependency_unavailable",
                client_id=client_id,
            ).inc()
            raise HTTPException(status_code=503, detail="vault dependency unavailable")

        if secret_name not in self.secrets:
            SECURITY_EVENTS.labels(
                service=self.service_name,
                event_type="secret_access",
                reason="not_found",
                client_id=client_id,
            ).inc()
            raise HTTPException(status_code=404, detail="secret not found")

        return {
            "name": secret_name,
            "value": self.secrets[secret_name],
            "source": "in-memory-vault",
        }


class VaultSimulationRequest(BaseModel):
    dependency_failure: int


def create_app():
    app = create_base_app("vault-service", 8002)
    runtime = VaultRuntime("vault-service", app.state.settings)
    app.state.vault_runtime = runtime
    runtime.sync_dependency_state(app)

    @app.get("/secrets/{secret_name}")
    async def get_secret(secret_name: str, client_id: str = "unknown"):
        return runtime.read_secret(app, secret_name, client_id)

    @app.post("/simulate/dependency")
    async def simulate_dependency(request: VaultSimulationRequest):
        app.state.settings.vault_dependency_failure = request.dependency_failure
        runtime.sync_dependency_state(app)
        return {
            "status": "updated",
            "dependency_failure": request.dependency_failure,
        }

    return app


app = create_app()
