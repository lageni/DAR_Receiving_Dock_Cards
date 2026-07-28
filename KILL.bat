@echo off
title Kill CodePuppyDAR Processes
color 0C

echo ========================================
echo   Kill CodePuppyDAR Processes
echo ========================================
echo.
echo This will stop all processes running on:
echo   - Port 8050 (Server)
echo   - Port 8051 (Client)
echo.
pause

echo.
echo [KILL] Finding processes on port 8050...
for /f "tokens=5" %%a in ('netstat -aon ^| find ":8050" ^| find "LISTENING"') do (
    echo Found PID: %%a
    taskkill /F /PID %%a
    if errorlevel 1 (
        echo [WARN] Could not kill PID %%a
    ) else (
        echo [OK] Process %%a terminated
    )
)

echo.
echo [KILL] Finding processes on port 8051...
for /f "tokens=5" %%a in ('netstat -aon ^| find ":8051" ^| find "LISTENING"') do (
    echo Found PID: %%a
    taskkill /F /PID %%a
    if errorlevel 1 (
        echo [WARN] Could not kill PID %%a
    ) else (
        echo [OK] Process %%a terminated
    )
)

echo.
echo ========================================
echo   All processes terminated!
echo ========================================
echo.
pause
