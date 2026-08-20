"""Application paths and bounded ACE-Step generation settings."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _default_data_root(project_root: Path) -> Path:
    data_drive = Path("D:/")
    return data_drive / "AI" / "fidget" if data_drive.exists() else project_root / ".fidget-data"


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Resolved paths for the lightweight controller and isolated ACE worker."""

    project_root: Path
    frontend_dist: Path
    data_root: Path
    model_dir: Path
    worker_runtime: Path
    outputs_dir: Path
    state_dir: Path
    logs_dir: Path
    model_id: str = "ACE-Step/acestep-v15-turbo"
    lm_model_id: str = "acestep-5Hz-lm-0.6B"
    # ACE-Step reports 480s (with the LM) / 600s (without) for this machine's
    # GPU tier -- "tier3", 6-8GB, see acestep/gpu_config.py. Duration costs
    # almost no VRAM (the latent is a couple of MB even at 10 minutes) and
    # generation time scales sublinearly, so the old 120s ceiling was an
    # arbitrary floor-of-the-tier value rather than a real safety bound.
    # ACE-Step additionally clamps its own decoder to the detected tier, so a
    # value above what the hardware supports degrades rather than fails.
    max_duration_seconds: int = 480
    worker_timeout_seconds: int = 1200
    heartbeat_timeout_seconds: int = 45
    min_available_ram_gb: float = 7.0
    min_free_vram_mb: int = 7000
    abort_available_ram_gb: float = 2.5
    abort_free_vram_mb: int = 420
    # A finished worker's VRAM is not reclaimed the instant its process exits,
    # so back-to-back takes pause briefly and then wait for the driver to hand
    # the memory back rather than tripping the launch gate on a stale reading.
    cooldown_between_jobs_seconds: float = 6.0
    resource_settle_timeout_seconds: float = 120.0
    max_variations: int = 4
    cuda_memory_fraction: float = 0.86
    enable_lm: bool = True

    @property
    def worker_python(self) -> Path:
        return self.worker_runtime / "Scripts" / "python.exe"

    @property
    def worker_script(self) -> Path:
        return self.project_root / "fidget" / "worker" / "ace_worker.py"

    @property
    def ace_project_root(self) -> Path:
        return self.worker_runtime.parent

    @property
    def jobs_file(self) -> Path:
        return self.state_dir / "jobs.json"

    @property
    def requests_dir(self) -> Path:
        return self.state_dir / "requests"

    @property
    def results_dir(self) -> Path:
        return self.state_dir / "results"

    @property
    def verification_dir(self) -> Path:
        return self.state_dir / "verification"

    @property
    def latest_verification_file(self) -> Path:
        return self.verification_dir / "latest-success.json"

    @classmethod
    def from_environment(cls, project_root: Path | None = None) -> "AppConfig":
        root = (project_root or Path(__file__).resolve().parents[2]).resolve()
        data_root = Path(os.getenv("FIDGET_DATA_ROOT", _default_data_root(root))).resolve()
        return cls(
            project_root=root,
            frontend_dist=root / "frontend" / "dist",
            data_root=data_root,
            model_dir=Path(
                os.getenv(
                    "FIDGET_MODEL_DIR",
                    data_root / "ACE-Step-1.5" / "checkpoints",
                )
            ).resolve(),
            worker_runtime=Path(
                os.getenv(
                    "FIDGET_WORKER_RUNTIME",
                    data_root / "ACE-Step-1.5" / ".venv",
                )
            ).resolve(),
            outputs_dir=data_root / "outputs",
            state_dir=data_root / "state",
            logs_dir=data_root / "logs",
            max_duration_seconds=int(os.getenv("FIDGET_MAX_DURATION", "480")),
            worker_timeout_seconds=int(os.getenv("FIDGET_WORKER_TIMEOUT", "1200")),
            heartbeat_timeout_seconds=int(os.getenv("FIDGET_HEARTBEAT_TIMEOUT", "45")),
            min_available_ram_gb=float(os.getenv("FIDGET_MIN_RAM_GB", "7.0")),
            min_free_vram_mb=int(os.getenv("FIDGET_MIN_FREE_VRAM_MB", "7000")),
            abort_available_ram_gb=float(os.getenv("FIDGET_ABORT_RAM_GB", "2.5")),
            abort_free_vram_mb=int(os.getenv("FIDGET_ABORT_FREE_VRAM_MB", "420")),
            cooldown_between_jobs_seconds=float(os.getenv("FIDGET_JOB_COOLDOWN_SECONDS", "6")),
            resource_settle_timeout_seconds=float(os.getenv("FIDGET_SETTLE_TIMEOUT_SECONDS", "120")),
            max_variations=int(os.getenv("FIDGET_MAX_VARIATIONS", "4")),
            cuda_memory_fraction=float(os.getenv("FIDGET_CUDA_MEMORY_FRACTION", "0.86")),
            enable_lm=os.getenv("FIDGET_ENABLE_LM", "true").strip().lower()
            in {"1", "true", "yes", "on"},
        )

    def ensure_directories(self) -> None:
        for path in (
            self.data_root,
            self.model_dir,
            self.outputs_dir,
            self.state_dir,
            self.logs_dir,
            self.requests_dir,
            self.results_dir,
            self.verification_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)
