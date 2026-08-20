"""FastAPI controller serving the React UI without importing model libraries."""

from __future__ import annotations

import json
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from .config import AppConfig
from .jobs import JobManager
from .schemas import GenerationRequest, JobRecord
from .worker_supervisor import WorkerSupervisor


def create_app(
    config: AppConfig | None = None,
    worker: WorkerSupervisor | None = None,
) -> FastAPI:
    """Create an injectable lightweight controller for desktop use and tests."""

    config = config or AppConfig.from_environment()
    config.ensure_directories()
    worker = worker or WorkerSupervisor(config)
    jobs = JobManager(config, worker)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        jobs.shutdown()
        worker.shutdown()

    app = FastAPI(title="Fidget", version="1.0.0", lifespan=lifespan)
    app.state.config = config
    app.state.worker = worker
    app.state.jobs = jobs
    app.state.started_at = time.time()

    app.mount("/media", StaticFiles(directory=config.outputs_dir), name="media")

    @app.get("/api/health")
    def health() -> dict[str, object]:
        return {
            "ok": True,
            "app": "Fidget",
            "controller_pid": os.getpid(),
            "uptime_seconds": round(time.time() - app.state.started_at, 3),
        }

    @app.get("/api/model")
    def model_status() -> dict[str, object]:
        return worker.status()

    @app.post("/api/model/start")
    def model_start() -> dict[str, object]:
        return worker.start()

    @app.post("/api/model/stop")
    def model_stop() -> dict[str, object]:
        return worker.stop()

    @app.post("/api/generate", response_model=list[JobRecord], status_code=202)
    def generate(request: GenerationRequest) -> list[JobRecord]:
        if request.duration > config.max_duration_seconds:
            raise HTTPException(
                status_code=422,
                detail=f"This safety profile allows at most {config.max_duration_seconds} seconds.",
            )
        if request.variations > config.max_variations:
            raise HTTPException(
                status_code=422,
                detail=f"This safety profile allows at most {config.max_variations} takes per request.",
            )
        return jobs.submit(request)

    @app.get("/api/jobs", response_model=list[JobRecord])
    def list_jobs() -> list[JobRecord]:
        return jobs.list()

    @app.get("/api/jobs/{job_id}", response_model=JobRecord)
    def get_job(job_id: str) -> JobRecord:
        job = jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return job

    @app.post("/api/jobs/{job_id}/cancel", response_model=JobRecord)
    def cancel_job(job_id: str) -> JobRecord:
        job = jobs.cancel(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return job

    @app.post("/api/jobs/{job_id}/favorite", response_model=JobRecord)
    def set_favorite(job_id: str, favorite: bool = True) -> JobRecord:
        job = jobs.set_favorite(job_id, favorite)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return job

    @app.delete("/api/jobs/{job_id}", status_code=204)
    def delete_job(job_id: str) -> Response:
        try:
            removed = jobs.delete(job_id)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if not removed:
            raise HTTPException(status_code=404, detail="Job not found")
        return Response(status_code=204)

    @app.post("/api/jobs/{job_id}/retry", response_model=JobRecord, status_code=202)
    def retry_job(job_id: str) -> JobRecord:
        job = jobs.retry(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return job

    @app.get("/api/verification/latest")
    def latest_verification() -> dict[str, object]:
        try:
            value = json.loads(config.latest_verification_file.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="No successful generation has been verified yet") from exc
        except (OSError, ValueError, TypeError) as exc:
            raise HTTPException(status_code=500, detail="Verification record is unreadable") from exc
        return value

    @app.get("/{requested_path:path}", include_in_schema=False)
    def frontend(requested_path: str):
        dist = config.frontend_dist.resolve()
        requested = (dist / requested_path).resolve()
        if requested_path and requested.is_file() and _is_within(requested, dist):
            return FileResponse(requested)
        index = dist / "index.html"
        if index.exists():
            return FileResponse(index)
        return HTMLResponse(
            "<h1>Fidget frontend is not built</h1><p>Run setup.ps1 from the repository root.</p>",
            status_code=503,
        )

    return app


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
