@echo off
REM ============================================================
REM Trading Dashboard - Windows Launcher (double-click to run)
REM ============================================================
cd /d "%~dp0"

echo ==================================================
echo   Trading Dashboard - Setup and Launch
echo ==================================================

REM Create venv if needed
if not exist ".venv" (
    echo [1/4] Creating virtual environment...
    python -m venv .venv
)

REM Activate
echo [2/4] Activating virtual environment...
call .venv\Scripts\activate.bat

REM Install deps
echo [3/4] Installing dependencies...
pip install -q -r requirements.txt

REM Launch in mock mode
echo [4/4] Starting server at http://localhost:8000
echo.
echo  Open your browser to: http://localhost:8000
echo  Press Ctrl+C to stop
echo.

cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload --mock

pause
