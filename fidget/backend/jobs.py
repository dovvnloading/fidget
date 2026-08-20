"""Durable single-worker queue with verified, atomic audio artifacts."""

from __future__ import annotations

import json
import os
import secrets
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .audio_validation import validate_wav
from .config import AppConfig
from .schemas import GenerationRequest, JobRecord
from .worker_supervisor import WorkerCancelledError, WorkerSupervisor

SEED_MAX = 2_147_483_647


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _public_error(value: str | None) -> str | None:
    """Keep old worker traces out of the frequently-polled public job list."""

    if not value:
        return value
    lowered = value.lower()
    if "out of memory" in lowered:
        return "ACE-Step was stopped safely because GPU memory was exhausted."
    if "connection was forcibly closed" in lowered or "winerror 10054" in lowered:
        return "The isolated ACE-Step worker crashed; the app remained online."
    if "timed out" in lowered:
        return "The isolated ACE-Step worker timed out and was terminated safely."
    first_line = next((line.strip() for line in value.splitlines() if line.strip()), "Generation failed")
    return first_line[:400]


class JobManager:
    """Serialize GPU jobs and persist every terminal outcome."""

    def __init__(self, config: AppConfig, worker: WorkerSupervisor) -> None:
        self.config = config
        self.worker = worker
        self._lock = threading.RLock()
        # Deliberately one worker: the GPU fits exactly one generation, so the
        # executor *is* the queue. Batches rely on this to serialise.
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="fidget-generation")
        self._jobs: dict[str, JobRecord] = {}
        self._last_finished_at: float | None = None
        self._load()

    def _variation_seeds(self, request: GenerationRequest) -> list[int]:
        """One distinct seed per take.

        An explicit seed walks upward from the user's value so a batch stays
        reproducible; otherwise each take draws its own.
        """
        count = max(1, request.variations)
        if request.seed is not None:
            return [(request.seed + offset) % (SEED_MAX + 1) for offset in range(count)]
        seeds: list[int] = []
        while len(seeds) < count:
            candidate = secrets.randbelow(SEED_MAX + 1)
            if candidate not in seeds:
                seeds.append(candidate)
        return seeds

    def submit(self, request: GenerationRequest) -> list[JobRecord]:
        """Queue every take for this request. They run strictly one at a time."""
        seeds = self._variation_seeds(request)
        batch_id = uuid.uuid4().hex[:12]
        size = len(seeds)
        fields = request.model_dump(exclude={"variations", "seed"})

        created: list[JobRecord] = []
        for index, seed in enumerate(seeds, start=1):
            job = JobRecord(
                id=uuid.uuid4().hex[:12],
                status="queued",
                seed=seed,
                batch_id=batch_id,
                batch_index=index,
                batch_size=size,
                message="Queued" if index == 1 else f"Queued · take {index} of {size}",
                **fields,
            )
            with self._lock:
                self._jobs[job.id] = job
                self._save()
            # Each take carries its own resolved seed and never re-fans out.
            take = request.model_copy(update={"seed": seed, "variations": 1})
            self._executor.submit(self._run, job.id, take)
            created.append(job.model_copy(deep=True))
        return created

    def retry(self, job_id: str) -> JobRecord | None:
        previous = self.get(job_id)
        if not previous:
            return None
        request = GenerationRequest(
            prompt=previous.prompt,
            lyrics=previous.lyrics,
            duration=min(max(previous.duration, 10), self.config.max_duration_seconds),
            bpm=previous.bpm,
            key_scale=previous.key_scale,
            time_signature=previous.time_signature,
            instrumental=previous.instrumental,
            seed=previous.seed,
            variations=1,
        )
        return self.submit(request)[0]

    def cancel(self, job_id: str) -> JobRecord | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            if job.status not in {"queued", "starting", "running"}:
                return job.model_copy(deep=True)
            self._jobs[job_id] = job.model_copy(
                update={
                    "status": "cancelled",
                    "message": "Cancelled",
                    "completed_at": _utc_now(),
                }
            )
            self._save()
        self.worker.cancel_current(job_id)
        return self.get(job_id)

    def set_favorite(self, job_id: str, favorite: bool) -> JobRecord | None:
        with self._lock:
            if job_id not in self._jobs:
                return None
            self._update(job_id, favorite=favorite)
        return self.get(job_id)

    def delete(self, job_id: str) -> bool:
        """Forget a finished take and remove everything it wrote to disk.

        Refuses while the take is still live: its worker owns those files, and
        the queue would keep writing to paths that no longer have a record.
        Cancel it first.
        """
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return False
            if job.status in {"queued", "starting", "running"}:
                raise ValueError("Cancel this take before deleting it")
            del self._jobs[job_id]
            self._save()

        for path in (
            self.config.outputs_dir / f"{job_id}.wav",
            self.config.verification_dir / f"{job_id}.json",
            self.config.requests_dir / f"{job_id}.json",
            self.config.results_dir / f"{job_id}.json",
            self.config.logs_dir / f"ace-{job_id}.log",
        ):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                # The record is already gone; a locked leftover file is not
                # worth failing the request over.
                pass
        return True

    def list(self) -> list[JobRecord]:
        with self._lock:
            ordered = sorted(self._jobs.values(), key=lambda item: item.created_at, reverse=True)
            return [item.model_copy(deep=True) for item in ordered]

    def get(self, job_id: str) -> JobRecord | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return job.model_copy(deep=True) if job else None

    def shutdown(self) -> None:
        self.worker.cancel_current()
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _is_cancelled(self, job_id: str) -> bool:
        job = self.get(job_id)
        return job is None or job.status == "cancelled"

    def _sleep_unless_cancelled(self, seconds: float, job_id: str) -> None:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if self._is_cancelled(job_id):
                raise WorkerCancelledError("Cancelled while the GPU was settling")
            time.sleep(0.25)

    def _settle_before_run(self, job_id: str) -> None:
        """Give the previous take's GPU memory time to come back.

        A worker's VRAM is released when its process exits, but not
        instantaneously, so a back-to-back take can read stale usage and trip
        the launch gate. Pause for a fixed cooldown, then wait -- bounded --
        for the driver to actually hand the memory back.
        """
        if self._last_finished_at is not None:
            remaining = self.config.cooldown_between_jobs_seconds - (
                time.monotonic() - self._last_finished_at
            )
            if remaining > 0:
                self._update(job_id, status="starting", progress=1, message="Letting the GPU settle")
                self._sleep_unless_cancelled(remaining, job_id)

        self.worker.await_resources(
            timeout=self.config.resource_settle_timeout_seconds,
            on_wait=lambda message: self._update(
                job_id, status="starting", progress=1, message=message
            ),
            should_abort=lambda: self._is_cancelled(job_id),
        )

    def _run(self, job_id: str, request: GenerationRequest) -> None:
        started_at = time.time()
        events: list[dict[str, Any]] = []
        launched = False
        try:
            current = self.get(job_id)
            if not current or current.status == "cancelled":
                return
            self._update(job_id, status="starting", progress=1, message="Running safety checks")
            self._settle_before_run(job_id)

            def report(progress: float, message: str, worker_pid: int | None) -> None:
                events.append(
                    {
                        "time": _utc_now(),
                        "progress": round(progress, 2),
                        "message": message,
                        "worker_pid": worker_pid,
                    }
                )
                self._update(
                    job_id,
                    status="running",
                    progress=min(max(progress, 1), 99),
                    message=message,
                    worker_pid=worker_pid,
                )

            launched = True
            worker_result = self.worker.run_generation(job_id, request, report)
            output_path = Path(str(worker_result["output_path"]))
            self._update(job_id, progress=99, message="Independently validating audio")
            audio = validate_wav(output_path, expected_seconds=request.duration)
            if worker_result.get("sha256") != audio["sha256"]:
                raise RuntimeError("Audio checksum changed between worker and controller validation")

            elapsed = round(time.time() - started_at, 3)
            verification = {
                "schema_version": 1,
                "success": True,
                "verified_at": _utc_now(),
                "job_id": job_id,
                "controller_pid": os.getpid(),
                "model": {
                    "id": self.config.model_id,
                    "path": str(self.config.model_dir),
                "lm_id": self.config.lm_model_id,
                "license": "MIT code / model-specific open weights",
                },
                "request": request.model_dump(mode="json"),
                "worker": worker_result,
                "audio": audio,
                "events": events,
                "time_to_verified_audio_seconds": elapsed,
            }
            self._write_verification(job_id, verification, latest=True)
            metrics = {
                "elapsed_seconds": elapsed,
                "peak_worker_rss_mb": worker_result.get("peak_worker_rss_mb"),
                "peak_gpu_used_mb": worker_result.get("peak_gpu_used_mb"),
                "minimum_available_ram_gb": worker_result.get("minimum_available_ram_gb"),
                "sha256": audio["sha256"],
                "audio_duration_seconds": audio["duration_seconds"],
                "audio_rms": audio["rms"],
            }
            self._update(
                job_id,
                status="succeeded",
                progress=100,
                message="Verified audio ready",
                completed_at=_utc_now(),
                result_url=f"/media/{output_path.name}",
                error=None,
                metrics=metrics,
            )
        except WorkerCancelledError:
            self._update(
                job_id,
                status="cancelled",
                message="Cancelled",
                completed_at=_utc_now(),
                error=None,
            )
        except Exception as exc:  # Background jobs must always become terminal.
            current = self.get(job_id)
            if current and current.status == "cancelled":
                return
            verification = {
                "schema_version": 1,
                "success": False,
                "verified_at": _utc_now(),
                "job_id": job_id,
                "controller_pid": os.getpid(),
                "request": request.model_dump(mode="json"),
                "error": str(exc),
                "events": events,
                "elapsed_seconds": round(time.time() - started_at, 3),
            }
            self._write_verification(job_id, verification, latest=False)
            self._update(
                job_id,
                status="failed",
                message="Generation failed safely; the app stayed online",
                completed_at=_utc_now(),
                error=_public_error(str(exc)),
            )
        finally:
            # Only a take that actually reached the GPU leaves memory to
            # reclaim, so only that one starts the next take's cooldown.
            if launched:
                self._last_finished_at = time.monotonic()

    def _update(self, job_id: str, **changes: object) -> None:
        with self._lock:
            job = self._jobs[job_id]
            updated = job.model_copy(update=changes)
            self._jobs[job_id] = JobRecord.model_validate(updated.model_dump())
            self._save()

    def _load(self) -> None:
        self.config.ensure_directories()
        path = self.config.jobs_file
        if not path.exists():
            return
        try:
            records = json.loads(path.read_text(encoding="utf-8"))
            for raw in records:
                job = JobRecord.model_validate(raw)
                if job.error:
                    job = job.model_copy(update={"error": _public_error(job.error)})
                if job.status in {"queued", "starting", "running"}:
                    job = job.model_copy(
                        update={
                            "status": "failed",
                            "message": "Interrupted safely by a previous app session",
                            "completed_at": _utc_now(),
                            "error": "The controller closed before this job completed.",
                        }
                    )
                self._jobs[job.id] = job
        except (OSError, ValueError, TypeError):
            backup = path.with_suffix(".invalid.json")
            try:
                path.replace(backup)
            except OSError:
                pass

    def _save(self) -> None:
        path = self.config.jobs_file
        temporary = path.with_suffix(".tmp")
        payload = [job.model_dump(mode="json") for job in self._jobs.values()]
        temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temporary.replace(path)

    def _write_verification(self, job_id: str, value: dict[str, Any], latest: bool) -> None:
        self._write_json(self.config.verification_dir / f"{job_id}.json", value)
        if latest:
            self._write_json(self.config.latest_verification_file, value)

    @staticmethod
    def _write_json(path: Path, value: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(value, indent=2), encoding="utf-8")
        temporary.replace(path)
