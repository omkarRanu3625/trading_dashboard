@echo off
echo RAIMA Markets v5 - MOCK mode
cd /d "%~dp0"
call .venv\Scripts\activate.bat
set MOCK_MODE=true
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
pause
