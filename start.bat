@echo off
REM CodePuppy DAR - Start Script
echo Starting CodePuppy DAR Dashboard...
echo.

REM Activate venv
call .venv\Scripts\activate.bat

REM Run the app
echo Starting FastAPI server on http://localhost:8000
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

pause
