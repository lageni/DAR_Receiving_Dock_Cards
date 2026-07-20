@echo off
title ACL Viewer Client (Port 8051)
color 0E

echo ========================================
echo   ACL Freight Awareness - CLIENT
echo ========================================
echo.
echo Mode:       READ-ONLY VIEWER
echo Port:       8051
echo Cache:      L:\Engineering\DAR Docktag Cards\cache_data
echo.
echo Server should be running on port 8050 to populate cache
echo.

cd /d "%~dp0"

REM Activate virtual environment
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
    echo [OK] Virtual environment activated
) else (
    echo [WARN] No .venv found - using system Python
)

echo.
echo Starting client...
echo.
echo Open browser: http://localhost:8051
echo.

python client_viewer.py

if errorlevel 1 (
    echo.
    echo [ERROR] Client failed to start!
    echo.
    echo Possible causes:
    echo   - Python not found
    echo   - Missing dependencies
    echo   - Port 8051 already in use
    echo.
    pause
)
