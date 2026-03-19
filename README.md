# 🐂 Trading Dashboard
**Real-time market data dashboard using FastAPI + Upstox Market Feed V3**

Inspired by LOC Calculator / Logic Trader UI with indices, commodities, scalp/positional stocks, live ticker, and market mood index.

---

## 📁 Project Structure

```
trading_dashboard/
├── backend/
│   ├── main.py           ← FastAPI app (WebSocket + REST API)
│   ├── mock_feed.py      ← Simulated market data (no credentials needed)
│   └── proto_decoder.py  ← Upstox Protobuf V3 decoder
├── frontend/
│   ├── index.html        ← Full dashboard UI (HTML/CSS/JS)
│   └── static/           ← Static assets
├── .env                  ← API credentials (edit this)
├── requirements.txt
├── start.sh              ← One-click start
└── README.md
```

---

## 🚀 Quick Start

### Option A — Mock Mode (no credentials needed)
```bash
cd trading_dashboard
bash start.sh
# Opens at http://localhost:8000
```

### Option B — Live Upstox Data
1. Edit `.env`:
```env
UPSTOX_API_KEY=your_api_key
UPSTOX_API_SECRET=your_api_secret
UPSTOX_ACCESS_TOKEN=your_access_token
```
2. Run:
```bash
bash start.sh
```

### Manual Run
```bash
pip install -r requirements.txt
cd backend

# Mock mode
python main.py --mock

# Live mode
python main.py

# Uvicorn with reload
uvicorn main:app --reload --port 8000
```

---

## 🔐 Upstox Authentication

### Getting API Credentials
1. Register at https://developer.upstox.com/
2. Create an app → get API Key and Secret
3. Set Redirect URI to: `http://localhost:8000/auth/callback`

### Getting Access Token

**Method 1 – OAuth Flow (recommended)**
```
http://localhost:8000/auth/login
```
This redirects to Upstox login → callback → feed starts automatically.

**Method 2 – Manual Token**
```bash
curl -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/json" \
  -d '{"access_token": "YOUR_TOKEN_HERE"}'
```

**Method 3 – .env File**
```env
UPSTOX_ACCESS_TOKEN=your_token_here
```
Feed starts automatically on server launch.

---

## 📡 API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Dashboard UI |
| GET | `/auth/login` | Upstox OAuth redirect |
| GET | `/auth/callback` | OAuth callback (auto) |
| POST | `/auth/token` | Set token manually |
| GET | `/api/market-data` | Current snapshot (JSON) |
| GET | `/api/status` | Feed status |
| POST | `/api/subscribe` | Subscribe new instruments |
| WS | `/ws/feed` | Live WebSocket feed |

---

## 🔌 WebSocket Protocol

**Connect:** `ws://localhost:8000/ws/feed`

**Messages received:**
```json
// Initial snapshot
{"type": "snapshot", "market_data": {...}, "market_status": {...}, "mode": "mock"}

// Live tick
{"type": "live_feed", "feeds": {"NSE_INDEX|Nifty 50": {"ltpc": {"ltp": 23170, "cp": 23500, ...}}}, "currentTs": "..."}

// Market status
{"type": "market_info", "marketInfo": {"segmentStatus": {"NSE_EQ": "NORMAL_OPEN", ...}}}

// Keep-alive
{"type": "ping", "ts": 1234567890}
```

---

## 📊 Tracked Instruments

**Indices (NSE/BSE)**
- Nifty 50, Nifty Bank, Finnifty, MidcpNifty, Sensex, Bankex

**Commodities (MCX)**
- Crude Oil, Gold, Silver, Natural Gas, Copper

**Stocks** (mock mode includes)
- Reliance, TCS, Infosys, HDFC Bank, ICICI Bank
- Dal Bharat, Tech Mahindra, Voltas, Tata Power, JSW Steel

---

## 🔧 Protobuf Setup (for Full V3 Decode)

Upstox V3 sends binary Protobuf. To decode fully:

```bash
pip install grpcio-tools

# Download proto file from Upstox docs
wget https://assets.upstox.com/feed/market-data-feed/v3/MarketDataFeed.proto

# Generate Python
python -m grpc_tools.protoc -I. --python_out=. MarketDataFeed.proto

# File MarketDataFeed_pb2.py is now auto-used by proto_decoder.py
```

---

## 📈 Dashboard Features

- ✅ Live index cards with flash animation (green/red)
- ✅ Commodity cards with icons
- ✅ Full instruments table with mini progress bars
- ✅ Scrolling bottom ticker tape
- ✅ Market segment status pills
- ✅ Market Mood Index (MMI) gauge
- ✅ Connection status indicator + tick counter
- ✅ Auth modal for token entry
- ✅ Auto-reconnect WebSocket
- ✅ Mock mode for development

---

## 📦 Dependencies

```
fastapi          — API framework
uvicorn          — ASGI server
websockets       — WebSocket client (for Upstox feed)
httpx            — Async HTTP client (OAuth token exchange)
protobuf         — Protobuf decoding
python-dotenv    — .env file loading
```
