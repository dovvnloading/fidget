[CmdletBinding()]
param(
    [switch]$SkipModelDownload
)

$ErrorActionPreference = "Stop"
$RepoRoot = $PSScriptRoot
$AppVenv = Join-Path $RepoRoot ".venv"
$AppPython = Join-Path $AppVenv "Scripts\python.exe"
$DataRoot = if (Test-Path -LiteralPath "D:\") { "D:\AI\fidget" } else { Join-Path $RepoRoot ".fidget-data" }
$AceRoot = Join-Path $DataRoot "ACE-Step-1.5"
$AcePython = Join-Path $AceRoot ".venv\Scripts\python.exe"
$CheckpointDir = Join-Path $AceRoot "checkpoints"

$Python312 = (& py -3.12 -c "import sys; print(sys.executable)").Trim()
if ($LASTEXITCODE -ne 0 -or -not $Python312) {
    throw "Python 3.12 is required for the Fidget desktop controller."
}

if (-not (Test-Path -LiteralPath $AppPython)) {
    & $Python312 -m venv $AppVenv
}
& $AppPython -m pip install --upgrade pip
& $AppPython -m pip install -r (Join-Path $RepoRoot "requirements.txt")

Push-Location (Join-Path $RepoRoot "frontend")
try {
    & npm ci
    & npm run build
} finally {
    Pop-Location
}

New-Item -ItemType Directory -Force -Path $DataRoot | Out-Null
if (-not (Test-Path -LiteralPath (Join-Path $AceRoot ".git"))) {
    & git clone --depth 1 https://github.com/ace-step/ACE-Step-1.5.git $AceRoot
}

& $AppPython -m pip install uv
Push-Location $AceRoot
try {
    & $AppPython -m uv sync
    if (-not $SkipModelDownload) {
        $env:ACESTEP_CHECKPOINTS_DIR = $CheckpointDir
        & $AppPython -m uv run acestep-download --model acestep-v15-turbo
        & $AppPython -m uv run acestep-download --model acestep-5Hz-lm-0.6B
    }
} finally {
    Remove-Item Env:ACESTEP_CHECKPOINTS_DIR -ErrorAction SilentlyContinue
    Pop-Location
}

if (-not (Test-Path -LiteralPath $AcePython)) {
    throw "ACE-Step's isolated runtime was not created."
}
& $AcePython -c "import torch; assert torch.cuda.is_available(); print('ACE worker CUDA:', torch.__version__, torch.cuda.get_device_name(0))"
if ($LASTEXITCODE -ne 0) {
    throw "The isolated ACE-Step CUDA runtime failed verification."
}

Write-Host ""
Write-Host "Fidget setup is complete." -ForegroundColor Green
Write-Host "Model: ACE-Step 1.5 Turbo INT8 + 0.6B LM (bounded isolated worker)."
Write-Host "Run .\run.ps1 to open the desktop studio."
