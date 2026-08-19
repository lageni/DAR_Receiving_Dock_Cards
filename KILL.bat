@echo off
title Kill Unloader Processes
color 0C

echo ========================================
echo   Kill Unloader Processes
echo ========================================
echo.
echo This will stop all processes running on:
echo   - Port 8060 (Unloader Server)
echo   - Port 8061 (Unloader Client)
echo   - Port 8062 (Unloader Manager)
echo.
pause

echo.
echo [KILL] Finding processes on port 8060...
for /f "tokens=5" %%a in ('netstat -aon ^| find ":8060" ^| find "LISTENING"') do (
    echo Found PID: %%a
    taskkill /F /PID %%a
    if errorlevel 1 (
        echo [WARN] Could not kill PID %%a
    ) else (
        echo [OK] Process %%a terminated
    )
)

echo.
echo [KILL] Finding processes on port 8061...
for /f "tokens=5" %%a in ('netstat -aon ^| find ":8061" ^| find "LISTENING"') do (
    echo Found PID: %%a
    taskkill /F /PID %%a
    if errorlevel 1 (
        echo [WARN] Could not kill PID %%a
    ) else (
        echo [OK] Process %%a terminated
    )
)

echo.
echo [KILL] Finding processes on port 8062...
for /f "tokens=5" %%a in ('netstat -aon ^| find ":8062" ^| find "LISTENING"') do (
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
