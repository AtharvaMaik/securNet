from fastapi.testclient import TestClient

from shared.app import create_base_app


def test_base_app_exposes_health_and_metrics():
    app = create_base_app("test-service", 9999)
    with TestClient(app) as client:
        health = client.get("/health")
        metrics = client.get("/metrics")

        assert health.status_code == 200
        assert health.json()["service"] == "test-service"
        assert metrics.status_code == 200
        assert "security_platform_requests_total" in metrics.text
