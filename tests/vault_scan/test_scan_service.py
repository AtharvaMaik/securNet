from fastapi.testclient import TestClient

from services.scan_service.app import create_app


def test_scan_queue_tracks_backlog_and_status():
    app = create_app()
    app.state.settings.scan_backlog_spike_multiplier = 3

    with TestClient(app) as client:
        response = client.post("/scan", json={"target": "artifact-a"})
        queue = client.get("/queue")
        metrics = client.get("/metrics")

    body = response.json()
    assert response.status_code == 202
    assert body["status"] == "queued"
    assert queue.json()["depth"] == 3
    assert queue.json()["pending_job_ids"] == [
        body["job_id"],
        f'{body["job_id"]}-backlog-1',
        f'{body["job_id"]}-backlog-2',
    ]
    assert (
        'security_platform_queue_depth{queue_name="scan-jobs",service="scan-service"} 3.0'
        in metrics.text
    )


def test_scan_worker_processes_job_and_records_duration_metric():
    app = create_app()

    with TestClient(app) as client:
        response = client.post("/scan", json={"target": "artifact-b"})
        runtime = client.app.state.scan_runtime
        processed = runtime.process_next()
        queue = client.get("/queue")
        metrics = client.get("/metrics")

    assert response.status_code == 202
    assert processed["status"] == "completed"
    assert processed["target"] == "artifact-b"
    assert queue.json()["depth"] == 0
    assert queue.json()["completed"] == 1
    assert "scan_job_duration_seconds_bucket" in metrics.text


def test_scan_worker_records_failures_in_metrics():
    app = create_app()

    with TestClient(app) as client:
        response = client.post("/scan", json={"target": "artifact-c", "should_fail": True})
        runtime = client.app.state.scan_runtime
        processed = runtime.process_next()
        queue = client.get("/queue")
        metrics = client.get("/metrics")

    assert response.status_code == 202
    assert processed["status"] == "failed"
    assert queue.json()["failed"] == 1
    assert 'scan_job_failures_total{reason="policy_violation",service="scan-service"} 1.0' in (
        metrics.text
    )


def test_scan_simulation_endpoints_manage_backlog_and_memory_pressure():
    app = create_app()

    with TestClient(app) as client:
        backlog = client.post("/simulate/backlog", json={"multiplier": 2, "jobs": 2})
        queue = client.get("/queue")
        memory = client.post("/simulate/memory-pressure", json={"enabled": 1})
        cleared = client.post("/simulate/clear-queue")
        final_queue = client.get("/queue")

    assert backlog.status_code == 200
    assert queue.json()["depth"] == 4
    assert memory.status_code == 200
    assert cleared.status_code == 200
    assert final_queue.json()["depth"] == 0
