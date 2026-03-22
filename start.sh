#!/usr/bin/env bash
# ── Local development only ──
# Render uses render.yaml startCommand directly, NOT this script

set -e
cd "$(dirname "$0")"

echo "=================================================="
echo "  Trading Dashboard  -  Local Dev"
echo "=================================================="

# Create venv if needed
if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  python -m venv .venv 2>/dev/null || python3 -m venv .venv
fi

# Activate (Windows or Unix)
if [ -f ".venv/Scripts/activate" ]; then
  source .venv/Scripts/activate
elif [ -f ".venv/bin/activate" ]; then
  source .venv/bin/activate
fi

pip install -q -r requirements.txt

# Check credentials
if grep -q "your_api_key_here" .env 2>/dev/null || [ ! -f ".env" ]; then
  echo "No credentials → MOCK mode"
  export MOCK_MODE=true
else
  echo "Credentials found → LIVE mode"
  export MOCK_MODE=false
fi

echo "Starting at http://localhost:8000"
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
