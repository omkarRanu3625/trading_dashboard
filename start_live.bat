@echo off
REM ============================================================
REM Trading Dashboard - LIVE MODE (requires Upstox credentials in .env)
REM ============================================================
cd /d "%~dp0"

echo ==================================================
echo   Trading Dashboard - LIVE MODE
echo ==================================================
echo.
echo  Make sure you have set your credentials in .env:
echo    UPSTOX_ACCESS_TOKEN=your_token_here
echo.

if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
)

call .venv\Scripts\activate.bat
pip install -q -r requirements.txt

echo Starting LIVE server at http://localhost:8000
echo.

cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

pause
