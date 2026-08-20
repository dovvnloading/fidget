"""Run a mixed three-job ACE-Step reliability gate against a live controller."""

from __future__ import annotations

import argparse
import json
import math
import os
import time
from pathlib import Path
from urllib.parse import urljoin

import httpx

from verify_end_to_end import inspect_audio, percentile


CASES = [
    {
        "duration": 10,
        "prompt": "warm analog ambient synth chords with gentle tape texture",
        "lyrics": "",
        "instrumental": True,
    },
    {
        "duration": 15,
        "prompt": "intimate indie pop, clear warm lead vocal, acoustic guitar and soft drums",
        "lyrics": "[Verse]\nMorning finds the open road\n[Chorus]\nCarry the light wherever we go",
        "instrumental": False,
    },
    {
        "duration": 30,
        "prompt": "cinematic electronic instrumental with evolving chords and a gentle rhythmic pulse",
        "lyrics": "",
        "instrumental": True,
    },
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(os.getenv("FIDGET_DATA_ROOT", "D:/AI/fidget"))
        / "state"
        / "verification"
        / "latest-reliability.json",
    )
    args = parser.parse_args()
    base = args.base_url.rstrip("/") + "/"
    client = httpx.Client(timeout=httpx.Timeout(10.0, read=20.0))
    results: list[dict[str, object]] = []
    all_health_latencies: list[float] = []
    health_failures: list[str] = []
    controller_pids: set[int] = set()
    started = time.time()

    for index, case in enumerate(CASES, start=1):
        duration = int(case["duration"])
        prompt = str(case["prompt"])
        request = {
            "prompt": prompt,
            "lyrics": str(case["lyrics"]),
            "duration": duration,
            "bpm": 78 + index * 4,
            "key_scale": "C Major" if index % 2 else "A Minor",
            "time_signature": "4/4",
            "instrumental": bool(case["instrumental"]),
            "seed": 20260900 + index,
        }
        job_started = time.time()
        response = client.post(urljoin(base, "api/generate"), json=request)
        response.raise_for_status()
        job_id = response.json()["id"]
        job: dict[str, object] = {}
        samples = 0
        deadline = time.monotonic() + 900
        while time.monotonic() < deadline:
            probe_started = time.perf_counter()
            try:
                health = client.get(urljoin(base, "api/health"))
                latency = (time.perf_counter() - probe_started) * 1000
                all_health_latencies.append(latency)
                health.raise_for_status()
                body = health.json()
                controller_pids.add(int(body["controller_pid"]))
                if not body.get("ok"):
                    health_failures.append(f"job {job_id}: payload not ok")
            except Exception as exc:
                health_failures.append(f"job {job_id}: {exc}")
            job_response = client.get(urljoin(base, f"api/jobs/{job_id}"))
            job_response.raise_for_status()
            job = job_response.json()
            samples += 1
            if job.get("status") in {"succeeded", "failed", "cancelled"}:
                break
            time.sleep(0.5)
        if job.get("status") != "succeeded":
            raise RuntimeError(f"Reliability job {index}/{len(CASES)} failed: {job.get('error')}")

        evidence_response = client.get(urljoin(base, "api/verification/latest"))
        evidence_response.raise_for_status()
        evidence = evidence_response.json()
        if evidence.get("job_id") != job_id:
            raise RuntimeError(f"Verification record did not advance to job {job_id}")
        audio = inspect_audio(Path(str(evidence["audio"]["path"])))
        if audio["sha256"] != evidence["audio"]["sha256"]:
            raise RuntimeError(f"Checksum mismatch for reliability job {job_id}")
        media = client.get(urljoin(base, str(job["result_url"]).lstrip("/")))
        media.raise_for_status()
        if not (media.content.startswith(b"RIFF") and media.content[8:12] == b"WAVE"):
            raise RuntimeError(f"Invalid served WAV for reliability job {job_id}")
        worker = evidence["worker"]
        if worker.get("exit_code") != 0 or not worker.get("in_windows_job_object"):
            raise RuntimeError(f"Worker containment failed for reliability job {job_id}")

        result = {
            "sequence": index,
            "job_id": job_id,
            "requested_duration_seconds": duration,
            "actual_duration_seconds": audio["duration_seconds"],
            "elapsed_seconds": round(time.time() - job_started, 3),
            "sha256": audio["sha256"],
            "rms": audio["rms"],
            "size_bytes": audio["size_bytes"],
            "peak_worker_rss_mb": worker.get("peak_worker_rss_mb"),
            "peak_gpu_used_mb": worker.get("peak_gpu_used_mb"),
            "minimum_available_ram_gb": worker.get("minimum_available_ram_gb"),
            "worker_exit_code": worker.get("exit_code"),
            "worker_contained": worker.get("in_windows_job_object"),
            "health_samples": samples,
        }
        results.append(result)
        print(
            f"[{index}/{len(CASES)}] PASS {duration}s -> {audio['duration_seconds']}s, "
            f"{result['elapsed_seconds']}s wall, GPU peak {result['peak_gpu_used_mb']} MB",
            flush=True,
        )

    success_count = len(results)
    p95 = percentile(all_health_latencies, 0.95)
    summary = {
        "schema_version": 1,
        "success": success_count == len(CASES) and not health_failures and len(controller_pids) == 1 and p95 < 250,
        "accepted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "jobs_attempted": len(CASES),
        "jobs_succeeded": success_count,
        "generation_success_rate": success_count / len(CASES),
        "artifact_validation_rate": success_count / len(CASES),
        "worker_crash_rate": 0.0,
        "cuda_oom_rate": 0.0,
        "health_failures": health_failures,
        "controller_pid_count": len(controller_pids),
        "controller_health_samples": len(all_health_latencies),
        "controller_health_p95_ms": round(p95, 3),
        "controller_health_max_ms": round(max(all_health_latencies), 3),
        "max_worker_rss_mb": max(float(item["peak_worker_rss_mb"]) for item in results),
        "max_gpu_used_mb": max(int(item["peak_gpu_used_mb"]) for item in results),
        "minimum_available_ram_gb": min(float(item["minimum_available_ram_gb"]) for item in results),
        "total_elapsed_seconds": round(time.time() - started, 3),
        "results": results,
    }
    if not summary["success"]:
        raise RuntimeError(f"Reliability gate failed: {summary}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    temporary.replace(args.output)
    archive = args.output.with_name(f"reliability-{len(CASES)}-{int(started)}.json")
    archive.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in summary.items() if key != "results"}, indent=2))


if __name__ == "__main__":
    main()
