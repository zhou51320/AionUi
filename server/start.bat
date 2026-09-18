@echo off
setlocal enabledelayedexpansion
title AionUi Server
cd /d "%~dp0"

echo ==============================================================================
echo                      AionUi Server (Windows 7 Offline)
echo ==============================================================================
echo.

set "PYTHON_EXE="
if exist "%~dp0python\python.exe" (
    set "PYTHON_EXE=%~dp0python\python.exe"
) else (
    where python >nul 2>nul
    if not errorlevel 1 (
        set "PYTHON_EXE=python"
    ) else (
        where py >nul 2>nul
        if not errorlevel 1 (
            set "PYTHON_EXE=py"
        )
    )
)

if "%PYTHON_EXE%"=="" (
    echo [ERROR] Python not found!
    echo Please install Python 3.8+ or copy Python to the python folder.
    pause
    exit /b 1
)

echo [OK] Using Python: %PYTHON_EXE%

if not exist "%~dp0aionui.db" (
    echo [AionUi] Initializing database...
    "%PYTHON_EXE%" app.py --init
)

if not exist "%~dp0uploads" (
    mkdir "%~dp0uploads" 2>nul
)

echo.
echo ------------------------------------------------------------------------------
echo  Service running at:
echo    * Local:     http://127.0.0.1:5000
echo    * Network:   http://0.0.0.0:5000
echo    * Admin:     http://127.0.0.1:5000/admin
echo    * Default:   admin / admin123
echo ------------------------------------------------------------------------------
echo  Press Ctrl+C to stop.
echo ==============================================================================
echo.

"%PYTHON_EXE%" app.py

if errorlevel 1 (
    echo.
    echo [AionUi] Server stopped with error code: %errorlevel%
)
pause
