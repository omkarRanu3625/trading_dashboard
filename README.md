# 🐂 RAIMA Markets Dashboard

Real-time Indian stock market dashboard. FastAPI + Upstox V3 Feed.

## Deploy on Render.com

### Build Command
```
pip install -r requirements.txt
```

### Start Command
```
uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

### Root Directory
*(leave empty)*

### Environment Variables (set in Render dashboard)
- UPSTOX_API_KEY
- UPSTOX_API_SECRET
- UPSTOX_ACCESS_TOKEN
- UPSTOX_REDIRECT_URI = https://YOUR-APP.onrender.com/auth/callback
- MOCK_MODE = false

## Local Run
```bash
bash start.sh        # auto-detects mock/live
bash start_mock.bat  # Windows mock
bash start_live.bat  # Windows live
```
