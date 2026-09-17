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

# Auto-locate dumpbin from Visual Studio if not in PATH
$Dumpbin = Get-Command "dumpbin.exe" -ErrorAction SilentlyContinue
if (-not $Dumpbin) {
    $vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
    if (Test-Path $vswhere) {
        $vsPath = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
        if ($vsPath) {
            $dumpbinItem = Get-ChildItem -Path "$vsPath\VC\Tools\MSVC" -Filter "dumpbin.exe" -Recurse -ErrorAction SilentlyContinue | Where-Object { $_.FullName -match "Hostx64\\x64" } | Select-Object -First 1
            if ($dumpbinItem) {
                $env:PATH = "$($dumpbinItem.DirectoryName);$env:PATH"
                $Dumpbin = Get-Command "dumpbin.exe" -ErrorAction SilentlyContinue
            }
        }
    }
}

if ($Dumpbin) {
    Write-Host "Running dumpbin header check..." -ForegroundColor Green
    & dumpbin /headers $TargetBinary | Select-String "subsystem version"

    Write-Host "Checking PE import table for prohibited Win10+ imports (bcryptprimitives.dll, api-ms-win-core-winrt, combase.dll)..." -ForegroundColor Green
    $ForbiddenImports = & dumpbin /imports $TargetBinary | Select-String -Pattern "bcryptprimitives\.dll|api-ms-win-core-winrt|ProcessPrng|combase\.dll"
    if ($ForbiddenImports) {
        Write-Host "WARNING: Found potentially incompatible imported symbols:" -ForegroundColor Red
        $ForbiddenImports | ForEach-Object { Write-Host "  $_" -ForegroundColor Red }
        exit 1
    } else {
        Write-Host "PASS: No forbidden Win10+ symbols detected in PE import table!" -ForegroundColor Green
    }
} else {
    Write-Host "dumpbin.exe not available. Reading PE header directly..." -ForegroundColor Yellow
    $bytes = [System.IO.File]::ReadAllBytes($TargetBinary)
    # e_lfanew at 0x3C
    $peOffset = [BitConverter]::ToInt32($bytes, 0x3C)
    # Check PE signature 'PE\0\0'
    if ($bytes[$peOffset] -eq 0x50 -and $bytes[$peOffset+1] -eq 0x45) {
        # Magic at peOffset + 24: 0x20B = PE32+ (64-bit)
        $magic = [BitConverter]::ToUInt16($bytes, $peOffset + 24)
        $subsystemOffset = if ($magic -eq 0x20B) { $peOffset + 24 + 44 } else { $peOffset + 24 + 44 }
        $majorSubsystem = [BitConverter]::ToUInt16($bytes, $subsystemOffset)
        $minorSubsystem = [BitConverter]::ToUInt16($bytes, $subsystemOffset + 2)
        Write-Host "PE Subsystem Version: $majorSubsystem.$minorSubsystem" -ForegroundColor Green
        if ($majorSubsystem -gt 6 -or ($majorSubsystem -eq 6 -and $minorSubsystem -gt 1)) {
            Write-Host "WARNING: Subsystem version $majorSubsystem.$minorSubsystem exceeds Windows 7 (6.1)!" -ForegroundColor Red
            exit 1
        }
        Write-Host "PASS: Subsystem version is compatible with Windows 7." -ForegroundColor Green
    }
}

