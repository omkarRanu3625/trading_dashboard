@echo off
cd /d "%~dp0"
echo Trading Dashboard - LIVE MODE
if not exist ".venv" python -m venv .venv
call .venv\Scripts\activate.bat
pip install -q -r requirements.txt
set MOCK_MODE=false
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
pause
