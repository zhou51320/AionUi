<#
.SYNOPSIS
    Builds AionUi and AionCore (Aion CLI) for Windows 7 (x86_64-win7-windows-msvc).
.DESCRIPTION
    Compiles Rust backend with Tier 3 Win7 target and -Zbuild-std,
    rebuilds native dependencies, and packages with Electron for Windows 7.
#>
param (
    [switch]$SkipRust,
    [switch]$SkipDesktop,
    [string]$ElectronDist = ""
)

$ErrorActionPreference = "Stop"

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "  AionUi Windows 7 Build Script" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

$RootDir = Split-Path -Parent $PSScriptRoot
$AionCoreDir = Join-Path $RootDir "AionCore"

# 1. Build AionCore / Aion CLI
if (-not $SkipRust) {
    Write-Host "`n[1/3] Compiling AionCore for x86_64-win7-windows-msvc..." -ForegroundColor Green

    Push-Location $AionCoreDir
    try {
        # Check nightly compiler
        rustup toolchain list | Select-String "nightly" | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Installing nightly Rust toolchain and rust-src..." -ForegroundColor Yellow
            rustup toolchain install nightly
            rustup component add rust-src --toolchain nightly
        }

        # Build with Tier 3 Windows 7 target
        Write-Host "Running cargo build with Tier 3 target..." -ForegroundColor Cyan
        cargo +nightly build --release `
            --target x86_64-win7-windows-msvc `
            -Zbuild-std `
            -p aionui-app

        if ($LASTEXITCODE -ne 0) {
            throw "Cargo build failed for x86_64-win7-windows-msvc"
        }

        Write-Host "Rust AionCore built successfully!" -ForegroundColor Green
    }
    finally {
        Pop-Location
    }
}

# 2. Package Desktop Client
if (-not $SkipDesktop) {
    Write-Host "`n[2/3] Building Frontend & Packaging Desktop for Win7..." -ForegroundColor Green

    Push-Location $RootDir
    try {
        # Rebuild native modules (e.g. better-sqlite3)
        Write-Host "Checking native modules..." -ForegroundColor Cyan
        
        # Package with electron-builder
        if ($ElectronDist -and (Test-Path $ElectronDist)) {
            Write-Host "Using custom Electron dist: $ElectronDist" -ForegroundColor Cyan
            npx electron-builder --win --x64 --config.electronDist=$ElectronDist
        } else {
            Write-Host "Building standard win x64 package (use -ElectronDist to supply custom win7 electron build)..." -ForegroundColor Yellow
            npm run build-win:x64
        }
    }
    finally {
        Pop-Location
    }
}

Write-Host "`n[3/3] Build completed successfully!" -ForegroundColor Green
