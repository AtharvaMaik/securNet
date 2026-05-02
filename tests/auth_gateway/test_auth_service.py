import pytest
from fastapi.testclient import TestClient

from shared.config import get_settings


@pytest.fixture(autouse=True)
def clear_settings_cache(monkeypatch):
    for key, value in {
        "DEFAULT_LATENCY_MS": "0",
        "LATENCY_JITTER_MS": "0",
        "ERROR_RATE": "0",
        "FAILED_LOGIN_SPIKE_MULTIPLIER": "2",
        "TOKEN_FAILURE_SPIKE_MULTIPLIER": "3",
    }.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def create_client():
    from services.auth_service.app import create_app

    return TestClient(create_app())


def test_login_returns_token_for_valid_credentials():
    with create_client() as client:
        response = client.post(
            "/login",
            json={"username": "analyst", "password": "correct-password", "client_id": "soc-1"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["client_id"] == "soc-1"
    assert body["access_token"].startswith("token-analyst-soc-1")


def test_login_rejects_invalid_credentials_and_emits_security_metric():
    with create_client() as client:
        response = client.post(
            "/login",
            json={"username": "analyst", "password": "wrong", "client_id": "soc-1"},
        )
        metrics = client.get("/metrics")

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid_credentials"
    assert 'event_type="failed_login"' in metrics.text
    assert 'client_id="soc-1"' in metrics.text
    assert " 2.0" in metrics.text


def test_validate_rejects_malformed_authorization_header():
    with create_client() as client:
        response = client.post("/validate", headers={"authorization": "Token bad-format"})
        metrics = client.get("/metrics")

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid_authorization_header"
    assert 'event_type="invalid_auth_header"' in metrics.text


def test_validate_accepts_issued_token():
    with create_client() as client:
        login = client.post(
            "/login",
            json={"username": "analyst", "password": "correct-password", "client_id": "soc-1"},
        )
        token = login.json()["access_token"]
        response = client.post("/validate", headers={"authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json() == {"active": True, "client_id": "soc-1", "subject": "analyst"}


def test_validate_can_inject_server_error_for_fault_simulations():
    with create_client() as client:
        response = client.post("/validate", headers={"x-fault-injection": "auth-5xx"})

    assert response.status_code == 503
    assert response.json()["detail"] == "synthetic_auth_failure"


def test_simulation_endpoint_updates_auth_runtime_settings():
    with create_client() as client:
        response = client.post(
            "/simulate",
            json={
                "latency_ms": 120,
                "token_failure_multiplier": 5,
                "failed_login_multiplier": 4,
                "memory_pressure_enabled": 1,
            },
        )
        health = client.get("/health")

    assert response.status_code == 200
    assert response.json()["settings"]["latency_ms"] == 120
    assert client.app.state.settings.token_failure_spike_multiplier == 5
    assert health.status_code == 200
