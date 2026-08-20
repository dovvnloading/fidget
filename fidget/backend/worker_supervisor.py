"""Supervise disposable ACE-Step workers without importing Torch in the app."""

from __future__ import annotations

import ctypes
import json
import os
import queue
import secrets
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Callable

from .config import AppConfig
from .schemas import GenerationRequest


ProgressCallback = Callable[[float, str, int | None], None]

if os.name == "nt":
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _psapi = ctypes.WinDLL("psapi", use_last_error=True)
    _kernel32.GlobalMemoryStatusEx.argtypes = [ctypes.c_void_p]
    _kernel32.GlobalMemoryStatusEx.restype = ctypes.c_int
    _kernel32.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    _kernel32.OpenProcess.restype = ctypes.c_void_p
    _kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    _kernel32.CloseHandle.restype = ctypes.c_int
    _kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
    _kernel32.CreateJobObjectW.restype = ctypes.c_void_p
    _kernel32.SetInformationJobObject.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_ulong,
    ]
    _kernel32.SetInformationJobObject.restype = ctypes.c_int
    _kernel32.AssignProcessToJobObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    _kernel32.AssignProcessToJobObject.restype = ctypes.c_int
    _psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
    _psapi.GetProcessMemoryInfo.restype = ctypes.c_int
else:
    _kernel32 = None
    _psapi = None


class WorkerCancelledError(RuntimeError):
    """The active generation was explicitly cancelled."""


class WorkerProcessError(RuntimeError):
    """The isolated worker failed or violated its supervision contract."""


class WorkerResourceError(WorkerProcessError):
    """Not enough free memory to launch right now.

    Distinct from its parent because this condition is expected to clear on its
    own -- typically the previous worker's VRAM has not been reclaimed yet --
    so a queue may wait on it, where a missing runtime must fail immediately.
    """


class _MemoryStatus(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


class _ProcessMemoryCounters(ctypes.Structure):
    _fields_ = [
        ("cb", ctypes.c_ulong),
        ("PageFaultCount", ctypes.c_ulong),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


def _available_ram_gb() -> float | None:
    if os.name != "nt":
        return None
    status = _MemoryStatus()
    status.dwLength = ctypes.sizeof(status)
    assert _kernel32 is not None
    if not _kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return None
    return round(status.ullAvailPhys / 1024**3, 3)


def _process_rss_mb(pid: int) -> float | None:
    if os.name != "nt":
        return None
    assert _kernel32 is not None and _psapi is not None
    handle = _kernel32.OpenProcess(0x0410, False, pid)
    if not handle:
        return None
    try:
        counters = _ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        if not _psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
            return None
        return round(counters.WorkingSetSize / 1024**2, 2)
    finally:
        _kernel32.CloseHandle(handle)


class _SystemMonitor:
    """Sample expensive system metrics off the API request path."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._latest: dict[str, Any] = self._sample()
        self._thread = threading.Thread(target=self._loop, name="fidget-resource-monitor", daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        while not self._stop.wait(2.0):
            sample = self._sample()
            with self._lock:
                self._latest = sample

    @staticmethod
    def _sample() -> dict[str, Any]:
        sample: dict[str, Any] = {
            "sampled_at": time.time(),
            "available_ram_gb": _available_ram_gb(),
            "vram_used_mb": None,
            "vram_total_mb": None,
            "vram_free_mb": None,
            "gpu_utilization_percent": None,
            "gpu_temperature_c": None,
        }
        try:
            completed = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=memory.used,memory.total,utilization.gpu,temperature.gpu",
                    "--format=csv,noheader,nounits",
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=3,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            used_text, total_text, utilization_text, temperature_text = (
                value.strip() for value in completed.stdout.splitlines()[0].split(",")
            )
            used = int(used_text)
            total = int(total_text)
            sample.update(
                {
                    "vram_used_mb": used,
                    "vram_total_mb": total,
                    "vram_free_mb": total - used,
                    "gpu_utilization_percent": int(utilization_text),
                    "gpu_temperature_c": int(temperature_text),
                }
            )
        except (OSError, ValueError, IndexError, subprocess.SubprocessError):
            pass
        return sample

    def refresh(self) -> dict[str, Any]:
        sample = self._sample()
        with self._lock:
            self._latest = sample
        return dict(sample)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._latest)

    def close(self) -> None:
        self._stop.set()
        self._thread.join(timeout=4)


class _IoCounters(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_ulonglong),
        ("WriteOperationCount", ctypes.c_ulonglong),
        ("OtherOperationCount", ctypes.c_ulonglong),
        ("ReadTransferCount", ctypes.c_ulonglong),
        ("WriteTransferCount", ctypes.c_ulonglong),
        ("OtherTransferCount", ctypes.c_ulonglong),
    ]


class _BasicLimitInformation(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", ctypes.c_ulong),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", ctypes.c_ulong),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", ctypes.c_ulong),
        ("SchedulingClass", ctypes.c_ulong),
    ]


class _ExtendedLimitInformation(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _BasicLimitInformation),
        ("IoInfo", _IoCounters),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


class _WindowsJob:
    """Kill the worker process tree if its supervisor exits."""

    def __init__(self, pid: int) -> None:
        self.handle: int | None = None
        if os.name != "nt":
            return
        assert _kernel32 is not None
        kernel = _kernel32
        handle = kernel.CreateJobObjectW(None, None)
        if not handle:
            return
        info = _ExtendedLimitInformation()
        info.BasicLimitInformation.LimitFlags = 0x00002000  # KILL_ON_JOB_CLOSE
        if not kernel.SetInformationJobObject(handle, 9, ctypes.byref(info), ctypes.sizeof(info)):
            kernel.CloseHandle(handle)
            return
        process_handle = kernel.OpenProcess(0x0001 | 0x0100 | 0x0400, False, pid)
        if not process_handle:
            kernel.CloseHandle(handle)
            return
        assigned = kernel.AssignProcessToJobObject(handle, process_handle)
        kernel.CloseHandle(process_handle)
        if not assigned:
            kernel.CloseHandle(handle)
            return
        self.handle = handle

    def close(self) -> None:
        if self.handle and os.name == "nt":
            assert _kernel32 is not None
            _kernel32.CloseHandle(self.handle)
            self.handle = None


class WorkerSupervisor:
    """Run one bounded generation at a time in a disposable CUDA process."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self._lock = threading.RLock()
        self._process: subprocess.Popen[str] | None = None
        self._active_job_id: str | None = None
        self._cancel_requested = False
        self._last_error: str | None = None
        self._monitor = _SystemMonitor()

    def prerequisites(self) -> tuple[bool, str | None]:
        if not self.config.worker_python.is_file():
            return False, "ACE-Step runtime is not installed. Run setup.ps1."
        if not self.config.worker_script.is_file():
            return False, f"Worker script is missing: {self.config.worker_script}"
        required_weights = [
            self.config.model_dir / "acestep-v15-turbo" / "model.safetensors",
            self.config.model_dir / "Qwen3-Embedding-0.6B" / "model.safetensors",
            self.config.model_dir / "vae" / "diffusion_pytorch_model.safetensors",
        ]
        if self.config.enable_lm:
            required_weights.append(
                self.config.model_dir / "acestep-5Hz-lm-0.6B" / "model.safetensors"
            )
        if not (self.config.ace_project_root / "acestep").is_dir():
            return False, f"ACE-Step source is missing: {self.config.ace_project_root}"
        if any(not path.is_file() or path.stat().st_size < 100_000_000 for path in required_weights):
            return False, "ACE-Step Turbo or 0.6B model files are incomplete. Run setup.ps1."
        return True, None

    def status(self) -> dict[str, Any]:
        ready, prerequisite_error = self.prerequisites()
        resources = self._monitor.snapshot()
        with self._lock:
            running = bool(self._process and self._process.poll() is None)
            if running:
                state = "running"
            elif not ready:
                state = "not_installed"
            elif self._last_error:
                state = "error"
            else:
                state = "ready"
            total = resources.get("vram_total_mb")
            used = resources.get("vram_used_mb")
            percent = round(used / total * 100, 1) if used is not None and total else 0
            return {
                "state": state,
                "status": state,
                "ready": ready,
                "installed": ready,
                "model_name": "ACE-Step 1.5 Turbo",
                "model_detail": (
                    "2B DiT + 0.6B LM · full songs · isolated worker"
                    if self.config.enable_lm
                    else "2B DiT INT8 · full songs · isolated safety gate"
                ),
                "device": "RTX 3060 Ti · CUDA",
                "license": "MIT code · local open weights",
                "vram_used": f"{used} MB" if used is not None else None,
                "vram_total": f"{total} MB" if total is not None else None,
                "vram_percent": percent,
                "available_ram_gb": resources.get("available_ram_gb"),
                "max_duration_seconds": self.config.max_duration_seconds,
                "max_variations": self.config.max_variations,
                "active_job_id": self._active_job_id,
                "pid": self._process.pid if running and self._process else None,
                "checkpoints_path": str(self.config.model_dir),
                "runtime_path": str(self.config.worker_runtime),
                "error": self._last_error or prerequisite_error,
            }

    def start(self) -> dict[str, Any]:
        ready, error = self.prerequisites()
        with self._lock:
            self._last_error = None if ready else error
        return self.status()

    def stop(self) -> dict[str, Any]:
        self.cancel_current()
        return self.status()

    def preflight(self) -> dict[str, Any]:
        ready, error = self.prerequisites()
        if not ready:
            raise WorkerProcessError(error or "ACE-Step runtime is incomplete")
        resources = self._monitor.refresh()
        available_ram = resources.get("available_ram_gb")
        free_vram = resources.get("vram_free_mb")
        if available_ram is not None and available_ram < self.config.min_available_ram_gb:
            raise WorkerResourceError(
                f"Generation blocked safely: {available_ram:.1f} GB RAM is free; "
                f"at least {self.config.min_available_ram_gb:.1f} GB is required."
            )
        if free_vram is not None and free_vram < self.config.min_free_vram_mb:
            raise WorkerResourceError(
                f"Generation blocked safely: {free_vram} MB GPU memory is free; "
                f"at least {self.config.min_free_vram_mb} MB is required."
            )
        return resources

    def await_resources(
        self,
        timeout: float,
        on_wait: Callable[[str], None] | None = None,
        should_abort: Callable[[], bool] | None = None,
    ) -> dict[str, Any]:
        """Preflight, tolerating memory that is still being handed back.

        Only :class:`WorkerResourceError` is retried; a broken runtime raises on
        the first attempt. Returns the successful preflight snapshot.
        """
        deadline = time.monotonic() + max(0.0, timeout)
        notified = False
        while True:
            if should_abort is not None and should_abort():
                raise WorkerCancelledError("Cancelled while waiting for memory")
            try:
                return self.preflight()
            except WorkerResourceError:
                if time.monotonic() >= deadline:
                    raise
                if on_wait is not None and not notified:
                    notified = True
                    on_wait("Waiting for the GPU to release memory")
                time.sleep(2.0)

    def run_generation(
        self,
        job_id: str,
        request: GenerationRequest,
        progress: ProgressCallback,
    ) -> dict[str, Any]:
        baseline = self.preflight()
        self.config.ensure_directories()
        seed = request.seed if request.seed is not None else secrets.randbelow(2_147_483_648)
        output_path = self.config.outputs_dir / f"{job_id}.wav"
        request_path = self.config.requests_dir / f"{job_id}.json"
        result_path = self.config.results_dir / f"{job_id}.json"
        log_path = self.config.logs_dir / f"ace-{job_id}.log"
        payload = {
            "job_id": job_id,
            "ace_project_root": str(self.config.ace_project_root),
            "checkpoint_dir": str(self.config.model_dir),
            "output_path": str(output_path),
            "prompt": request.prompt,
            "lyrics": request.lyrics,
            "duration_seconds": request.duration,
            "bpm": request.bpm,
            "key_scale": request.key_scale,
            "time_signature": request.time_signature,
            "instrumental": request.instrumental,
            "seed": seed,
            "cuda_memory_fraction": self.config.cuda_memory_fraction,
            "use_lm": self.config.enable_lm,
        }
        self._write_json(request_path, payload)
        for stale in (result_path, output_path, output_path.with_suffix(".partial.wav")):
            try:
                stale.unlink()
            except FileNotFoundError:
                pass

        env = os.environ.copy()
        env.update(
            {
                "HF_HUB_OFFLINE": "1",
                "TRANSFORMERS_OFFLINE": "1",
                "TOKENIZERS_PARALLELISM": "false",
                "PYTHONUNBUFFERED": "1",
                "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True,max_split_size_mb:128",
                "CUDA_MODULE_LOADING": "LAZY",
                "OMP_NUM_THREADS": "4",
                "MKL_NUM_THREADS": "4",
                "MAX_CUDA_VRAM": "7",
                "ACESTEP_SAVE_MEMORY": "1",
                "ACESTEP_VAE_ON_CPU": "0",
                "ACESTEP_CONFIGURE_THREADS": "1",
                "ACESTEP_CHECKPOINTS_DIR": str(self.config.model_dir),
                "ACESTEP_CONFIG_PATH": "acestep-v15-turbo",
                "ACESTEP_LM_MODEL_PATH": self.config.lm_model_id,
                "ACESTEP_LM_BACKEND": "pt",
                "ACESTEP_INIT_LLM": "true" if self.config.enable_lm else "false",
                "ACESTEP_COMPILE_MODEL": "false",
            }
        )
        creation_flags = (
            getattr(subprocess, "CREATE_NO_WINDOW", 0)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            | getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)
        )
        process = subprocess.Popen(
            [
                str(self.config.worker_python),
                str(self.config.worker_script),
                "--request",
                str(request_path),
                "--result",
                str(result_path),
            ],
            cwd=self.config.project_root,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=creation_flags,
        )
        job_object = _WindowsJob(process.pid)
        with self._lock:
            self._process = process
            self._active_job_id = job_id
            self._cancel_requested = False
            self._last_error = None
        progress(2, "Worker process isolated", process.pid)

        lines: queue.Queue[str] = queue.Queue()

        def read_output() -> None:
            assert process.stdout is not None
            with log_path.open("a", encoding="utf-8", errors="replace") as log:
                log.write(f"\n--- job {job_id} pid {process.pid} ---\n")
                for line in process.stdout:
                    log.write(line)
                    log.flush()
                    lines.put(line)

        reader = threading.Thread(target=read_output, name=f"worker-log-{job_id}", daemon=True)
        reader.start()
        started = time.monotonic()
        last_heartbeat = started
        peak_worker_rss = 0.0
        peak_gpu_used = float(baseline.get("vram_used_mb") or 0)
        minimum_available_ram = float(baseline.get("available_ram_gb") or 0)
        final_event: dict[str, Any] | None = None
        actual_worker_pid = process.pid

        try:
            while True:
                while True:
                    try:
                        raw_line = lines.get_nowait()
                    except queue.Empty:
                        break
                    try:
                        event = json.loads(raw_line)
                    except json.JSONDecodeError:
                        continue
                    # Transformers writes pretty-printed model config to the
                    # merged log stream. A line such as `"relu"` is valid JSON
                    # but is not one of our structured worker events.
                    if not isinstance(event, dict):
                        continue
                    event_pid = event.get("worker_pid")
                    if isinstance(event_pid, int) and event_pid > 0:
                        actual_worker_pid = event_pid
                    last_heartbeat = time.monotonic()
                    if event.get("type") == "progress":
                        final_event = event
                        progress(
                            float(event.get("progress", 5)),
                            str(event.get("message", "Generating locally")),
                            actual_worker_pid,
                        )
                    elif event.get("type") == "error":
                        final_event = event

                rss = _process_rss_mb(actual_worker_pid)
                if rss is not None:
                    peak_worker_rss = max(peak_worker_rss, rss)
                resources = self._monitor.snapshot()
                if resources.get("vram_used_mb") is not None:
                    peak_gpu_used = max(peak_gpu_used, float(resources["vram_used_mb"]))
                if resources.get("available_ram_gb") is not None:
                    value = float(resources["available_ram_gb"])
                    minimum_available_ram = value if minimum_available_ram == 0 else min(minimum_available_ram, value)
                    if value < self.config.abort_available_ram_gb:
                        self._terminate(process)
                        raise WorkerProcessError(
                            f"ACE-Step was terminated safely to preserve the desktop: "
                            f"available RAM fell to {value:.2f} GB."
                        )
                free_vram = resources.get("vram_free_mb")
                if free_vram is not None and int(free_vram) < self.config.abort_free_vram_mb:
                    self._terminate(process)
                    raise WorkerProcessError(
                        f"ACE-Step was terminated safely to preserve display stability: "
                        f"free VRAM fell to {free_vram} MB."
                    )

                with self._lock:
                    cancelled = self._cancel_requested
                if cancelled:
                    self._terminate(process)
                    raise WorkerCancelledError("Generation cancelled")
                elapsed = time.monotonic() - started
                if elapsed > self.config.worker_timeout_seconds:
                    self._terminate(process)
                    raise WorkerProcessError("ACE-Step worker exceeded its safety timeout")
                if time.monotonic() - last_heartbeat > self.config.heartbeat_timeout_seconds:
                    self._terminate(process)
                    raise WorkerProcessError("ACE-Step worker stopped responding and was terminated safely")
                if process.poll() is not None and lines.empty() and not reader.is_alive():
                    break
                time.sleep(0.25)

            exit_code = process.wait(timeout=5)
            reader.join(timeout=3)
            result = self._read_json(result_path)
            if exit_code != 0 or not result.get("ok"):
                detail = str(result.get("error") or (final_event or {}).get("message") or "unknown worker failure")
                if exit_code in {-1073741819, 3221225477}:
                    detail = f"Native access violation in the isolated worker: {detail}"
                raise WorkerProcessError(f"ACE-Step worker exited with code {exit_code}: {detail}")
            if Path(str(result.get("output_path", ""))).resolve() != output_path.resolve():
                raise WorkerProcessError("Worker result referenced an unexpected output path")
            result.update(
                {
                    "exit_code": exit_code,
                    "peak_worker_rss_mb": round(peak_worker_rss, 2),
                    "baseline_gpu_used_mb": baseline.get("vram_used_mb"),
                    "peak_gpu_used_mb": int(peak_gpu_used),
                    "minimum_available_ram_gb": round(minimum_available_ram, 3),
                    "job_object_assigned": bool(job_object.handle),
                    "launcher_pid": process.pid,
                    "actual_worker_pid": actual_worker_pid,
                    "log_path": str(log_path),
                }
            )
            return result
        except Exception as exc:
            with self._lock:
                self._last_error = str(exc)
            raise
        finally:
            if process.poll() is None:
                self._terminate(process)
            job_object.close()
            with self._lock:
                self._process = None
                self._active_job_id = None
                self._cancel_requested = False

    def cancel_current(self, job_id: str | None = None) -> bool:
        with self._lock:
            if not self._process or self._process.poll() is not None:
                return False
            if job_id is not None and job_id != self._active_job_id:
                return False
            self._cancel_requested = True
            return True

    def shutdown(self) -> None:
        self.cancel_current()
        with self._lock:
            process = self._process
        if process and process.poll() is None:
            self._terminate(process)
        self._monitor.close()

    @staticmethod
    def _build_prompt(request: GenerationRequest) -> str:
        parts = [request.prompt.strip()]
        if request.bpm:
            parts.append(f"{request.bpm} BPM")
        if request.key_scale:
            parts.append(request.key_scale)
        if request.time_signature:
            parts.append(f"{request.time_signature} time")
        if request.lyrics.strip():
            notes = " ".join(request.lyrics.split())[:400]
            parts.append(f"creative theme and imagery: {notes}")
        parts.append("instrumental music, no vocals")
        return ", ".join(parts)

    @staticmethod
    def _write_json(path: Path, value: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(value, indent=2), encoding="utf-8")
        temporary.replace(path)

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except (OSError, ValueError, TypeError):
            return {}

    @staticmethod
    def _terminate(process: subprocess.Popen[str]) -> None:
        if process.poll() is not None:
            return
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                check=False,
                capture_output=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        else:
            process.terminate()
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            process.kill()
