@echo off
title Unloader Server (Port 8060)
color 0E

echo ========================================
echo   UNLOADER SERVER - Port 8060
echo ========================================
echo.
echo Data Source:    BigQuery DAR_DELIVERIES_CACHE
echo Cache:          L:\Engineering\DAR Docktag Cards\cache_data_unloader
echo Door Range:     430-450 (default)
echo.
echo Background:     Cache updates every 10 minutes
echo.

cd /d "%~dp0"

REM Activate virtual environment
echo [SERVER] Activating virtual environment...
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
    echo [OK] Virtual environment activated
) else (
    echo [ERROR] No .venv found!
    echo Run RUN.bat first to set up the main ACL app
    pause
    exit /b 1
)

echo.
echo Starting unloader server...
echo.
echo Server UI:      http://localhost:8060
echo Client UI:      http://localhost:8061
echo.

python scripts\unloader_server.py

if errorlevel 1 (
    echo.
    echo [ERROR] Server failed to start!
    echo.
    pause
)
