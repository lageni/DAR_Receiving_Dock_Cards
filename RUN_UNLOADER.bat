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

REM First-time setup: create .env from template if missing
if not exist ".env" (
    echo [SETUP] No .env found - creating template...
    (
        echo # MDM Item API Credentials
        echo MDM_API_KEY=PASTE_YOUR_KEY_HERE
        echo MDM_FACILITY_NUM=6068
        echo MDM_FACILITY_COUNTRY_CODE=US
        echo MDM_WMT_USERID=mdm-ui
        echo GCS_PROJECT_ID=PASTE_YOUR_BQ_PROJECT_HERE
    ) > .env
    echo [WARN] .env created - please fill in MDM_API_KEY and GCS_PROJECT_ID
    notepad .env
)

REM Activate virtual environment, creating it on first run
echo [SERVER] Activating virtual environment...
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
    echo [OK] Virtual environment activated
) else (
    echo [SETUP] No .venv found - creating one now...
    python -m venv .venv
    call .venv\Scripts\activate.bat
    echo [OK] Virtual environment created and activated
    echo [SETUP] Installing dependencies from Walmart Artifactory...
    pip install -r requirements.txt --index-url https://pypi.ci.artifacts.walmart.com/artifactory/api/pypi/external-pypi/simple --allow-insecure-host pypi.ci.artifacts.walmart.com
    if errorlevel 1 (
        echo [ERROR] Dependency install failed - check VPN/Eagle WiFi connection
        pause
        exit /b 1
    )
    echo [OK] Dependencies installed
)

echo.
echo [SERVER] Checking GCP authentication (BigQuery)...
python scripts\setup_gcp_auth.py --check
if errorlevel 1 (
    echo [WARN] GCP not authenticated - running setup now...
    python scripts\setup_gcp_auth.py
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
