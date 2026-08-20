"""One-shot, resource-bounded ACE-Step 1.5 worker.

The desktop controller never imports Torch or ACE-Step. Each request gets a
fresh child process in a Windows Job Object, and CUDA memory is released when
that process exits.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import threading
import time
import traceback
from pathlib import Path


_print_lock = threading.Lock()
_stop_heartbeat = threading.Event()


def emit(kind: str, **values: object) -> None:
    event = {"type": kind, "time": time.time(), "worker_pid": os.getpid(), **values}
    with _print_lock:
        print(json.dumps(event, ensure_ascii=True), flush=True)


def heartbeat_loop() -> None:
    while not _stop_heartbeat.wait(2.0):
        emit("heartbeat")


def atomic_json(path: str | Path, payload: dict[str, object]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, destination)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def in_windows_job_object() -> bool | None:
    if os.name != "nt":
        return None
    import ctypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    kernel32.IsProcessInJob.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
    kernel32.IsProcessInJob.restype = ctypes.c_int
    assigned = ctypes.c_int(0)
    current_process = kernel32.GetCurrentProcess()
    if not kernel32.IsProcessInJob(current_process, None, ctypes.byref(assigned)):
        return None
    return bool(assigned.value)


def run(request_path: str, result_path: str) -> int:
    started = time.time()
    request = json.loads(Path(request_path).read_text(encoding="utf-8"))
    ace_root = Path(request["ace_project_root"]).resolve()
    checkpoint_dir = Path(request["checkpoint_dir"]).resolve()
    output_path = Path(request["output_path"]).resolve()
    partial_path = output_path.with_suffix(".partial.wav")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    for stale in (partial_path, output_path):
        try:
            stale.unlink()
        except FileNotFoundError:
            pass

    if not (ace_root / "acestep").is_dir():
        raise RuntimeError(f"ACE-Step source is missing: {ace_root}")
    if not checkpoint_dir.is_dir():
        raise RuntimeError(f"ACE-Step checkpoints are missing: {checkpoint_dir}")
    sys.path.insert(0, str(ace_root))
    os.chdir(ace_root)

    emit("progress", progress=3, message="Starting isolated ACE-Step worker")
    import torch

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable in the ACE-Step worker runtime")
    memory_fraction = float(request.get("cuda_memory_fraction", 0.86))
    if not 0.5 <= memory_fraction <= 0.95:
        raise RuntimeError("Unsafe CUDA memory fraction")
    torch.cuda.set_per_process_memory_fraction(memory_fraction, 0)
    torch.backends.cuda.matmul.allow_tf32 = True
    gpu_name = torch.cuda.get_device_name(0)
    emit(
        "progress",
        progress=8,
        message="CUDA bounded; loading ACE-Step",
        torch_version=torch.__version__,
        gpu_name=gpu_name,
        cuda_memory_fraction=memory_fraction,
    )

    from acestep.handler import AceStepHandler
    from acestep.inference import GenerationConfig, GenerationParams, generate_music
    from acestep.llm_inference import LLMHandler

    emit("progress", progress=14, message="Loading ACE-Step Turbo INT8 with staged offload")
    dit_handler = AceStepHandler()
    status_dit, success_dit = dit_handler.initialize_service(
        project_root=str(ace_root),
        config_path="acestep-v15-turbo",
        device="cuda",
        use_flash_attention=False,
        compile_model=False,
        offload_to_cpu=True,
        offload_dit_to_cpu=False,
        quantization="int8_weight_only",
    )
    if not success_dit:
        raise RuntimeError(f"ACE-Step Turbo initialization failed: {status_dit}")

    use_lm = bool(request.get("use_lm", False))
    llm_handler = LLMHandler()
    if use_lm:
        emit("progress", progress=34, message="Loading ACE-Step 0.6B language model")
        status_lm, success_lm = llm_handler.initialize(
            checkpoint_dir=str(checkpoint_dir),
            lm_model_path="acestep-5Hz-lm-0.6B",
            backend="pt",
            device="cuda",
            offload_to_cpu=False,
            dtype=None,
        )
        if not success_lm:
            raise RuntimeError(f"ACE-Step language model initialization failed: {status_lm}")
    else:
        emit("progress", progress=40, message="ACE-Step Turbo loaded in DiT-only safety mode")

    seed = int(request["seed"])
    lyrics = str(request.get("lyrics") or "")
    instrumental = bool(request.get("instrumental", False))
    if instrumental:
        lyrics = "[Instrumental]"
    emit(
        "progress",
        progress=48,
        message="Planning full-song structure" if use_lm else "Preparing song conditioning",
    )
    params = GenerationParams(
        task_type="text2music",
        caption=str(request["prompt"]),
        lyrics=lyrics,
        instrumental=instrumental,
        bpm=request.get("bpm"),
        keyscale=str(request.get("key_scale") or ""),
        timesignature=str(request.get("time_signature") or "4"),
        vocal_language="en",
        duration=float(request["duration_seconds"]),
        thinking=use_lm,
        use_cot_metas=use_lm,
        use_cot_caption=use_lm,
        use_cot_language=use_lm and not instrumental,
        use_constrained_decoding=True,
        inference_steps=8,
        guidance_scale=1.0,
        seed=seed,
    )
    config = GenerationConfig(
        batch_size=1,
        allow_lm_batch=False,
        use_random_seed=False,
        seeds=[seed],
        audio_format="wav",
    )
    emit("progress", progress=58, message="Generating high-quality local audio")
    generation = generate_music(
        dit_handler,
        llm_handler,
        params=params,
        config=config,
        save_dir=str(output_path.parent),
    )
    if not generation.success or not generation.audios:
        detail = getattr(generation, "error", None) or getattr(generation, "status_message", None)
        raise RuntimeError(f"ACE-Step generation failed: {detail or 'no audio returned'}")
    generated_path = Path(str(generation.audios[0].get("path") or ""))
    if not generated_path.is_file():
        raise RuntimeError("ACE-Step reported success without a saved audio file")

    emit("progress", progress=94, message="Converting and validating PCM WAV artifact")
    import numpy as np
    import soundfile as sf

    waveform, sample_rate = sf.read(str(generated_path), dtype="float32", always_2d=True)
    waveform = np.nan_to_num(waveform, nan=0.0, posinf=0.0, neginf=0.0)
    peak = float(np.max(np.abs(waveform))) if waveform.size else 0.0
    rms = float(np.sqrt(np.mean(np.square(waveform, dtype=np.float64)))) if waveform.size else 0.0
    if waveform.size == 0 or peak < 1e-5 or rms < 1e-6:
        raise RuntimeError("ACE-Step returned an empty or silent waveform")
    waveform = np.clip(waveform, -1.0, 1.0)
    sf.write(str(partial_path), waveform, sample_rate, format="WAV", subtype="PCM_16")
    os.replace(partial_path, output_path)
    if generated_path.resolve() != output_path.resolve():
        try:
            generated_path.unlink()
        except OSError:
            pass

    result = {
        "ok": True,
        "worker_pid": os.getpid(),
        "output_path": str(output_path),
        "size_bytes": output_path.stat().st_size,
        "sha256": sha256_file(output_path),
        "sample_rate": int(sample_rate),
        "channels": int(waveform.shape[1]),
        "frames": int(waveform.shape[0]),
        "duration_seconds": round(float(waveform.shape[0]) / sample_rate, 3),
        "source_peak": round(peak, 7),
        "source_rms": round(rms, 7),
        "seed": seed,
        "gpu_name": gpu_name,
        "torch_version": torch.__version__,
        "engine": (
            "ACE-Step 1.5 Turbo + 0.6B LM"
            if use_lm
            else "ACE-Step 1.5 Turbo (DiT-only)"
        ),
        "in_windows_job_object": in_windows_job_object(),
        "elapsed_seconds": round(time.time() - started, 3),
    }
    atomic_json(result_path, result)
    emit("progress", progress=100, message="Verified ACE-Step WAV written", result=result)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True)
    parser.add_argument("--result", required=True)
    args = parser.parse_args()
    heartbeat = threading.Thread(target=heartbeat_loop, name="worker-heartbeat", daemon=True)
    heartbeat.start()
    try:
        return run(args.request, args.result)
    except Exception as exc:
        failure = {
            "ok": False,
            "worker_pid": os.getpid(),
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }
        try:
            atomic_json(args.result, failure)
        except Exception:
            pass
        emit("error", message=str(exc))
        return 1
    finally:
        _stop_heartbeat.set()


if __name__ == "__main__":
    sys.exit(main())
