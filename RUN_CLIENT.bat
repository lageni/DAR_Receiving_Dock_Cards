@echo off
title ACL Viewer Client (Port 8001)
color 0E

echo ========================================
echo   ACL Freight Awareness - CLIENT
echo ========================================
echo.
echo Mode:       READ-ONLY VIEWER
echo Port:       8001
echo Cache:      L:\Engineering\DAR Docktag Cards\cache_data
echo.
echo Server should be running on port 8000 to populate cache
echo.
echo Starting client...
echo.

cd /d "%~dp0"

python client_viewer.py

if errorlevel 1 (
    echo.
    echo [ERROR] Client failed to start!
    echo.
    echo Possible causes:
    echo   - Python not found
    echo   - Missing dependencies
    echo   - Port 8001 already in use
    echo.
    pause
)
