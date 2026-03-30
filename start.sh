#!/bin/bash
echo "RAIMA Markets v5"
cd "$(dirname "$0")"
source .venv/bin/activate 2>/dev/null || source .venv/Scripts/activate 2>/dev/null || true

# Check if .env exists
if [ ! -f .env ]; then cp .env.example .env 2>/dev/null || true; fi

# Detect mode
if grep -q "UPSTOX_ACCESS_TOKEN=." .env 2>/dev/null && ! grep -q "MOCK_MODE=true" .env; then
  echo "Credentials found → LIVE mode"
else
  echo "No token → MOCK mode"
  export MOCK_MODE=true
fi

echo "Starting backend at http://localhost:8000"
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
