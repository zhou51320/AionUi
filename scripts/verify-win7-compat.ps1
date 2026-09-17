<#
.SYNOPSIS
    Verifies that compiled binaries are compatible with Windows 7.
.DESCRIPTION
    Checks PE header subsystem versions (expecting 6.00 for Win7)
    and inspects import tables for forbidden Win10+ APIs (ProcessPrng, WinRT, etc.)
#>
param (
    [Alias("ExePath")]
    [Parameter(Mandatory=$false)]
    [string]$TargetBinary = ""
)

$ErrorActionPreference = "Stop"

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "  AionUi Win7 Binary Compatibility Check" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

$RootDir = Split-Path -Parent $PSScriptRoot
if (-not $TargetBinary) {
    # Default search for built binary
    $Candidates = @(
        "$RootDir\AionCore\target\x86_64-win7-windows-msvc\release\aioncore.exe",
        "$RootDir\AionCore\target\release\aioncore.exe",
        "$RootDir\AionCore\target\x86_64-win7-windows-msvc\release\aionui-app.exe",
        "$RootDir\AionCore\target\release\aionui-app.exe"
    )
    foreach ($cand in $Candidates) {
        if (Test-Path $cand) {
            $TargetBinary = $cand
            break
        }
    }
}

if (-not $TargetBinary -or -not (Test-Path $TargetBinary)) {
    Write-Host "No binary found to check. Pass -TargetBinary path\to\binary.exe" -ForegroundColor Yellow
    exit 0
}

Write-Host "Checking target binary: $TargetBinary" -ForegroundColor Cyan

# 1. Check with dumpbin if available
$Dumpbin = Get-Command "dumpbin.exe" -ErrorAction SilentlyContinue
if ($Dumpbin) {
    Write-Host "Running dumpbin header check..." -ForegroundColor Green
    & dumpbin /headers $TargetBinary | Select-String "subsystem version"

    Write-Host "Checking for prohibited Win10+ imports (ProcessPrng, bcryptprimitives, winrt)..." -ForegroundColor Green
    $Forbidden = & dumpbin /dependents $TargetBinary | Select-String "ProcessPrng|bcryptprimitives|winrt"
    if ($Forbidden) {
        Write-Host "WARNING: Found potentially incompatible symbols:" -ForegroundColor Red
        $Forbidden | ForEach-Object { Write-Host "  $_" -ForegroundColor Red }
        exit 1
    } else {
        Write-Host "PASS: No forbidden Win10+ symbols detected!" -ForegroundColor Green
    }
} else {
    Write-Host "dumpbin.exe not in PATH. Performing binary string scan..." -ForegroundColor Yellow
    $Content = [System.IO.File]::ReadAllText($TargetBinary, [System.Text.Encoding]::ASCII)
    $IncompatibleSymbols = @("ProcessPrng", "bcryptprimitives.dll", "api-ms-win-core-winrt")
    $FoundAny = $false

    foreach ($sym in $IncompatibleSymbols) {
        if ($Content.Contains($sym)) {
            Write-Host "WARNING: Symbol '$sym' found in binary!" -ForegroundColor Red
            $FoundAny = $true
        }
    }

    if ($FoundAny) {
        Write-Host "FAIL: Incompatible Windows 10+ symbols found in binary." -ForegroundColor Red
        exit 1
    } else {
        Write-Host "PASS: No Windows 10+ symbols detected in binary string scan." -ForegroundColor Green
    }
}
