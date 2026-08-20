<#
.SYNOPSIS
    Builds Fidget into a distributable Windows application.

.DESCRIPTION
    Builds the React interface, freezes the Python app with PyInstaller, then
    optionally code-signs the executable and packages everything into a zip.

.PARAMETER Version
    Release version, used to name the archive. Defaults to 1.0.0.

.PARAMETER Sign
    Sign the executable with Azure Trusted Signing. Requires the Trusted
    Signing dlib and the AZURE_* environment variables described in
    packaging/SIGNING.md.

.EXAMPLE
    .\packaging\build.ps1
    .\packaging\build.ps1 -Version 1.1.0 -Sign
#>
[CmdletBinding()]
param(
    [string]$Version = "1.0.0",
    [switch]$Sign
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$BuildDir = Join-Path $RepoRoot "build"
$DistDir = Join-Path $BuildDir "dist"
$AppDir = Join-Path $DistDir "Fidget"
$Exe = Join-Path $AppDir "Fidget.exe"

if (-not (Test-Path $Python)) {
    throw "Fidget is not set up yet. Run .\setup.ps1 first."
}

Write-Host "==> Building the interface" -ForegroundColor Cyan
Push-Location (Join-Path $RepoRoot "frontend")
try {
    & npm run build
    if ($LASTEXITCODE -ne 0) { throw "The frontend build failed." }
} finally {
    Pop-Location
}

Write-Host "==> Freezing the application" -ForegroundColor Cyan
& $Python -m PyInstaller (Join-Path $PSScriptRoot "fidget.spec") `
    --noconfirm `
    --distpath $DistDir `
    --workpath (Join-Path $BuildDir "work")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed." }
if (-not (Test-Path $Exe)) { throw "The build did not produce Fidget.exe." }

if ($Sign) {
    Write-Host "==> Signing" -ForegroundColor Cyan
    $required = @("AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET",
                  "TRUSTED_SIGNING_ENDPOINT", "TRUSTED_SIGNING_ACCOUNT",
                  "TRUSTED_SIGNING_PROFILE", "TRUSTED_SIGNING_DLIB")
    $missing = $required | Where-Object { -not (Get-Item "Env:$_" -ErrorAction SilentlyContinue) }
    if ($missing) {
        throw "Signing needs these environment variables: $($missing -join ', '). See packaging/SIGNING.md."
    }

    $signtool = Get-ChildItem "${env:ProgramFiles(x86)}\Windows Kits\10\bin\*\x64\signtool.exe" |
        Sort-Object FullName -Descending | Select-Object -First 1
    if (-not $signtool) { throw "signtool.exe not found. Install the Windows SDK." }

    # Metadata file the Trusted Signing dlib reads to locate the certificate profile.
    $metadata = Join-Path $BuildDir "trusted-signing.json"
    @{
        Endpoint               = $env:TRUSTED_SIGNING_ENDPOINT
        CodeSigningAccountName = $env:TRUSTED_SIGNING_ACCOUNT
        CertificateProfileName = $env:TRUSTED_SIGNING_PROFILE
    } | ConvertTo-Json | Set-Content -Path $metadata -Encoding utf8

    & $signtool.FullName sign `
        /v /fd SHA256 /tr "http://timestamp.acs.microsoft.com" /td SHA256 `
        /dlib $env:TRUSTED_SIGNING_DLIB /dmdf $metadata `
        $Exe
    if ($LASTEXITCODE -ne 0) { throw "Signing failed." }

    & $signtool.FullName verify /pa /v $Exe
    if ($LASTEXITCODE -ne 0) { throw "The signature did not verify." }
    Write-Host "    signed and verified" -ForegroundColor Green
} else {
    Write-Host "==> Skipping signing (pass -Sign to enable)" -ForegroundColor DarkYellow
}

Write-Host "==> Packaging" -ForegroundColor Cyan
$archive = Join-Path $DistDir "Fidget-$Version-windows-x64.zip"
if (Test-Path $archive) { Remove-Item $archive -Force }
Compress-Archive -Path $AppDir -DestinationPath $archive -CompressionLevel Optimal

$size = "{0:N1} MB" -f ((Get-Item $archive).Length / 1MB)
$hash = (Get-FileHash $archive -Algorithm SHA256).Hash

Write-Host ""
Write-Host "Build complete" -ForegroundColor Green
Write-Host "  archive : $archive"
Write-Host "  size    : $size"
Write-Host "  sha256  : $hash"
