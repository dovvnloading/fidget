# Fidget

[![License: MIT](https://img.shields.io/github/license/dovvnloading/fidget?style=flat-square)](LICENSE)
[![Platform: Windows](https://img.shields.io/badge/platform-Windows-0078D6?style=flat-square&logo=windows&logoColor=white)](#requirements)
[![Runs 100% locally](https://img.shields.io/badge/runs-100%25%20locally-brightgreen?style=flat-square)](#architecture)
[![GPU: NVIDIA CUDA](https://img.shields.io/badge/GPU-NVIDIA%20CUDA-76B900?style=flat-square&logo=nvidia&logoColor=white)](#requirements)
[![Powered by ACE-Step 1.5](https://img.shields.io/badge/powered%20by-ACE--Step%201.5-e8734f?style=flat-square)](https://github.com/ace-step/ACE-Step-1.5)
[![Code signed](https://img.shields.io/badge/releases-code%20signed-2ea44f?style=flat-square)](packaging/SIGNING.md)

Fidget is a Windows desktop application for local text-to-music generation. It provides a native interface over the [ACE-Step 1.5](https://github.com/ace-step/ACE-Step-1.5) model, running inference on the local GPU and producing complete tracks — structure, instrumentation, and optional vocals — from a text description and, optionally, lyrics. No audio, prompts, or telemetry leave the machine.

![The Fidget interface](docs/screenshot.png)

## Contents

- [Overview](#overview)
- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
- [Architecture](#architecture)
- [HTTP API](#http-api)
- [Configuration](#configuration)
- [Development](#development)
- [Acknowledgements](#acknowledgements)
- [Licence](#licence)

## Overview

Fidget consists of a native WebView2 window, a FastAPI controller that owns the job queue, and a per-generation worker process that runs the ACE-Step runtime in isolation. The interface is a React application served by the controller.

Principal capabilities:

- **Prompt composition.** A curated library of complete prompts across eight genre families, each carrying tempo, key, and duration, alongside a library of individual descriptors (genre, instrumentation, vocal character, mood, rhythm, production) that can be toggled into a caption without disturbing hand-written text.
- **Track length** from 10 to 480 seconds on the default profile.
- **Batch generation.** Up to four takes per request, each with a distinct seed, executed sequentially with resource settling between runs.
- **Library management.** Finished takes are persisted with their full parameters. Unheard tracks are visually distinguished; tracks can be favourited or deleted (including their audio on disk).
- **Playback.** A waveform rendered from the decoded audio, seek, volume, and a per-track detail panel reporting render time, peak memory, measured duration, RMS, seed, and SHA-256.
- **Reproducibility.** Every take records the seed that produced it.

## Requirements

| Component | Requirement |
|---|---|
| Operating system | Windows 10 or Windows 11 (x64) |
| GPU | NVIDIA, CUDA-capable, 8 GB VRAM minimum |
| System memory | 16 GB |
| Runtime | Microsoft Edge WebView2 (present on Windows 11 and current Windows 10) |
| Build tooling (source installs only) | Python 3.12, Node.js 20, Git |

The reference configuration is an RTX 3060 Ti (8 GB), Intel i5-10400F, and 16 GB RAM. ACE-Step selects its own duration and batch limits according to detected VRAM; larger cards permit longer tracks and faster rendering.

## Installation

### Binary release

1. Download the latest archive from the [releases page](https://github.com/dovvnloading/fidget/releases).
2. Extract it to any location and run `Fidget.exe`.

Release executables are code-signed. The signature can be verified with:

```powershell
Get-AuthenticodeSignature .\Fidget\Fidget.exe | Format-List Status, SignerCertificate
```

Each release also publishes a SHA-256 checksum for the archive.

The ACE-Step model is **not** bundled with releases. It is several gigabytes and is installed once, to a shared location, by the setup script described below. Run `setup.ps1` from a source checkout to provision it; the binary release will then locate it automatically.

### From source

```powershell
.\setup.ps1
.\run.ps1
```

`setup.ps1` creates the Python environment, builds the frontend, clones ACE-Step into an isolated runtime, downloads the Turbo and 0.6B language-model checkpoints, and verifies CUDA availability. Pass `-SkipModelDownload` to provision everything except the model weights.

## Usage

### Describing a track

The caption is the primary control. The bundled prompt library follows the structure the model is trained against: approximately two sentences naming **genre**, **instrumentation**, **mood**, and **production style**.

> A nostalgic boom-bap hip-hop track with a chopped soul sample, upright bass, and a crisp swung snare. Features vinyl crackle, muted rhodes chords, and warm, lo-fi production.

Specific instrumentation and production detail produce more consistent results than genre labels alone.

Tempo and key should be set using their dedicated controls rather than described in the caption. ACE-Step treats caption text and metadata parameters as separate inputs, and conflicting values between them degrade output.

### Lyrics

Selecting **With vocals** exposes a lyrics field. Bracketed section tags define song structure and guide dynamics:

```
[Intro]

[Verse 1]
Slow light on the kitchen floor
Everything the way you left it

[Chorus]
We rise together
Into the light

[Bridge]

[Outro]
```

Lines of six to ten syllables align most reliably with the generated melody. Upper-case text increases vocal intensity; parenthesised text is rendered as backing vocals. Section tags are useful on their own, without lyric content, as a structural guide.

### Takes

The **Takes** control requests one to four variations of the current prompt. Takes are queued and rendered sequentially; any queued take can be cancelled independently.

## Architecture

Fidget separates the interface, the controller, and generation into three processes.

| Process | Role |
|---|---|
| **Window** | A pywebview WebView2 host. Contains no model code. |
| **Controller** | A FastAPI service that serves the interface, persists job state, and owns a single-worker queue. |
| **Worker** | A short-lived process, one per generation, that loads the ACE-Step runtime, renders a track, and exits. |

Each worker runs inside a Windows Job Object at below-normal priority, emits a heartbeat, and is terminated by the controller if it stops responding, exceeds the configured timeout, or drives available system or GPU memory below the abort floors. Launch is refused outright if free memory is already below the launch floors. GPU memory is released on worker exit, before the next job starts.

Output is written atomically. Before a track is exposed to the interface, the controller independently parses the WAV, rejects silent or near-silent audio, and confirms that its SHA-256 digest matches the one reported by the worker. A verification record for every job is written to `state/verification/<job-id>.json`.

Source layout:

```
fidget/backend/     Controller, job queue, worker supervision, audio validation
fidget/worker/      Isolated generation process (executed by the ACE-Step runtime)
frontend/src/       React interface
packaging/          PyInstaller spec, build script, signing documentation
```

## HTTP API

The controller binds to a random loopback port on each launch. The interface is its only intended client, but the surface is small and stable.

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/health` | Liveness and uptime |
| `GET` | `/api/model` | Runtime state, hardware, memory headroom, and active limits |
| `POST` | `/api/generate` | Submit a generation request; returns one job per requested take |
| `GET` | `/api/jobs` | All jobs, newest first |
| `GET` | `/api/jobs/{id}` | A single job |
| `POST` | `/api/jobs/{id}/cancel` | Cancel a queued or running job |
| `POST` | `/api/jobs/{id}/retry` | Re-submit a job's parameters |
| `POST` | `/api/jobs/{id}/favorite` | Set or clear the favourite flag |
| `DELETE` | `/api/jobs/{id}` | Remove a finished job and its artefacts |
| `GET` | `/api/verification/latest` | The most recent successful verification record |

## Configuration

All settings have working defaults. They can be overridden through environment variables.

| Variable | Default | Description |
|---|---|---|
| `FIDGET_MAX_DURATION` | `480` | Maximum track length in seconds |
| `FIDGET_MAX_VARIATIONS` | `4` | Maximum takes per request |
| `FIDGET_ENABLE_LM` | `true` | Use the 0.6B language model for planning. Set to `false` to reduce memory use. |
| `FIDGET_MIN_RAM_GB` | `7.0` | Free system memory required to launch a worker |
| `FIDGET_MIN_FREE_VRAM_MB` | `7000` | Free GPU memory required to launch a worker |
| `FIDGET_ABORT_RAM_GB` | `2.5` | Free system memory below which a running worker is terminated |
| `FIDGET_ABORT_FREE_VRAM_MB` | `420` | Free GPU memory below which a running worker is terminated |
| `FIDGET_WORKER_TIMEOUT` | `1200` | Hard timeout per generation, in seconds |
| `FIDGET_HEARTBEAT_TIMEOUT` | `45` | Seconds without a heartbeat before a worker is considered hung |
| `FIDGET_JOB_COOLDOWN_SECONDS` | `6` | Pause between consecutive takes |
| `FIDGET_SETTLE_TIMEOUT_SECONDS` | `120` | Maximum wait for memory to be reclaimed before a take is abandoned |
| `FIDGET_CUDA_MEMORY_FRACTION` | `0.86` | Fraction of GPU memory the worker may allocate |
| `FIDGET_DATA_ROOT` | `D:\AI\fidget` | Location of the model runtime, generated audio, and job state |

## Development

```powershell
# Run the test suite
.\.venv\Scripts\python.exe -m pytest -q

# Build the interface
npm --prefix .\frontend run build

# Interface with hot reload, proxied to a running controller
npm --prefix .\frontend run dev

# Produce a distributable build
.\packaging\build.ps1 -Version 1.0.0
```

Releases are produced by the GitHub Actions workflow in `.github/workflows/release.yml` on tag push. The workflow builds, tests, signs the executable via Azure Artifact Signing over OpenID Connect, and publishes the archive with its checksum. See [`packaging/SIGNING.md`](packaging/SIGNING.md) for the signing configuration.

## Acknowledgements

All audio is generated by **ACE-Step 1.5**, an open-source music generation model developed by ACE Studio and StepFun. Fidget is an interface to that model and contributes no generative capability of its own.

ACE-Step produces full-length compositions with coherent structure, multilingual vocals, and explicit control over tempo, key, and time signature, at speeds suitable for consumer hardware. Fidget uses the `acestep-v15-turbo` checkpoint with the `acestep-5Hz-lm-0.6B` language model, a configuration selected to operate within 8 GB of VRAM.

| | |
|---|---|
| Repository | <https://github.com/ace-step/ACE-Step-1.5> |
| Model weights | <https://huggingface.co/ACE-Step/Ace-Step1.5> |
| Project page | <https://ace-step.github.io/ace-step-v1.5.github.io/> |

The model and its source are released under the MIT Licence. Fidget does not redistribute them; `setup.ps1` retrieves them from the official sources at install time.

If ACE-Step contributes to published work, the authors request the following citation:

```bibtex
@misc{gong2026acestep,
    title={ACE-Step 1.5: Pushing the Boundaries of Open-Source Music Generation},
    author={Junmin Gong, Yulin Song, Wenxiao Zhao, Sen Wang, Shengyuan Xu, Jing Guo},
    howpublished={\url{https://github.com/ace-step/ACE-Step-1.5}},
    year={2026},
    note={GitHub repository}
}
```

## Licence

Fidget is released under the MIT Licence. See [LICENSE](LICENSE).

Generated audio is the property of the user. Use of the model weights is governed separately by the ACE-Step licence.
