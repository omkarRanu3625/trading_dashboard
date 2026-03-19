#!/usr/bin/env bash
# ============================================================
# Trading Dashboard – Quick Start (Windows Git Bash / Linux / Mac)
# ============================================================
set -e

cd "$(dirname "$0")"

echo "=================================================="
echo "  Trading Dashboard  -  Setup & Launch"
echo "=================================================="

# 1. Create venv if not exists
if [ ! -d ".venv" ]; then
  echo "[1/4] Creating Python virtual environment..."
  python -m venv .venv 2>/dev/null || python3 -m venv .venv
fi

# 2. Activate venv - Windows uses Scripts/, Unix uses bin/
if [ -f ".venv/Scripts/activate" ]; then
  echo "[2/4] Activating venv (Windows)..."
  source .venv/Scripts/activate
elif [ -f ".venv/bin/activate" ]; then
  echo "[2/4] Activating venv (Unix/Mac)..."
  source .venv/bin/activate
else
  echo "[WARN] venv activate not found - using system Python"
fi

# 3. Install deps
echo "[3/4] Installing dependencies..."
pip install -q -r requirements.txt

# 4. Detect mock mode
if grep -q "your_api_key_here" .env 2>/dev/null || [ ! -f ".env" ]; then
  echo ""
  echo "  No Upstox credentials - starting in MOCK mode (simulated data)"
  echo ""
  MOCK_FLAG="--mock"
else
  MOCK_FLAG=""
  echo ""
  echo "  Upstox credentials found - starting in LIVE mode"
  echo ""
fi

# 5. Launch
echo "[4/4] Server starting at http://localhost:8000"
echo ""

cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload $MOCK_FLAG "$@"
