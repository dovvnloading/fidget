[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = "High")]
param(
    [switch]$PermanentlyDelete
)

$ErrorActionPreference = "Stop"

# Deliberately use a fixed allowlist. Do not replace these with globs or a computed root.
$ObsoletePaths = @(
    "D:\AI\fidget\models\ace-step-1.5",
    "D:\AI\fidget\models\musicgen-small",
    "D:\AI\fidget\musicgen-runtime",
    "D:\AI\fidget\ACE-Step-1.5\checkpoints\acestep-5Hz-lm-1.7B"
)

$ActivePaths = @(
    "D:\AI\fidget\ACE-Step-1.5\.venv",
    "D:\AI\fidget\ACE-Step-1.5\checkpoints\acestep-v15-turbo",
    "D:\AI\fidget\ACE-Step-1.5\checkpoints\acestep-5Hz-lm-0.6B",
    "D:\AI\fidget\ACE-Step-1.5\checkpoints\Qwen3-Embedding-0.6B",
    "D:\AI\fidget\ACE-Step-1.5\checkpoints\vae"
)

function Get-NormalizedPath([string]$Path) {
    return [System.IO.Path]::GetFullPath($Path).TrimEnd("\")
}

$Allowed = @{}
foreach ($Path in $ObsoletePaths) {
    $Allowed[(Get-NormalizedPath $Path).ToLowerInvariant()] = $true
}

foreach ($Path in $ActivePaths) {
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        throw "Required active ACE-Step path is missing; refusing cleanup: $Path"
    }
}

$Inventory = foreach ($Path in $ObsoletePaths) {
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        continue
    }
    $Resolved = (Resolve-Path -LiteralPath $Path).Path
    $Normalized = Get-NormalizedPath $Resolved
    if (-not $Allowed.ContainsKey($Normalized.ToLowerInvariant())) {
        throw "Resolved path is outside the exact cleanup allowlist: $Resolved"
    }
    $Bytes = (
        Get-ChildItem -LiteralPath $Resolved -File -Recurse -Force |
            Measure-Object -Property Length -Sum
    ).Sum
    [pscustomobject]@{
        Path = $Resolved
        GiB = [math]::Round($Bytes / 1GB, 3)
    }
}

if (-not $Inventory) {
    Write-Host "No obsolete Fidget model data remains." -ForegroundColor Green
    exit 0
}

$Inventory | Format-Table -AutoSize
$TotalGiB = [math]::Round(($Inventory | Measure-Object -Property GiB -Sum).Sum, 3)
Write-Host "Obsolete data identified: $TotalGiB GiB"

if (-not $PermanentlyDelete) {
    Write-Host "Inventory only. Pass -PermanentlyDelete to request deletion."
    exit 0
}

foreach ($Item in $Inventory) {
    if ($PSCmdlet.ShouldProcess($Item.Path, "Permanently delete obsolete Fidget model data")) {
        Remove-Item -LiteralPath $Item.Path -Recurse -Force
        Write-Host "Deleted: $($Item.Path)"
    }
}

foreach ($Path in $ActivePaths) {
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        throw "Cleanup postcondition failed; active path is missing: $Path"
    }
}

$Remaining = @($ObsoletePaths | Where-Object { Test-Path -LiteralPath $_ })
if ($Remaining.Count -gt 0) {
    throw "Cleanup incomplete; obsolete paths remain: $($Remaining -join ', ')"
}

Write-Host "Obsolete model cleanup complete. Active ACE-Step profile verified." -ForegroundColor Green
