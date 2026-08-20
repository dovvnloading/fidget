$ErrorActionPreference = "Stop"
$RepoRoot = $PSScriptRoot
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "Fidget is not installed yet. Run .\setup.ps1 first."
}
& $Python (Join-Path $RepoRoot "fidget\fidget.py")

