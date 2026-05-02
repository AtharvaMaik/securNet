import time
import uuid
from collections import deque

from fastapi import HTTPException
from prometheus_client import Counter, Histogram
from pydantic import BaseModel

from shared.app import create_base_app
from shared.metrics import DEPENDENCY_HEALTH, MEMORY_PRESSURE, QUEUE_DEPTH, SECURITY_EVENTS

SCAN_JOB_DURATION = Histogram(
    "scan_job_duration_seconds",
    "Duration of simulated scan jobs in seconds",
    ["service", "status"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
)

SCAN_JOB_FAILURES = Counter(
    "scan_job_failures_total",
    "Count of simulated scan job failures",
    ["service", "reason"],
)


class ScanRequest(BaseModel):
    target: str
    should_fail: bool = False
    client_id: str = "scanner"


class BacklogSimulationRequest(BaseModel):
    multiplier: int
    jobs: int = 1


class MemoryPressureRequest(BaseModel):
    enabled: int


class ScanRuntime:
    def __init__(self, service_name: str, settings) -> None:
        self.service_name = service_name
        self.settings = settings
        self.pending_jobs: deque[dict] = deque()
        self.running_job_id: str | None = None
        self.completed = 0
        self.failed = 0

    def _sync_metrics(self, app) -> None:
        depth = len(self.pending_jobs)
        QUEUE_DEPTH.labels(service=self.service_name, queue_name="scan-jobs").set(depth)
        healthy = depth < 5
        app.state.dependencies["scan-worker"] = {
            "healthy": healthy,
            "status": "ok" if healthy else "backlogged",
            "queue_depth": depth,
        }
        DEPENDENCY_HEALTH.labels(
            service=self.service_name,
            dependency="scan-worker",
        ).set(1 if healthy else 0)

    def enqueue(self, app, request: ScanRequest) -> dict[str, str]:
        multiplier = max(1, self.settings.scan_backlog_spike_multiplier)
        job_id = str(uuid.uuid4())
        primary_job = {
            "job_id": job_id,
            "target": request.target,
            "should_fail": request.should_fail,
            "client_id": request.client_id,
            "synthetic": False,
        }
        self.pending_jobs.append(primary_job)
        for index in range(1, multiplier):
            self.pending_jobs.append(
                {
                    "job_id": f"{job_id}-backlog-{index}",
                    "target": request.target,
                    "should_fail": False,
                    "client_id": request.client_id,
                    "synthetic": True,
                }
            )
        self._sync_metrics(app)
        return {"job_id": job_id, "status": "queued"}

    def process_next(self, app=None) -> dict[str, str]:
        if not self.pending_jobs:
            raise HTTPException(status_code=409, detail="no jobs queued")

        job = self.pending_jobs.popleft()
        self.running_job_id = job["job_id"]
        started = time.perf_counter()
        time.sleep(0.01)

        if job["should_fail"]:
            self.failed += 1
            SCAN_JOB_FAILURES.labels(
                service=self.service_name,
                reason="policy_violation",
            ).inc()
            SECURITY_EVENTS.labels(
                service=self.service_name,
                event_type="scan_job",
                reason="policy_violation",
                client_id=job["client_id"],
            ).inc()
            status = "failed"
        else:
            self.completed += 1
            status = "completed"

        SCAN_JOB_DURATION.labels(
            service=self.service_name,
            status=status,
        ).observe(time.perf_counter() - started)
        self.running_job_id = None
        if app is not None:
            self._sync_metrics(app)
        return {
            "job_id": job["job_id"],
            "target": job["target"],
            "status": status,
        }

    def snapshot(self, app) -> dict:
        self._sync_metrics(app)
        return {
            "depth": len(self.pending_jobs),
            "running_job_id": self.running_job_id,
            "pending_job_ids": [job["job_id"] for job in self.pending_jobs],
            "completed": self.completed,
            "failed": self.failed,
        }


def create_app():
    app = create_base_app("scan-service", 8003)
    runtime = ScanRuntime("scan-service", app.state.settings)
    app.state.scan_runtime = runtime
    app.state.memory_ballast = []
    runtime._sync_metrics(app)

    @app.post("/scan", status_code=202)
    async def create_scan(request: ScanRequest):
        return runtime.enqueue(app, request)

    @app.get("/queue")
    async def get_queue():
        return runtime.snapshot(app)

    @app.post("/worker/process-next")
    async def process_next():
        return runtime.process_next(app)

    @app.post("/simulate/backlog")
    async def simulate_backlog(request: BacklogSimulationRequest):
        app.state.settings.scan_backlog_spike_multiplier = request.multiplier
        for index in range(request.jobs):
            runtime.enqueue(
                app,
                ScanRequest(
                    target=f"synthetic-{index}",
                    client_id="incident-simulator",
                    should_fail=False,
                ),
            )
        return {"status": "queued", "jobs": request.jobs, "multiplier": request.multiplier}

    @app.post("/simulate/memory-pressure")
    async def simulate_memory_pressure(request: MemoryPressureRequest):
        app.state.settings.memory_pressure_enabled = request.enabled
        MEMORY_PRESSURE.labels(service="scan-service").set(request.enabled)
        app.state.memory_ballast = [b"x" * 1024 * 1024 for _ in range(512 * request.enabled)]
        return {"status": "updated", "enabled": request.enabled}

    @app.post("/simulate/clear-queue")
    async def clear_queue():
        runtime.pending_jobs.clear()
        runtime.running_job_id = None
        runtime._sync_metrics(app)
        return {"status": "cleared"}

    return app


app = create_app()
