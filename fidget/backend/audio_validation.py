"""Independent validation for artifacts before the API exposes them."""

from __future__ import annotations

import hashlib
import math
import wave
from array import array
from pathlib import Path
from typing import Any


class InvalidAudioError(RuntimeError):
    """Raised when a worker output is not a usable PCM WAV file."""


def validate_wav(path: Path, expected_seconds: float | None = None) -> dict[str, Any]:
    """Parse, measure, and hash a PCM WAV file without model dependencies."""

    if not path.is_file():
        raise InvalidAudioError(f"Audio output does not exist: {path}")
    size_bytes = path.stat().st_size
    if size_bytes < 4096:
        raise InvalidAudioError("Audio output is too small to be a valid generated clip")

    try:
        with wave.open(str(path), "rb") as handle:
            channels = handle.getnchannels()
            sample_width = handle.getsampwidth()
            sample_rate = handle.getframerate()
            frames = handle.getnframes()
            compression = handle.getcomptype()
            raw = handle.readframes(frames)
    except (OSError, EOFError, wave.Error) as exc:
        raise InvalidAudioError(f"Audio output could not be parsed: {exc}") from exc

    if compression != "NONE" or sample_width != 2:
        raise InvalidAudioError("Audio output must be uncompressed 16-bit PCM WAV")
    if channels not in {1, 2} or sample_rate < 16_000 or frames <= 0:
        raise InvalidAudioError("Audio output has invalid channel, sample-rate, or frame metadata")

    duration_seconds = frames / sample_rate
    if expected_seconds is not None and not (expected_seconds * 0.82 <= duration_seconds <= expected_seconds * 1.12):
        raise InvalidAudioError(
            f"Audio duration {duration_seconds:.2f}s does not match requested {expected_seconds:.2f}s"
        )

    samples = array("h")
    samples.frombytes(raw)
    if not samples:
        raise InvalidAudioError("Audio output contains no samples")
    peak = max(abs(value) for value in samples) / 32768.0
    rms = math.sqrt(sum(value * value for value in samples) / len(samples)) / 32768.0
    if peak < 0.005 or rms < 0.0005:
        raise InvalidAudioError("Audio output is silent or effectively silent")

    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)

    return {
        "path": str(path.resolve()),
        "size_bytes": size_bytes,
        "sha256": digest.hexdigest(),
        "sample_rate": sample_rate,
        "channels": channels,
        "sample_width_bits": sample_width * 8,
        "frames": frames,
        "duration_seconds": round(duration_seconds, 3),
        "peak": round(peak, 6),
        "rms": round(rms, 6),
    }
