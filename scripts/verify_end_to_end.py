"""Run and persist Fidget's real controller-to-audio acceptance check."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import time
import wave
from array import array
from pathlib import Path
from urllib.parse import urljoin

import httpx


TERMINAL = {"succeeded", "failed", "cancelled"}


def percentile(values: list[float], percent: float) -> float:
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * percent) - 1)
    return ordered[index]


def inspect_audio(path: Path) -> dict[str, object]:
    with wave.open(str(path), "rb") as handle:
        sample_rate = handle.getframerate()
        channels = handle.getnchannels()
        frames = handle.getnframes()
        raw = handle.readframes(frames)
    samples = array("h")
    samples.frombytes(raw)
    rms = math.sqrt(sum(value * value for value in samples) / len(samples)) / 32768.0
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "path": str(path.resolve()),
        "sha256": digest,
        "sample_rate": sample_rate,
        "channels": channels,
        "frames": frames,
        "duration_seconds": round(frames / sample_rate, 3),
        "rms": round(rms, 6),
        "size_bytes": path.stat().st_size,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    parser.add_argument("--duration", type=int, default=10)
    parser.add_argument("--seed", type=int, default=20260818)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(os.getenv("FIDGET_DATA_ROOT", "D:/AI/fidget"))
        / "state"
        / "verification"
        / "latest-acceptance.json",
    )
    args = parser.parse_args()
    base = args.base_url.rstrip("/") + "/"
    client = httpx.Client(timeout=httpx.Timeout(10.0, read=20.0))
    initial_health = client.get(urljoin(base, "api/health"))
    initial_health.raise_for_status()
    request = {
        "prompt": "warm analog ambient synth chords, gentle tape texture, calm cinematic pulse",
        "lyrics": "soft sunrise over a quiet city",
        "duration": args.duration,
        "bpm": 82,
        "key_scale": "C Major",
        "time_signature": "4/4",
        "instrumental": True,
        "seed": args.seed,
    }
    submitted_at = time.time()
    response = client.post(urljoin(base, "api/generate"), json=request)
    response.raise_for_status()
    job_id = response.json()["id"]
    latencies: list[float] = []
    health_failures: list[str] = []
    controller_pids: set[int] = set()
    statuses: list[dict[str, object]] = []
    deadline = time.monotonic() + 900
    job: dict[str, object] = {}

    while time.monotonic() < deadline:
        probe_started = time.perf_counter()
        try:
            health = client.get(urljoin(base, "api/health"))
            latency = (time.perf_counter() - probe_started) * 1000
            latencies.append(latency)
            health.raise_for_status()
            body = health.json()
            if not body.get("ok"):
                health_failures.append("health payload was not ok")
            if body.get("controller_pid") is not None:
                controller_pids.add(int(body["controller_pid"]))
        except Exception as exc:
            health_failures.append(str(exc))

        job_response = client.get(urljoin(base, f"api/jobs/{job_id}"))
        job_response.raise_for_status()
        job = job_response.json()
        statuses.append(
            {
                "time": time.time(),
                "status": job.get("status"),
                "progress": job.get("progress"),
                "message": job.get("message"),
            }
        )
        if job.get("status") in TERMINAL:
            break
        time.sleep(0.75)
    else:
        raise RuntimeError("Generation did not reach a terminal state within 15 minutes")

    if job.get("status") != "succeeded":
        raise RuntimeError(f"Generation failed: {job.get('error')}")
    evidence_response = client.get(urljoin(base, "api/verification/latest"))
    evidence_response.raise_for_status()
    evidence = evidence_response.json()
    media_response = client.get(urljoin(base, str(job["result_url"]).lstrip("/")))
    media_response.raise_for_status()
    if not (media_response.content.startswith(b"RIFF") and media_response.content[8:12] == b"WAVE"):
        raise RuntimeError("Served artifact is not a WAV file")

    audio_path = Path(str(evidence["audio"]["path"]))
    audio = inspect_audio(audio_path)
    if audio["sha256"] != evidence["audio"]["sha256"]:
        raise RuntimeError("Acceptance checksum does not match controller verification")
    if health_failures or len(controller_pids) != 1:
        raise RuntimeError(f"Controller continuity failed: {health_failures}, pids={controller_pids}")
    p95 = percentile(latencies, 0.95)
    if p95 >= 250:
        raise RuntimeError(f"Controller health p95 was {p95:.2f} ms, above the 250 ms target")

    acceptance = {
        "schema_version": 1,
        "success": True,
        "accepted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "job_id": job_id,
        "request": request,
        "controller": {
            "pid": next(iter(controller_pids)),
            "health_samples": len(latencies),
            "health_failures": 0,
            "health_latency_p95_ms": round(p95, 3),
            "health_latency_max_ms": round(max(latencies), 3),
            "remained_online": True,
        },
        "job": job,
        "audio": audio,
        "worker": evidence["worker"],
        "elapsed_seconds": round(time.time() - submitted_at, 3),
        "status_samples": statuses,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(acceptance, indent=2), encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps(acceptance, indent=2))


if __name__ == "__main__":
    main()
