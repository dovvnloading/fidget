from __future__ import annotations

import math
import struct
import time
import wave
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from fidget.backend.app import create_app
from fidget.backend.audio_validation import InvalidAudioError, validate_wav
from fidget.backend.config import AppConfig


class FakeWorker:
    def __init__(self, config: AppConfig, fail: bool = False) -> None:
        self.config = config
        self.fail = fail
        self.stopped = False
        self.await_calls = 0
        self.concurrent = 0
        self.max_concurrent = 0

    def await_resources(self, timeout, on_wait=None, should_abort=None) -> dict[str, object]:
        self.await_calls += 1
        return {"available_ram_gb": 16.0, "vram_free_mb": 8192}

    def status(self) -> dict[str, object]:
        return {
            "state": "ready",
            "status": "ready",
            "ready": True,
            "installed": True,
            "model_name": "Fake ACE-Step",
            "vram_percent": 0,
            "max_duration_seconds": self.config.max_duration_seconds,
        }

    def start(self) -> dict[str, object]:
        return self.status()

    def stop(self) -> dict[str, object]:
        self.stopped = True
        return self.status()

    def cancel_current(self, job_id: str | None = None) -> bool:
        self.stopped = True
        return True

    def shutdown(self) -> None:
        self.stopped = True

    def run_generation(self, job_id, request, progress):
        self.concurrent += 1
        self.max_concurrent = max(self.max_concurrent, self.concurrent)
        try:
            progress(10, "Worker isolated", 1234)
            if self.fail:
                raise RuntimeError("simulated native worker crash")
            output = self.config.outputs_dir / f"{job_id}.wav"
            _write_tone(output, request.duration)
            progress(95, "WAV written", 1234)
            metadata = validate_wav(output, request.duration)
        finally:
            self.concurrent -= 1
        return {
            "ok": True,
            "output_path": str(output),
            "sha256": metadata["sha256"],
            "worker_pid": 1234,
            "exit_code": 0,
            "peak_worker_rss_mb": 256,
            "peak_gpu_used_mb": 1024,
            "minimum_available_ram_gb": 8.0,
        }


def _write_tone(path: Path, seconds: int, sample_rate: int = 32_000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    samples = [
        int(math.sin(index * 2 * math.pi * 440 / sample_rate) * 12_000)
        for index in range(seconds * sample_rate)
    ]
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(struct.pack(f"<{len(samples)}h", *samples))


def make_config(root: Path, **overrides: object) -> AppConfig:
    data = root / "data"
    frontend = root / "frontend" / "dist"
    frontend.mkdir(parents=True)
    frontend.joinpath("index.html").write_text("<main>Fidget</main>", encoding="utf-8")
    return AppConfig(
        project_root=root,
        frontend_dist=frontend,
        data_root=data,
        model_dir=data / "ACE-Step-1.5" / "checkpoints",
        worker_runtime=data / "ACE-Step-1.5" / ".venv",
        outputs_dir=data / "outputs",
        state_dir=data / "state",
        logs_dir=data / "logs",
        **overrides,
    )


def wait_for_terminal(client: TestClient, job_id: str) -> dict[str, object]:
    deadline = time.monotonic() + 4
    job: dict[str, object] = {}
    while time.monotonic() < deadline:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in {"succeeded", "failed", "cancelled"}:
            return job
        time.sleep(0.02)
    return job


def test_health_frontend_and_cached_model_status(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    app = create_app(config, FakeWorker(config))
    with TestClient(app) as client:
        assert client.get("/api/health").json()["ok"] is True
        assert client.get("/api/model").json()["model_name"] == "Fake ACE-Step"
        assert "Fidget" in client.get("/").text


def test_generation_reaches_verified_local_audio(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    app = create_app(config, FakeWorker(config))
    with TestClient(app) as client:
        response = client.post(
            "/api/generate",
            json={
                "prompt": "warm analog synthwave",
                "lyrics": "",
                "duration": 10,
                "instrumental": True,
                "seed": 123,
            },
        )
        assert response.status_code == 202
        job = wait_for_terminal(client, response.json()[0]["id"])
        assert job["status"] == "succeeded"
        media = client.get(str(job["result_url"]))
        assert media.status_code == 200
        assert media.content[:4] == b"RIFF"
        evidence = client.get("/api/verification/latest").json()
        assert evidence["success"] is True
        assert evidence["audio"]["sha256"] == job["metrics"]["sha256"]
        assert evidence["audio"]["rms"] > 0


def test_worker_crash_does_not_take_controller_offline(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    app = create_app(config, FakeWorker(config, fail=True))
    with TestClient(app) as client:
        response = client.post("/api/generate", json={"prompt": "crash test music", "duration": 10})
        job = wait_for_terminal(client, response.json()[0]["id"])
        assert job["status"] == "failed"
        assert "simulated native worker crash" in str(job["error"])
        assert client.get("/api/health").status_code == 200
        assert client.get("/").status_code == 200


def test_invalid_generation_is_rejected(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    app = create_app(config, FakeWorker(config))
    over = config.max_duration_seconds + 1
    with TestClient(app) as client:
        assert client.post("/api/generate", json={"prompt": "x", "duration": 5}).status_code == 422
        assert client.post("/api/generate", json={"prompt": "valid prompt", "duration": over}).status_code == 422
        # Beyond ACE-Step's own DURATION_MAX, refused by the schema envelope.
        assert client.post("/api/generate", json={"prompt": "valid prompt", "duration": 601}).status_code == 422


def test_configured_ceiling_above_two_minutes_is_honoured(tmp_path: Path) -> None:
    """A duration over 120s must reach the worker rather than being refused.

    The request schema used to hard-cap duration at 120, so raising
    FIDGET_MAX_DURATION had no effect: validation rejected the request before
    the configurable ceiling was ever consulted.
    """
    config = make_config(tmp_path, max_duration_seconds=480)
    app = create_app(config, FakeWorker(config))
    with TestClient(app) as client:
        response = client.post("/api/generate", json={"prompt": "a long ambient piece", "duration": 240})
        assert response.status_code == 202
        assert response.json()[0]["duration"] == 240


def test_status_publishes_the_duration_ceiling(tmp_path: Path) -> None:
    """The composer's slider bound comes from the controller, not a constant."""
    config = make_config(tmp_path, max_duration_seconds=300)
    app = create_app(config, FakeWorker(config))
    with TestClient(app) as client:
        assert client.get("/api/model").json()["max_duration_seconds"] == 300


def test_silent_audio_is_not_accepted(tmp_path: Path) -> None:
    silent = tmp_path / "silent.wav"
    silent.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(silent), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(32_000)
        handle.writeframes(b"\0\0" * 32_000 * 5)
    with pytest.raises(InvalidAudioError, match="silent"):
        validate_wav(silent, 5)


def test_batch_creates_one_take_per_variation_with_distinct_seeds(tmp_path: Path) -> None:
    config = make_config(tmp_path, cooldown_between_jobs_seconds=0.0)
    app = create_app(config, FakeWorker(config))
    with TestClient(app) as client:
        response = client.post(
            "/api/generate",
            json={"prompt": "warm analog synthwave", "duration": 10, "variations": 4},
        )
        assert response.status_code == 202
        created = response.json()
        assert len(created) == 4

        # One batch, numbered for display, every take with its own seed.
        assert {job["batch_id"] for job in created} == {created[0]["batch_id"]}
        assert [job["batch_index"] for job in created] == [1, 2, 3, 4]
        assert all(job["batch_size"] == 4 for job in created)
        seeds = [job["seed"] for job in created]
        assert len(set(seeds)) == 4
        assert all(isinstance(seed, int) for seed in seeds)

        for job in created:
            assert wait_for_terminal(client, job["id"])["status"] == "succeeded"


def test_batch_never_runs_two_generations_at_once(tmp_path: Path) -> None:
    """The GPU fits exactly one generation; a batch must not overlap takes."""
    config = make_config(tmp_path, cooldown_between_jobs_seconds=0.0)
    worker = FakeWorker(config)
    app = create_app(config, worker)
    with TestClient(app) as client:
        created = client.post(
            "/api/generate",
            json={"prompt": "layered ambient drift", "duration": 10, "variations": 4},
        ).json()
        for job in created:
            wait_for_terminal(client, job["id"])
    assert worker.max_concurrent == 1
    # Every take waits for memory to come back before it launches.
    assert worker.await_calls == 4


def test_explicit_seed_makes_a_batch_reproducible(tmp_path: Path) -> None:
    config = make_config(tmp_path, cooldown_between_jobs_seconds=0.0)
    app = create_app(config, FakeWorker(config))
    with TestClient(app) as client:
        created = client.post(
            "/api/generate",
            json={"prompt": "brushed jazz trio", "duration": 10, "variations": 3, "seed": 1000},
        ).json()
        assert [job["seed"] for job in created] == [1000, 1001, 1002]


def test_single_request_is_still_a_batch_of_one(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    app = create_app(config, FakeWorker(config))
    with TestClient(app) as client:
        created = client.post("/api/generate", json={"prompt": "one take only", "duration": 10}).json()
        assert len(created) == 1
        assert created[0]["batch_size"] == 1
        assert created[0]["batch_index"] == 1
        # Resolved up front, so the take can be reproduced later.
        assert isinstance(created[0]["seed"], int)


def test_variations_beyond_the_profile_are_rejected(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    app = create_app(config, FakeWorker(config))
    with TestClient(app) as client:
        response = client.post(
            "/api/generate",
            json={"prompt": "too many takes", "duration": 10, "variations": 5},
        )
        assert response.status_code == 422


def test_takes_are_paced_by_a_cooldown_between_runs(tmp_path: Path) -> None:
    """A finished worker's VRAM is not reclaimed instantly, so takes are paced.

    The first take starts immediately; each later one waits out the cooldown.
    """
    config = make_config(tmp_path, cooldown_between_jobs_seconds=0.4)
    app = create_app(config, FakeWorker(config))
    with TestClient(app) as client:
        started = time.monotonic()
        created = client.post(
            "/api/generate",
            json={"prompt": "paced takes", "duration": 10, "variations": 3},
        ).json()
        for job in created:
            assert wait_for_terminal(client, job["id"])["status"] == "succeeded"
        elapsed = time.monotonic() - started
    # Two gaps between three takes; no cooldown before the first.
    assert elapsed >= 0.8


def test_cancelling_a_queued_take_leaves_the_rest_of_the_batch_running(tmp_path: Path) -> None:
    config = make_config(tmp_path, cooldown_between_jobs_seconds=0.0)
    app = create_app(config, FakeWorker(config))
    with TestClient(app) as client:
        created = client.post(
            "/api/generate",
            json={"prompt": "cancel the middle take", "duration": 10, "variations": 3},
        ).json()
        assert client.post(f"/api/jobs/{created[2]['id']}/cancel").status_code == 200

        assert wait_for_terminal(client, created[0]["id"])["status"] == "succeeded"
        assert wait_for_terminal(client, created[1]["id"])["status"] == "succeeded"
        assert wait_for_terminal(client, created[2]["id"])["status"] == "cancelled"


def test_a_take_blocked_on_memory_waits_instead_of_failing(tmp_path: Path) -> None:
    """Transient memory pressure must not kill a queued take."""
    from fidget.backend.worker_supervisor import WorkerProcessError, WorkerResourceError

    config = make_config(tmp_path, cooldown_between_jobs_seconds=0.0)

    class BusyThenFreeWorker(FakeWorker):
        def await_resources(self, timeout, on_wait=None, should_abort=None):
            self.await_calls += 1
            if self.await_calls == 1 and on_wait:
                on_wait("Waiting for the GPU to release memory")
            return {"available_ram_gb": 16.0, "vram_free_mb": 8192}

    worker = BusyThenFreeWorker(config)
    app = create_app(config, worker)
    with TestClient(app) as client:
        created = client.post("/api/generate", json={"prompt": "waits for memory", "duration": 10}).json()
        assert wait_for_terminal(client, created[0]["id"])["status"] == "succeeded"

    # Memory pressure is a retryable subclass, not a hard worker failure.
    assert issubclass(WorkerResourceError, WorkerProcessError)


def test_favourite_and_delete_a_take(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    app = create_app(config, FakeWorker(config))
    with TestClient(app) as client:
        created = client.post("/api/generate", json={"prompt": "keep or cull", "duration": 10}).json()
        job_id = created[0]["id"]
        assert wait_for_terminal(client, job_id)["status"] == "succeeded"
        assert client.get(f"/api/jobs/{job_id}").json()["favorite"] is False

        assert client.post(f"/api/jobs/{job_id}/favorite?favorite=true").json()["favorite"] is True
        assert client.post(f"/api/jobs/{job_id}/favorite?favorite=false").json()["favorite"] is False

        audio = config.outputs_dir / f"{job_id}.wav"
        assert audio.exists()
        assert client.delete(f"/api/jobs/{job_id}").status_code == 204
        assert client.get(f"/api/jobs/{job_id}").status_code == 404
        # The take's audio goes with it rather than orphaning a file on disk.
        assert not audio.exists()
        assert client.delete(f"/api/jobs/{job_id}").status_code == 404


def test_a_live_take_cannot_be_deleted(tmp_path: Path) -> None:
    """Its worker still owns those paths; the take must be cancelled first."""
    config = make_config(tmp_path, cooldown_between_jobs_seconds=30.0)
    app = create_app(config, FakeWorker(config))
    with TestClient(app) as client:
        created = client.post(
            "/api/generate",
            json={"prompt": "still running", "duration": 10, "variations": 2},
        ).json()
        # The second take sits queued behind the cooldown.
        queued = created[1]["id"]
        assert client.delete(f"/api/jobs/{queued}").status_code == 409
        assert client.post(f"/api/jobs/{queued}/cancel").status_code == 200
        assert client.delete(f"/api/jobs/{queued}").status_code == 204


def test_favourite_survives_a_controller_restart(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    app = create_app(config, FakeWorker(config))
    with TestClient(app) as client:
        job_id = client.post("/api/generate", json={"prompt": "persisted pick", "duration": 10}).json()[0]["id"]
        wait_for_terminal(client, job_id)
        client.post(f"/api/jobs/{job_id}/favorite?favorite=true")

    # A fresh controller reads the same jobs file.
    restarted = create_app(config, FakeWorker(config))
    with TestClient(restarted) as client:
        assert client.get(f"/api/jobs/{job_id}").json()["favorite"] is True
