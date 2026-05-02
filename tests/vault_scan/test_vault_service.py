from fastapi.testclient import TestClient

from services.vault_service.app import create_app


def test_secret_access_returns_value_and_tracks_health():
    app = create_app()

    with TestClient(app) as client:
        response = client.get("/secrets/db-password", params={"client_id": "scanner-a"})
        metrics = client.get("/metrics")
        health = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "name": "db-password",
        "value": "super-secret-password",
        "source": "in-memory-vault",
    }
    assert health.json()["status"] == "ok"
    assert '"dependency":"vault-backend","healthy":true' not in metrics.text
    assert (
        'security_platform_dependency_health{dependency="vault-backend",'
        'service="vault-service"} 1.0'
        in metrics.text
    )


def test_secret_access_reports_dependency_failure():
    app = create_app()
    app.state.settings.vault_dependency_failure = 1

    with TestClient(app) as client:
        response = client.get("/secrets/db-password", params={"client_id": "scanner-a"})
        health = client.get("/health")
        metrics = client.get("/metrics")

    assert response.status_code == 503
    assert response.json()["detail"] == "vault dependency unavailable"
    assert health.json()["status"] == "degraded"
    assert (
        'security_platform_dependency_health{dependency="vault-backend",'
        'service="vault-service"} 0.0'
        in metrics.text
    )
    assert (
        'security_platform_security_events_total{client_id="scanner-a",'
        'event_type="secret_access",reason="dependency_unavailable",'
        'service="vault-service"} 1.0'
        in metrics.text
    )


def test_secret_access_reports_missing_secret_as_security_event():
    app = create_app()

    with TestClient(app) as client:
        response = client.get("/secrets/missing-secret", params={"client_id": "client-z"})
        metrics = client.get("/metrics")

    assert response.status_code == 404
    assert response.json()["detail"] == "secret not found"
    assert (
        'security_platform_security_events_total{client_id="client-z",'
        'event_type="secret_access",reason="not_found",service="vault-service"} 1.0'
        in metrics.text
    )


def test_vault_simulation_endpoint_toggles_dependency_failure():
    app = create_app()

    with TestClient(app) as client:
        response = client.post("/simulate/dependency", json={"dependency_failure": 1})
        health = client.get("/health")

    assert response.status_code == 200
    assert response.json()["dependency_failure"] == 1
    assert health.json()["status"] == "degraded"
