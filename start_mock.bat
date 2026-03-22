@echo off
cd /d "%~dp0"
echo Trading Dashboard - MOCK MODE
if not exist ".venv" python -m venv .venv
call .venv\Scripts\activate.bat
pip install -q -r requirements.txt
set MOCK_MODE=true
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
pause
