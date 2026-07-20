@echo off
REM CodePuppyDAR - Master Startup & Setup Script
REM Handles first-time setup and daily server startup

setlocal enabledelayedexpansion
cd /d "%~dp0"

echo.
echo ============================================================
echo  CodePuppyDAR - Startup & Setup
echo ============================================================
echo.

REM Check if this is first run
if not exist "read_rates.db" (
    echo [FIRST-TIME SETUP DETECTED]
    echo.
    goto setup
) else (
    goto startup
)

:setup
echo ============================================================
echo  FIRST-TIME SETUP
echo ============================================================
echo.

REM Step 1: Check Python
echo [1/5] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found!
    echo Please install Python 3.10+ from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation
    pause
    exit /b 1
)
for /f "tokens=2" %%i in ('python --version') do set PYTHON_VERSION=%%i
echo [OK] Python %PYTHON_VERSION% found

REM Step 2: Sync dependencies from Walmart Artifactory
echo.
echo [2/5] Syncing dependencies from Walmart Artifactory...
echo       Index: https://pypi.ci.artifacts.walmart.com/artifactory/api/pypi/external-pypi/simple
uv sync
if errorlevel 1 (
    echo ERROR: Failed to sync dependencies
    echo Make sure you are connected to Walmart VPN or Eagle WiFi
    pause
    exit /b 1
)
echo [OK] Dependencies synced - see DEPENDENCIES.md for full list

REM Step 3: Check .env
echo.
echo [3/4] Checking .env configuration...
if not exist ".env" (
    echo WARNING: .env file not found!
    echo Creating template .env file...
    
    (
        echo # MDM Item API Credentials
        echo MDM_API_KEY=PASTE_YOUR_KEY_HERE
        echo MDM_FACILITY_NUM=6068
        echo MDM_FACILITY_COUNTRY_CODE=US
        echo MDM_WMT_USERID=mdm-ui
    ) > .env
    
    echo [WARN] .env created - please fill in your MDM_API_KEY
    echo Opening .env in notepad for editing...
    notepad .env
) else (
    echo [OK] .env file found
)

REM Step 4: Initialize database
echo.
echo [4/4] Initializing SQLite database...
python db.py
if errorlevel 1 (
    echo ERROR: Database initialization failed
    pause
    exit /b 1
)
echo [OK] Database initialized

REM Verify connectivity (informational)
echo.
echo [INFO] Testing network connectivity...
ping -n 1 uwms-item.prod.us.walmart.net >nul 2>&1
if errorlevel 1 (
    echo WARNING: Cannot reach MDM API endpoint
    echo The server may still work if behind a proxy
) else (
    echo [OK] MDM API endpoint reachable
)

REM Test BigQuery (optional)
echo.
echo [INFO] BigQuery connection status (optional)...
echo If your GCS_PROJECT_ID, GCS_DATASET_ID, GCS_TABLE_ID are set in .env, they will be tested
echo Otherwise, you can configure this in the admin debug page
echo.
python -c "from gcs_sync import test_gcs_connection; import os; proj=os.getenv('GCS_PROJECT_ID'); data=os.getenv('GCS_DATASET_ID'); tbl=os.getenv('GCS_TABLE_ID'); result = test_gcs_connection(proj, data, tbl) if proj and data and tbl else {'status': 'skipped', 'message': 'No GCS credentials in .env'}; print(f\"BigQuery Test: {result.get('status')}\" if result.get('status') != 'skipped' else 'BigQuery test skipped (configure in admin debug page)') except Exception as e: print(f'BigQuery test skipped: {e}')" 2>nul || echo [INFO] BigQuery test skipped

echo.
echo ============================================================
echo  SETUP COMPLETE - Starting Server
echo ============================================================
echo.

:startup
REM Activate virtual environment first
echo [SERVER] Activating virtual environment...
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
    echo [OK] Virtual environment activated
) else (
    echo [WARN] No .venv found - creating one now...
    python -m venv .venv
    call .venv\Scripts\activate.bat
    echo [OK] Virtual environment created and activated
    echo [INFO] Installing dependencies...
    pip install -r requirements.txt --index-url https://pypi.ci.artifacts.walmart.com/artifactory/api/pypi/external-pypi/simple --allow-insecure-host pypi.ci.artifacts.walmart.com
)

REM Start the server
echo.
echo [SERVER] Starting CodePuppyDAR...
echo.
echo Local Access:        http://localhost:8050
echo Network Access:       http://%COMPUTERNAME%:8050
echo Admin Debug Page:    http://localhost:8050/admin/debug
echo.
echo Press Ctrl+C to stop the server
echo.

REM Try to open browser automatically
start http://localhost:8050

REM Run main.py using activated venv Python
python main.py

REM If we get here, server was stopped
echo.
echo Server stopped.
pause
