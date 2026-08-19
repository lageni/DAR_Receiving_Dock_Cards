@echo off
title Unloader Client (Port 8061)
color 0A

echo ========================================
echo   UNLOADER CLIENT - Port 8061
echo ========================================
echo.
echo Mode:           READ-ONLY VIEWER
echo Cache Source:   L:\Engineering\DAR Docktag Cards\cache_data_unloader
echo Door Range:     430-450 (default)
echo.
echo Server should be running on port 8060 to populate cache
echo.

cd /d "%~dp0"

REM Activate virtual environment
echo [CLIENT] Activating virtual environment...
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
echo [CLIENT] Checking GCP authentication (BigQuery)...
python scripts\setup_gcp_auth.py --check
if errorlevel 1 (
    echo [WARN] GCP not authenticated - running setup now...
    python scripts\setup_gcp_auth.py
)

echo.
echo Starting unloader client...
echo.
echo Opening browser: http://localhost:8061
echo.

start http://localhost:8061

python scripts\unloader_client.py

if errorlevel 1 (
    echo.
    echo [ERROR] Client failed to start!
    echo.
    pause
)
