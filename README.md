# 🐂 RAIMA Markets Dashboard — Complete Documentation

## Project Structure

```
trading_dashboard/
├── backend/
│   ├── main.py              ← FastAPI app (all routes + feed)
│   ├── instruments.py       ← Upstox API helpers (expiry, option chain)
│   ├── instrument_keys.py   ← Correct ISIN-based NSE_EQ keys for all stocks
│   ├── loc_engine.py        ← 25-formula LOC calculator (auto, dynamic)
│   ├── mock_feed.py         ← Simulated feed for development
│   └── proto_decoder.py     ← Upstox V3 Protobuf binary decoder
├── frontend/
│   └── index.html           ← Full SPA dashboard
├── .env                     ← Credentials (never commit)
├── render.yaml              ← Render.com deployment config
└── requirements.txt
```

---

## Quick Start

```bash
# Development (mock data, no credentials needed)
bash start.sh

# Windows
start_mock.bat      # mock mode
start_live.bat      # live mode

# Manual
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Default password: `raima2024`

---

## Environment Variables (.env)

```env
UPSTOX_API_KEY=your_api_key
UPSTOX_API_SECRET=your_api_secret
UPSTOX_ACCESS_TOKEN=your_access_token
UPSTOX_REDIRECT_URI=https://your-app.onrender.com/auth/callback
DASHBOARD_PASSWORD=raima2024
MOCK_MODE=false
```

---

## Upstox API Endpoints Used

### 1. OAuth Authentication
```
GET  https://api.upstox.com/v2/login/authorization/dialog
     ?client_id=YOUR_API_KEY
     &redirect_uri=YOUR_REDIRECT_URI
     &response_type=code

POST https://api.upstox.com/v2/login/authorization/token
Headers: Accept: application/json
Body: code=AUTH_CODE
      client_id=API_KEY
      client_secret=API_SECRET
      redirect_uri=REDIRECT_URI
      grant_type=authorization_code

Response:
{
  "access_token": "eyJ...",
  "token_type": "Bearer",
  "expires_in": 86400
}
```

### 2. Option Expiry Dates
```
GET https://api.upstox.com/v2/option/contract
    ?instrument_key=NSE_INDEX|Nifty 50
Headers: Authorization: Bearer {token}

Response:
{
  "status": "success",
  "data": ["2026-03-27","2026-04-03","2026-04-10","2026-04-24",...]
}

Note: Returns empty on weekends/holidays → system auto-calculates fallback expiries
```

### 3. Option Chain (CE + PE OHLC)
```
GET https://api.upstox.com/v2/option/chain
    ?instrument_key=NSE_INDEX|Nifty 50
    &expiry_date=2026-03-27
Headers: Authorization: Bearer {token}

Response:
{
  "status": "success",
  "data": [
    {
      "strike_price": 22550,
      "underlying_key": "NSE_INDEX|Nifty 50",
      "underlying_spot_price": 22641.80,
      "call_options": {
        "instrument_key": "NSE_FO|12345",
        "market_data": {
          "ltp": 120.5,
          "prev_close_price": 98.3,
          "high_price": 145.0,
          "low_price": 85.0,
          "oi": 25000,
          "volume": 150000
        },
        "option_greeks": {"iv": 12.5, "delta": 0.45, "theta": -8.2}
      },
      "put_options": { ... same structure ... }
    }
  ]
}
```

### 4. Market Quote OHLC (Stocks / MCX)
```
GET https://api.upstox.com/v2/market-quote/ohlc
    ?instrument_key=NSE_EQ|INE002A01018,NSE_EQ|INE467B01029
    &interval=1d
Headers: Authorization: Bearer {token}

Response:
{
  "status": "success",
  "data": {
    "NSE_EQ:RELIANCE": {
      "ohlc": {"open":1410.0,"high":1432.5,"low":1398.0,"close":1407.2},
      "last_price": 1407.2,
      "instrument_token": "NSE_EQ|INE002A01018"
    }
  }
}

Note: Use ISIN-based keys (NSE_EQ|INE002A01018) NOT symbol-based (NSE_EQ|RELIANCE)
```

### 5. Full Market Quote
```
GET https://api.upstox.com/v2/market-quote/quotes
    ?instrument_key=NSE_EQ|INE002A01018
Headers: Authorization: Bearer {token}

Response:
{
  "status": "success",
  "data": {
    "NSE_EQ:RELIANCE": {
      "ohlc": {"open":1410,"high":1432,"low":1398,"close":1407},
      "depth": {"buy":[...],"sell":[...]},
      "last_price": 1407.2,
      "volume": 4500000
    }
  }
}
```

### 6. WebSocket Feed V3 (Live Ticks)
```
WSS wss://api.upstox.com/v3/feed/market-data-feed
Headers: Authorization: Bearer {token}
         Accept: */*

Subscribe message (send as binary):
{
  "guid": "unique_id",
  "method": "sub",
  "data": {
    "mode": "full",
    "instrumentKeys": ["NSE_INDEX|Nifty 50","NSE_EQ|INE002A01018"]
  }
}

Modes:
  "ltpc"  → LTP + Close only (lightweight)
  "full"  → OHLC + market depth + option greeks
  "full_d30" → Full + 30-level depth (Upstox Plus)

Response (binary Protobuf → decoded to JSON):
// INDEX tick:
{
  "type": "live_feed",
  "feeds": {
    "NSE_INDEX|Nifty 50": {
      "ltpc": {"ltp":22641.80,"ltt":"1748000000000","cp":23114.50}
    }
  },
  "currentTs": "1748000123456"
}

// STOCK tick (full mode):
{
  "type": "live_feed",
  "feeds": {
    "NSE_EQ|INE002A01018": {
      "ltpc": {"ltp":1407.2,"cp":1398.5},
      "efeed": {"atp":1405.0,"uc":1500.0,"lc":1300.0,"high":1432.5,"low":1398.0}
    }
  }
}

// Market status (first message after connect):
{
  "type": "market_info",
  "marketInfo": {
    "segmentStatus": {
      "NSE_EQ":"NORMAL_OPEN","NSE_FO":"NORMAL_OPEN",
      "BSE_EQ":"NORMAL_OPEN","MCX_FO":"NORMAL_OPEN"
    }
  }
}
```

---

## Instrument Key Formats

| Type | Format | Example |
|------|--------|---------|
| NSE Index | `NSE_INDEX\|Name` | `NSE_INDEX\|Nifty 50` |
| BSE Index | `BSE_INDEX\|Name` | `BSE_INDEX\|SENSEX` |
| NSE Stock | `NSE_EQ\|ISIN` | `NSE_EQ\|INE002A01018` |
| NSE FO | `NSE_FO\|token` | `NSE_FO\|51059` |
| MCX Futures | `MCX_FO\|SYMYYMONfut` | `MCX_FO\|CRUDEOIL26MARFUT` |
| BSE Options | `BFO\|token` | `BFO\|123456` |

**Important:** NSE Equity stocks use ISIN codes, not trading symbols.
`NSE_EQ|RELIANCE` ❌ Wrong
`NSE_EQ|INE002A01018` ✅ Correct

---

## Our Dashboard API Endpoints

### Auth
```
POST /auth/login
Body: {"password": "raima2024"}
Response: {"status":"ok","token":"sess_1234567890"}

GET  /auth/upstox/login       → Redirect to Upstox OAuth
GET  /auth/callback?code=...  → OAuth callback (auto)
POST /auth/token
Body: {"access_token": "eyJ..."}
Response: {"status":"ok","message":"Feed starting..."}
```

### Market Data
```
GET /api/market-data
Response: {
  "market_data": {
    "NSE_INDEX|Nifty 50": {
      "ltpc": {"ltp":22641,"cp":23114},
      "efeed": {"high":22900,"low":22200},
      "ts": "1748000000000"
    }
  },
  "market_status": {"NSE_EQ":"NORMAL_OPEN",...},
  "timestamp": 1748000000000,
  "mode": "live"
}
```

### LOC Analysis
```
GET /api/loc-all
Response: {
  "NIFTY": {"ltp":22641,"bop":22580,"cep":22800,"pep":22360,
             "ul":22820,"ll":22310,"zone":"WAIT","direction":"DOWN",...},
  "BANKNIFTY": {...},
  ...
}

GET /api/loc/NIFTY
Response: {
  "ltp":22641.80,"cp":23114.50,"change":-472.70,"pct":-2.05,
  "bop":22640.9,"cep":22640.9,"pep":22640.9,"ul":22663.5,"ll":22618.3,
  "ful":22663.5,"fll":22618.3,"ful_diff":22.6,"fll_diff":-22.6,
  "dsl":0,"dsp":0,"call_move":0,"put_move":0,
  "call_cp":0,"put_cp":0,"call_cp_diff":0,"put_cp_diff":0,
  "zone":"WAIT","direction":"DOWN","distance":0,
  "ce_strike":22550,"pe_strike":22750,
  "ce_ltp":120.5,"pe_ltp":145.2,"ce_iv":12.5,"pe_iv":13.1,
  "expiry":"2026-03-27","symbol":"NIFTY"
}

GET /api/loc-history/NIFTY
Response: {
  "symbol":"NIFTY",
  "history":[
    {"ts":1748000000000,"ltp":22641,"bop":22580,"cep":22800,
     "pep":22360,"ul":22820,"ll":22310,"zone":"WAIT","direction":"DOWN"},
    ...
  ]
}
```

### Expiry Management
```
GET /api/expiry/NIFTY
Response: {
  "all":["2026-03-27","2026-04-03","2026-04-10","2026-04-24"],
  "default":"2026-03-27",
  "current_week":"2026-03-27",
  "next_week":"2026-04-03",
  "far_week":"2026-04-10"
}

POST /api/expiry/NIFTY
Body: {"expiry":"2026-04-03"}
Response: {"status":"ok","symbol":"NIFTY","expiry":"2026-04-03"}
```

### Debug
```
GET /api/debug/chain/NIFTY
Response: {
  "symbol":"NIFTY","expiry":"2026-03-27",
  "spot_ltp":22641,"last_atm":22650,
  "ce_strike":22550,"ce_ltp":120.5,"ce_key":"NSE_FO|51234",
  "pe_strike":22750,"pe_ltp":145.2,"pe_key":"NSE_FO|51235",
  "chain_size":150,"loc":{...}
}

GET /api/status
Response: {
  "auth":true,"feed_connected":true,"instruments":125,
  "frames":4521,"decoded":4521,"mode":"live",
  "option_keys":18,"expiry_loaded":["NIFTY","BANKNIFTY",...]
}
```

### OHLC Chart Data
```
GET /api/ohlc/NSE_INDEX|Nifty 50
Response: {
  "key":"NSE_INDEX|Nifty 50",
  "candles":[
    {"t":1748000000000,"o":22800,"h":22900,"l":22200,"c":22641,"v":125},
    ...
  ]
}
```

### Watchlist
```
GET  /api/watchlist
POST /api/watchlist
Body: {"name":"My List","keys":["NSE_EQ|INE002A01018","NSE_INDEX|Nifty 50"]}
DELETE /api/watchlist/My List
```

### WebSocket (Browser)
```
WSS ws://localhost:8000/ws/feed  (local)
WSS wss://your-app.onrender.com/ws/feed  (production)

Messages received:
// On connect:
{"type":"snapshot","market_data":{...},"loc_results":{...},"expiry_cache":{...},"mode":"live"}

// Live tick:
{"type":"live_feed","feeds":{"NSE_INDEX|Nifty 50":{"ltpc":{"ltp":22641,"cp":23114}}},"currentTs":"..."}

// LOC update (after each spot tick):
{"type":"loc_update","symbol":"NIFTY","spot_key":"NSE_INDEX|Nifty 50","loc":{...}}

// Market segments:
{"type":"market_info","marketInfo":{"segmentStatus":{"NSE_EQ":"NORMAL_OPEN",...}}}

// Expiry loaded:
{"type":"expiry_update","expiry_cache":{"NIFTY":{...},...}}

// Keep-alive:
{"type":"ping","ts":1748000000000}
```

---

## LOC Formulas Reference (All 25)

| # | Name | Formula |
|---|------|---------|
| 1 | CEH/SH | Max(CE High, CE Close) / Max(Spot High, Spot Close) |
| 2 | CEL/SL | Min(CE Low, CE Close) / Min(Spot Low, Spot Close) |
| 3 | PEH/SL | Max(PE High, PE Close) / Min(Spot Low, Spot Close) |
| 4 | PEL/SH | Min(PE Low, PE Close) / Max(Spot High, Spot Close) |
| 5 | C-CE/S | CE LTP / Spot LTP |
| 6 | C-PE/S | PE LTP / Spot LTP |
| 7 | Call Move | CEH/SH − CEL/SL |
| 8 | Put Move | PEH/SL − PEL/SH |
| 9 | Call CP | Call Move / 2 |
| 10 | Put CP | Put Move / 2 |
| 11 | Call CP Diff (AB) | C-CE/S − Call CP |
| 12 | Put CP Diff (AC) | C-PE/S − Put CP |
| 13 | Different | Put Move − Call Move |
| 14 | Zone | CALL / PUT / WAIT based on LTP vs BOP/CEP/PEP |
| 15 | DSL | IFS(AB>0,AC<0→\|AB\|+\|AC\|; AB<0,AC>0→\|AB\|+\|AC\|; ...) |
| 16 | DSP | DSL × Spot LTP |
| 17 | BOP | IF(AB<AC→LTP+DSP; AB>AC→LTP−AC; else LTP) |
| 18 | CEP | IF(AB<0→LTP+\|AB\|×LTP; AB>0→LTP−\|AB\|×LTP; else LTP) |
| 19 | PEP | IF(AC<0→LTP−\|AC\|×LTP; AC>0→LTP+\|AC\|×LTP; else LTP) |
| 20 | FUL | BOP × 1.001 |
| 21 | FLL | BOP × 0.999 |
| 22 | FUL Diff | FUL − CEP |
| 23 | FLL Diff | FLL − PEP |
| 24 | UL | LTP + FUL Diff |
| 25 | LL | LTP + FLL Diff |

**ITM-2 Auto-Calculation:**
- CE ITM-2 = ATM − 2 × step  (e.g., NIFTY step=50, ATM=22650 → CE=22550)
- PE ITM-2 = ATM + 2 × step  (→ PE=22750)
- Auto-updates when spot price crosses ATM boundary

---

## Deploy on Render.com

```
Root Directory: (empty)
Build Command:  pip install -r requirements.txt
Start Command:  uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

Environment Variables in Render dashboard:
- `UPSTOX_API_KEY`
- `UPSTOX_API_SECRET`
- `UPSTOX_ACCESS_TOKEN`
- `UPSTOX_REDIRECT_URI` = `https://YOUR-APP.onrender.com/auth/callback`
- `DASHBOARD_PASSWORD` = `your_password`
- `MOCK_MODE` = `false`

---

## Known Issues & Solutions

| Issue | Cause | Fix |
|-------|-------|-----|
| Expiry shows "Loading..." | Weekend/holiday — Upstox API returns empty | System auto-calculates Thursday expiries |
| CE/PE = 0 | Option chain not yet loaded | Wait 5–10s after token set; check `/api/debug/chain/NIFTY` |
| Stocks = 0 | Wrong instrument key format | Using ISIN-based keys (INE002A01018) now |
| MCX = 0 | Wrong contract month | Keys auto-generate for current month |
| WS shows wss:// error | HTTP vs HTTPS mismatch | Auto-detects protocol (wss on Render, ws local) |
