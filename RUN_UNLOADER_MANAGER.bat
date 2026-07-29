@echo off
title Unloader Manager (Port 8062)
color 0D

echo ========================================
echo   UNLOADER MANAGER - Port 8062
echo ========================================
echo.
echo Mode:           MANAGER SUMMARY VIEW
echo Cache Source:   L:\Engineering\DAR Docktag Cards\cache_data_unloader
echo Door Range:     425-500 (default)
echo.
echo Shows:          Case distribution by door (Good/Bad/Unknown)
echo.

cd /d "%~dp0"

REM Activate virtual environment
echo [MANAGER] Activating virtual environment...
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
echo Starting unloader manager view...
echo.
echo Opening browser: http://localhost:8062
echo.

start http://localhost:8062

python scripts\unloader_manager.py

if errorlevel 1 (
    echo.
    echo [ERROR] Manager failed to start!
    echo.
    pause
)
