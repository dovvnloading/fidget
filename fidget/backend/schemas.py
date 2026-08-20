"""Request and response models exposed by Fidget's API."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class GenerationRequest(BaseModel):
    """A single bounded local ACE-Step request."""

    prompt: str = Field(min_length=3, max_length=1000)
    lyrics: str = Field(default="", max_length=4000)
    # Envelope only -- ACE-Step's own DURATION_MIN/DURATION_MAX (acestep/
    # constants.py). The deployed ceiling is AppConfig.max_duration_seconds,
    # enforced in app.generate(); keeping this at 120 silently capped
    # FIDGET_MAX_DURATION, since validation rejected the request before the
    # configurable check could run.
    duration: int = Field(default=30, ge=10, le=600)
    bpm: int | None = Field(default=None, ge=30, le=300)
    key_scale: str = Field(default="", max_length=40)
    time_signature: str = Field(default="4/4", max_length=12)
    instrumental: bool = True
    seed: int | None = Field(default=None, ge=0, le=2_147_483_647)
    # One submission can fan out into several same-prompt takes that differ only
    # by seed. They still run strictly one at a time on the single GPU worker.
    variations: int = Field(default=1, ge=1, le=4)

    @field_validator("prompt")
    @classmethod
    def strip_prompt(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise ValueError("Describe the music in at least three characters")
        return value


class JobRecord(BaseModel):
    """Persisted public state for a queued generation."""

    id: str
    status: Literal["queued", "starting", "running", "succeeded", "failed", "cancelled"]
    progress: float = Field(default=0, ge=0, le=100)
    message: str = "Queued"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: str | None = None
    prompt: str
    lyrics: str = ""
    duration: int
    bpm: int | None = None
    key_scale: str = ""
    time_signature: str = "4/4"
    instrumental: bool = True
    # Resolved when the job is queued rather than deep inside the worker, so a
    # take the user liked is always reproducible from what the API reports.
    seed: int | None = None
    # Set for every job; a lone take is simply a batch of one.
    batch_id: str | None = None
    batch_index: int = 1
    batch_size: int = 1
    result_url: str | None = None
    favorite: bool = False
    error: str | None = None
    worker_pid: int | None = None
    metrics: dict[str, Any] | None = None
