"""
RAIMA Markets Dashboard v5 — Fully Dynamic LOC
All option data fetched automatically from Upstox.
"""
import asyncio, inspect, json, os, sys, time, struct as _struct
from pathlib import Path
from typing import Set
from urllib.parse import urlencode
import httpx, websockets
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()
USE_MOCK = os.getenv("MOCK_MODE","false").lower() in ("true","1","yes")

app = FastAPI(title="RAIMA Markets v5")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])
static_dir = Path(__file__).parent.parent / "frontend" / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

API_KEY      = os.getenv("UPSTOX_API_KEY", "8e11a453-2de7-4b87-9e02-986a0661d762")
API_SECRET   = os.getenv("UPSTOX_API_SECRET", "fuy5zne695")
REDIRECT_URI = os.getenv("UPSTOX_REDIRECT_URI", "https://trading-dashboard-15ld.onrender.com/auth/callback")
ACCESS_TOKEN = os.getenv("UPSTOX_ACCESS_TOKEN", "")
FEED_URL     = "wss://api.upstox.com/v3/feed/market-data-feed"
PASSWORD     = os.getenv("DASHBOARD_PASSWORD", "raima2024")

from .instruments import (
    SPOT_KEYS, OPTION_EXCHANGE,
    get_current_and_next_expiry, get_itm2_strikes,
    fetch_expiry_list, fetch_option_chain
)
from .loc_engine import LOCEngine

# Reverse map: spot_feed_key → symbol name
SPOT_KEY_TO_SYM = {v: k for k, v in SPOT_KEYS.items()}

# Option instrument key → (symbol, "CE"/"PE")
option_key_map: dict = {}

LOC_SYMBOLS = ["NIFTY","BANKNIFTY","FINNIFTY","MIDCPNIFTY","SENSEX","CRUDEOIL","NATURALGAS","GOLD","SILVER"]

INDEX_KEYS = [
    "NSE_INDEX|Nifty 50","NSE_INDEX|Nifty Bank","NSE_INDEX|Nifty Fin Service",
    "NSE_INDEX|NIFTY MID SELECT","NSE_INDEX|Nifty Next 50",
    "BSE_INDEX|SENSEX","BSE_INDEX|BANKEX",
]
COMMODITY_KEYS = [
    "MCX_FO|CRUDEOIL25APRFUT","MCX_FO|NATURALGAS25APRFUT",
    "MCX_FO|GOLD25APRFUT","MCX_FO|SILVER25MAYFUT",
]
FO_STOCKS = [
    "NSE_EQ|RELIANCE","NSE_EQ|TCS","NSE_EQ|HDFCBANK","NSE_EQ|INFY","NSE_EQ|ICICIBANK",
    "NSE_EQ|BHARTIARTL","NSE_EQ|SBIN","NSE_EQ|HINDUNILVR","NSE_EQ|ITC","NSE_EQ|KOTAKBANK",
    "NSE_EQ|LT","NSE_EQ|AXISBANK","NSE_EQ|ASIANPAINT","NSE_EQ|DMART","NSE_EQ|BAJFINANCE",
    "NSE_EQ|WIPRO","NSE_EQ|ULTRACEMCO","NSE_EQ|TITAN","NSE_EQ|TECHM","NSE_EQ|POWERGRID",
    "NSE_EQ|NTPC","NSE_EQ|TATAPOWER","NSE_EQ|JSWSTEEL","NSE_EQ|VOLTAS","NSE_EQ|DALBHARAT",
    "NSE_EQ|PFC","NSE_EQ|DRREDDY","NSE_EQ|SUNPHARMA","NSE_EQ|ONGC","NSE_EQ|TATACONSUM",
    "NSE_EQ|ADANIENT","NSE_EQ|ADANIPORTS","NSE_EQ|BAJAJ-AUTO","NSE_EQ|BANKBARODA",
    "NSE_EQ|BEL","NSE_EQ|BHEL","NSE_EQ|BPCL","NSE_EQ|BRITANNIA","NSE_EQ|CANBK",
    "NSE_EQ|CIPLA","NSE_EQ|COALINDIA","NSE_EQ|COFORGE","NSE_EQ|DLF","NSE_EQ|DIVISLAB",
    "NSE_EQ|EICHERMOT","NSE_EQ|FEDERALBNK","NSE_EQ|GAIL","NSE_EQ|GMRAIRPORT",
    "NSE_EQ|GRASIM","NSE_EQ|HAL","NSE_EQ|HAVELLS","NSE_EQ|HCLTECH","NSE_EQ|HDFCAMC",
    "NSE_EQ|HEROMOTOCO","NSE_EQ|HINDALCO","NSE_EQ|HINDPETRO","NSE_EQ|HINDZINC",
    "NSE_EQ|INDIGO","NSE_EQ|INDUSINDBK","NSE_EQ|INDUSTOWER","NSE_EQ|JIOFIN",
    "NSE_EQ|JSWENERGY","NSE_EQ|LUPIN","NSE_EQ|M&M","NSE_EQ|MARICO","NSE_EQ|MARUTI",
    "NSE_EQ|MOTHERSON","NSE_EQ|MUTHOOTFIN","NSE_EQ|NAUKRI","NSE_EQ|NESTLEIND",
    "NSE_EQ|NHPC","NSE_EQ|NMDC","NSE_EQ|NYKAA","NSE_EQ|OFSS","NSE_EQ|PAGEIND",
    "NSE_EQ|PAYTM","NSE_EQ|PERSISTENT","NSE_EQ|PETRONET","NSE_EQ|PIDILITIND",
    "NSE_EQ|PNB","NSE_EQ|POLYCAB","NSE_EQ|RECLTD","NSE_EQ|RVNL","NSE_EQ|SBICARD",
    "NSE_EQ|SBILIFE","NSE_EQ|SHRIRAMFIN","NSE_EQ|SIEMENS","NSE_EQ|SUZLON",
    "NSE_EQ|TATASTEEL","NSE_EQ|TATAELXSI","NSE_EQ|TATATECH","NSE_EQ|TITAN",
    "NSE_EQ|TORNTPHARM","NSE_EQ|TRENT","NSE_EQ|TVSMOTOR","NSE_EQ|UPL","NSE_EQ|VEDL",
    "NSE_EQ|YESBANK","NSE_EQ|ZYDUSLIFE",
]


# ══════════════════════════════════════════════════════════════════
#  PROTO DECODER
# ══════════════════════════════════════════════════════════════════

def _rv(b, p):
    r = 0; s = 0
    while p < len(b):
        x = b[p]; p += 1; r |= (x & 127) << s
        if not (x & 128): break
        s += 7
    return r, p

def _parse_ltpc(d):
    o = {}; i = 0
    while i < len(d):
        t = d[i]; i += 1; fn = t >> 3; wt = t & 7
        if wt == 1 and i+8 <= len(d):
            v = _struct.unpack_from('<d', d, i)[0]; i += 8
            if fn == 1: o["ltp"] = round(v, 2)
            elif fn == 4: o["cp"] = round(v, 2)
        elif wt == 0:
            v, i = _rv(d, i)
            if fn == 2: o["ltt"] = str(v)
            elif fn == 3: o["ltq"] = str(v)
        elif wt == 2: ln, i = _rv(d, i); i += ln
        elif wt == 5 and i+4 <= len(d): i += 4
        else: break
    return o

def _parse_efeed(d):
    o = {}; i = 0
    dm = {1:"atp", 2:"cp", 6:"uc", 7:"lc", 8:"high52", 9:"low52", 10:"ltp", 11:"high", 12:"low"}
    im = {3:"vtt", 4:"tbq", 5:"tsq"}
    while i < len(d):
        t = d[i]; i += 1; fn = t >> 3; wt = t & 7
        if wt == 1 and i+8 <= len(d):
            v = _struct.unpack_from('<d', d, i)[0]; i += 8
            if fn in dm: o[dm[fn]] = round(v, 2)
        elif wt == 0:
            v, i = _rv(d, i)
            if fn in im: o[im[fn]] = v
        elif wt == 2: ln, i = _rv(d, i); i += ln
        elif wt == 5 and i+4 <= len(d): i += 4
        else: break
    return o

def _parse_mf(d):
    o = {}; i = 0
    while i < len(d):
        t = d[i]; i += 1; fn = t >> 3; wt = t & 7
        if wt == 2:
            ln, i = _rv(d, i); ch = d[i:i+ln]; i += ln
            if fn == 1:
                lt = _parse_ltpc(ch)
                if lt and lt.get("ltp") and "ltpc" not in o: o["ltpc"] = lt
            elif fn == 2:
                inn = _parse_mf(ch)
                for k, v in inn.items():
                    if k not in o: o[k] = v
                    elif k == "ltpc" and isinstance(v, dict):
                        for fk, fv in v.items():
                            if fk not in o["ltpc"]: o["ltpc"][fk] = fv
            elif fn == 4:
                ef = _parse_efeed(ch)
                if ef:
                    o["efeed"] = ef
                    if "ltpc" not in o: o["ltpc"] = {}
                    lv = ef.get("ltp"); cv = ef.get("cp")
                    if lv and lv != 0: o["ltpc"]["ltp"] = lv
                    if cv and cv != 0 and "cp" not in o["ltpc"]: o["ltpc"]["cp"] = cv
        elif wt == 1 and i+8 <= len(d): i += 8
        elif wt == 0: _, i = _rv(d, i)
        elif wt == 5 and i+4 <= len(d): i += 4
        else: break
    return o

def _parse_fd(d):
    o = {}; i = 0
    while i < len(d):
        t = d[i]; i += 1; fn = t >> 3; wt = t & 7
        if wt == 2:
            ln, i = _rv(d, i); ch = d[i:i+ln]; i += ln
            if fn == 1: o["ltpc"] = _parse_ltpc(ch)
            elif fn == 2: o.update(_parse_mf(ch))
        elif wt == 0: _, i = _rv(d, i)
        elif wt == 1 and i+8 <= len(d): i += 8
        elif wt == 5 and i+4 <= len(d): i += 4
        else: break
    return o

def _parse_me(d):
    k = ""; v = {}; i = 0
    while i < len(d):
        t = d[i]; i += 1; fn = t >> 3; wt = t & 7
        if wt == 2:
            ln, i = _rv(d, i); ch = d[i:i+ln]; i += ln
            if fn == 1: k = ch.decode("utf-8", "replace")
            elif fn == 2: v = _parse_fd(ch)
        elif wt == 0: _, i = _rv(d, i)
        elif wt == 1 and i+8 <= len(d): i += 8
        elif wt == 5 and i+4 <= len(d): i += 4
        else: break
    return k, v

def _parse_mi(d):
    seg = {}; i = 0
    ST = {0:"CLOSED", 1:"NORMAL_OPEN", 2:"NORMAL_OPEN", 3:"PREOPEN", 4:"CLOSED"}
    while i < len(d):
        t = d[i]; i += 1; fn = t >> 3; wt = t & 7
        if wt == 2:
            ln, i = _rv(d, i); ch = d[i:i+ln]; i += ln
            if fn == 1:
                si = 0; sn = ""; sv = 0
                while si < len(ch):
                    st = ch[si]; si += 1; sf = st >> 3; sw = st & 7
                    if sw == 2:
                        sln, si = _rv(ch, si)
                        if sf == 1: sn = ch[si:si+sln].decode("utf-8", "replace")
                        si += sln
                    elif sw == 0: sv, si = _rv(ch, si)
                    else: break
                if sn: seg[sn] = ST.get(sv, "NORMAL_OPEN")
        elif wt == 0: _, i = _rv(d, i)
        elif wt == 1 and i+8 <= len(d): i += 8
        elif wt == 5 and i+4 <= len(d): i += 4
        else: break
    return seg

def decode_v3(raw):
    try: return json.loads(raw.decode("utf-8"))
    except: pass
    try:
        r = {"type":"unknown","feeds":{},"currentTs":str(int(time.time()*1000))}
        i = 0; mt = 0
        while i < len(raw):
            t = raw[i]; i += 1; fn = t >> 3; wt = t & 7
            if wt == 0:
                v, i = _rv(raw, i)
                if fn == 1: mt = v
                elif fn == 3: r["currentTs"] = str(v)
            elif wt == 2:
                ln, i = _rv(raw, i); ch = raw[i:i+ln]; i += ln
                if fn == 2:
                    k, v = _parse_me(ch)
                    if k and v: r["feeds"][k] = v
                elif fn == 4:
                    r["marketInfo"] = {"segmentStatus": _parse_mi(ch)}
            elif wt == 1 and i+8 <= len(raw): i += 8
            elif wt == 5 and i+4 <= len(raw): i += 4
            else: break
        if mt == 2 or r.get("marketInfo"): r["type"] = "market_info"
        elif mt == 1 or r["feeds"]: r["type"] = "live_feed"
        return r if (r["feeds"] or r.get("marketInfo")) else None
    except: return None


# ══════════════════════════════════════════════════════════════════
#  APP STATE
# ══════════════════════════════════════════════════════════════════

class AppState:
    access_token: str = ACCESS_TOKEN
    market_data:  dict = {}
    market_status: dict = {}
    ohlc_history: dict = {}
    loc_history:  dict = {}
    loc_history_last: dict = {}
    connected_clients: Set[WebSocket] = set()
    upstox_ws = None
    feed_task  = None
    chain_task = None
    frame_count: int = 0
    decode_ok:   int = 0
    sessions:    dict = {}
    expiry_cache: dict = {}
    subscribed_option_keys: set = set()

state = AppState()

loc_engine = LOCEngine()

async def on_loc_updated(symbol: str, result: dict):
    spot_key = SPOT_KEYS.get(symbol, "")
    _record_loc_history(symbol, result)
    await broadcast({"type":"loc_update","symbol":symbol,"spot_key":spot_key,"loc":result})

loc_engine.on_loc_update = on_loc_updated

for sym in LOC_SYMBOLS:
    loc_engine.register(sym)


def _update_ohlc(key, ltp, ts_ms):
    if not ltp: return
    minute = (int(ts_ms) // 60000) * 60000
    hist = state.ohlc_history.setdefault(key, [])
    if hist and hist[-1]["t"] == minute:
        c = hist[-1]; c["h"] = max(c["h"],ltp); c["l"] = min(c["l"],ltp)
        c["c"] = ltp; c["v"] = c.get("v",0)+1
    else:
        hist.append({"t":minute,"o":ltp,"h":ltp,"l":ltp,"c":ltp,"v":1})
        if len(hist) > 390: hist.pop(0)

def _record_loc_history(symbol, loc):
    if not loc or loc.get("error"): return
    now = int(time.time()//60)*60000
    if state.loc_history_last.get(symbol) == now: return
    state.loc_history_last[symbol] = now
    hist = state.loc_history.setdefault(symbol, [])
    keep = ["ltp","bop","cep","pep","ul","ll","zone","change","direction","ce_strike","pe_strike","ce_ltp","pe_ltp","ce_iv","pe_iv"]
    hist.insert(0, {"ts":int(time.time()*1000), **{k:loc[k] for k in keep if k in loc}})
    if len(hist) > 60: hist.pop()


# ══════════════════════════════════════════════════════════════════
#  EXPIRY & CHAIN MANAGEMENT
# ══════════════════════════════════════════════════════════════════

async def init_expiries():
    """Fetch expiry lists for all LOC symbols on startup."""
    if not state.access_token:
        print("[Expiry] No token, skipping expiry fetch")
        return
    print("[Expiry] Fetching expiry lists...")
    for sym in LOC_SYMBOLS:
        try:
            expiries = await fetch_expiry_list(sym, state.access_token)
            if expiries:
                info = get_current_and_next_expiry(expiries, sym)
                state.expiry_cache[sym] = info
                default = info.get("default")
                if default:
                    loc_engine.set_expiry(sym, default)
            else:
                print(f"[Expiry] No expiries found for {sym}")
        except Exception as e:
            print(f"[Expiry] {sym} error: {e}")
    # Broadcast updated expiry cache to all clients
    await broadcast({"type":"expiry_update","expiry_cache":state.expiry_cache})


async def periodic_chain_refresh():
    """Refresh option chains every 60 seconds."""
    while True:
        await asyncio.sleep(60)
        if not state.access_token: continue
        await loc_engine.refresh_all_chains()
        # Subscribe any new option keys
        await _subscribe_option_keys()


async def _subscribe_option_keys():
    """Subscribe newly discovered option instrument keys to the feed."""
    if not state.upstox_ws: return
    new_keys = [k for k in loc_engine.get_option_keys()
                if k and k not in state.subscribed_option_keys]
    if new_keys:
        await _sub(state.upstox_ws, new_keys, "full")
        state.subscribed_option_keys.update(new_keys)
        # Update option_key_map
        for sym_st in loc_engine.symbols.values():
            if sym_st.ce.instrument_key:
                option_key_map[sym_st.ce.instrument_key] = (sym_st.symbol, "CE")
            if sym_st.pe.instrument_key:
                option_key_map[sym_st.pe.instrument_key] = (sym_st.symbol, "PE")
        print(f"[Options] Subscribed {len(new_keys)} option keys")


# ══════════════════════════════════════════════════════════════════
#  ROUTES
# ══════════════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
async def root():
    return (Path(__file__).parent.parent/"frontend"/"index.html").read_text(encoding="utf-8")

@app.post("/auth/login")
async def login(payload: dict):
    if payload.get("password") == PASSWORD:
        token = f"sess_{int(time.time())}"
        state.sessions[token] = {"ts": time.time()}
        return {"status":"ok","token":token}
    raise HTTPException(401, "Invalid password")

@app.get("/auth/upstox/login")
async def upstox_login():
    params = {"client_id":API_KEY,"redirect_uri":REDIRECT_URI,"response_type":"code"}
    return RedirectResponse(f"https://api.upstox.com/v2/login/authorization/dialog?{urlencode(params)}")

@app.get("/auth/callback")
async def callback(code: str):
    async with httpx.AsyncClient() as c:
        r = await c.post("https://api.upstox.com/v2/login/authorization/token",
            data={"code":code,"client_id":API_KEY,"client_secret":API_SECRET,
                  "redirect_uri":REDIRECT_URI,"grant_type":"authorization_code"},
            headers={"Accept":"application/json"})
    d = r.json()
    if "access_token" not in d: raise HTTPException(400, str(d))
    state.access_token = d["access_token"]
    loc_engine.access_token = d["access_token"]
    asyncio.create_task(_restart_all())
    return RedirectResponse("/?auth=success")

@app.post("/auth/token")
async def set_token(payload: dict):
    t = payload.get("access_token","")
    if not t: raise HTTPException(400, "access_token required")
    state.access_token = t
    loc_engine.access_token = t
    asyncio.create_task(_restart_all())
    return {"status":"ok","message":"Feed starting..."}

async def _restart_all():
    if state.feed_task and not state.feed_task.done():
        state.feed_task.cancel()
    state.feed_task = asyncio.create_task(start_feed())
    await asyncio.sleep(3)
    await init_expiries()
    if state.chain_task and not state.chain_task.done():
        state.chain_task.cancel()
    state.chain_task = asyncio.create_task(periodic_chain_refresh())

@app.get("/api/market-data")
async def market_data():
    return {"market_data":state.market_data,"market_status":state.market_status,
            "timestamp":int(time.time()*1000),"mode":"mock" if USE_MOCK else "live"}

@app.get("/api/loc-all")
async def loc_all():
    return loc_engine.get_all_results()

@app.get("/api/loc/{symbol}")
async def get_loc(symbol: str):
    st = loc_engine.get_state(symbol.upper())
    if not st: raise HTTPException(404,"Not found")
    return st.loc_result or {"symbol":symbol,"error":"No data yet — waiting for expiry/chain"}

@app.get("/api/loc-history/{symbol}")
async def loc_history(symbol: str):
    return {"symbol":symbol,"history":state.loc_history.get(symbol.upper(),[])}

@app.get("/api/expiry/{symbol}")
async def get_expiry(symbol: str):
    return state.expiry_cache.get(symbol.upper(), {"error":"Not loaded","all":[]})

@app.post("/api/expiry/{symbol}")
async def set_expiry(symbol: str, payload: dict):
    expiry = payload.get("expiry","")
    sym = symbol.upper()
    if sym not in state.expiry_cache:
        state.expiry_cache[sym] = {}
    state.expiry_cache[sym]["selected"] = expiry
    loc_engine.set_expiry(sym, expiry)
    return {"status":"ok","symbol":sym,"expiry":expiry}

@app.get("/api/status")
async def get_status():
    return {
        "auth": bool(state.access_token) or USE_MOCK,
        "feed_connected": state.upstox_ws is not None,
        "instruments": len(state.market_data),
        "frames": state.frame_count,
        "decoded": state.decode_ok,
        "mode": "mock" if USE_MOCK else "live",
        "option_keys_subscribed": len(state.subscribed_option_keys),
        "expiry_loaded": list(state.expiry_cache.keys()),
        "loc_symbols": list(loc_engine.symbols.keys()),
    }

@app.get("/api/debug/chain/{symbol}")
async def debug_chain(symbol: str):
    """Show current chain data for debugging."""
    st = loc_engine.get_state(symbol.upper())
    if not st: return {"error":"not registered"}
    ce_s = st.ce_strike; pe_s = st.pe_strike
    chain_sample = {}
    if st.option_chain:
        for s in [ce_s-100, ce_s-50, ce_s, st.last_atm, pe_s, pe_s+50, pe_s+100]:
            if s in st.option_chain:
                chain_sample[s] = {"CE_ltp":st.option_chain[s]["CE"]["ltp"],
                                   "PE_ltp":st.option_chain[s]["PE"]["ltp"]}
    return {
        "symbol": symbol, "expiry": st.expiry,
        "spot_ltp": st.spot.ltp, "last_atm": st.last_atm,
        "ce_strike": ce_s, "ce_ltp": st.ce.ltp, "ce_key": st.ce.instrument_key,
        "pe_strike": pe_s, "pe_ltp": st.pe.ltp, "pe_key": st.pe.instrument_key,
        "chain_size": len(st.option_chain),
        "chain_sample": chain_sample,
        "loc": st.loc_result,
    }

@app.get("/api/ohlc/{key:path}")
async def get_ohlc(key: str):
    return {"key":key,"candles":state.ohlc_history.get(key,[])}

@app.post("/api/subscribe")
async def subscribe(payload: dict):
    keys = payload.get("instrumentKeys",[]); mode = payload.get("mode","full")
    if state.upstox_ws and keys: await _sub(state.upstox_ws, keys, mode)
    return {"status":"ok"}

watchlists: dict = {}

@app.get("/api/watchlist")
async def get_wl():
    return watchlists

@app.post("/api/watchlist")
async def save_wl(p: dict):
    n = p.get("name","default")
    watchlists[n] = p.get("keys",[])
    return {"status":"ok"}

@app.delete("/api/watchlist/{name}")
async def del_wl(name: str):
    watchlists.pop(name, None)
    return {"status":"ok"}


# ══════════════════════════════════════════════════════════════════
#  BROWSER WEBSOCKET
# ══════════════════════════════════════════════════════════════════

@app.websocket("/ws/feed")
async def ws_browser(ws: WebSocket):
    await ws.accept()
    state.connected_clients.add(ws)
    try:
        await ws.send_text(json.dumps({
            "type": "snapshot",
            "market_data": state.market_data,
            "market_status": state.market_status,
            "loc_results": loc_engine.get_all_results(),
            "expiry_cache": state.expiry_cache,
            "mode": "mock" if USE_MOCK else "live",
        }))
        while True:
            await asyncio.sleep(20)
            await ws.send_text(json.dumps({"type":"ping","ts":int(time.time()*1000)}))
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        state.connected_clients.discard(ws)


async def broadcast(msg: dict):
    if msg.get("type") == "live_feed":
        for k, v in msg.get("feeds",{}).items():
            ltpc = v.get("ltpc",{}); ltp = ltpc.get("ltp",0)
            ts   = int(msg.get("currentTs",0) or time.time()*1000)
            state.market_data[k] = {**v,"ts":str(ts)}
            if ltp: _update_ohlc(k, ltp, ts)
    elif msg.get("type") == "market_info":
        si = msg.get("marketInfo",{}).get("segmentStatus",{})
        if si: state.market_status = si
    if not state.connected_clients: return
    t = json.dumps(msg)
    dead = set()
    for ws in list(state.connected_clients):
        try: await ws.send_text(t)
        except: dead.add(ws)
    state.connected_clients -= dead


# ══════════════════════════════════════════════════════════════════
#  FEED — routes ticks to LOC engine
# ══════════════════════════════════════════════════════════════════

def _route_to_loc(key: str, data: dict):
    """Route live tick to LOC engine (spot or option)."""
    ltpc = data.get("ltpc",{}); ltp = ltpc.get("ltp",0)
    if not ltp: return
    ef = data.get("efeed",{})

    # Spot tick
    sym = SPOT_KEY_TO_SYM.get(key)
    if sym and sym in LOC_SYMBOLS:
        loc_engine.update_spot(
            symbol=sym, ltp=ltp,
            close=ltpc.get("cp",0) or ef.get("cp",0),
            high=ef.get("high",0)  or ef.get("ltp",ltp),
            low=ef.get("low",0)   or ef.get("ltp",ltp),
            ts=int(data.get("ts",0) or time.time()*1000)
        )
        return

    # Option tick
    if key in option_key_map:
        sym, opt_type = option_key_map[key]
        loc_engine.update_option_from_feed(
            symbol=sym, opt_type=opt_type, ltp=ltp,
            close=ltpc.get("cp",0),
            high=ef.get("high",0),
            low=ef.get("low",0),
            iv=ef.get("iv",0) or data.get("optionGreeks",{}).get("iv",0),
        )


# ══════════════════════════════════════════════════════════════════
#  UPSTOX LIVE FEED
# ══════════════════════════════════════════════════════════════════

def _sub_msg(keys, mode):
    return json.dumps({"guid":f"d{int(time.time())}","method":"sub",
                        "data":{"mode":mode,"instrumentKeys":keys}}).encode()

async def _sub(ws, keys, mode="full"):
    await ws.send(_sub_msg(keys, mode))

def _ws_connect(url, headers):
    sig = inspect.signature(websockets.connect); p = sig.parameters
    kw  = dict(ping_interval=20, ping_timeout=10)
    if "extra_headers" in p: kw["extra_headers"] = headers
    else: kw["additional_headers"] = headers
    return websockets.connect(url, **kw)


async def start_feed():
    if USE_MOCK:
        from backend.mock_feed import start_mock_feed
        await start_mock_feed(broadcast)
        return
    headers = {"Authorization":f"Bearer {state.access_token}","Accept":"*/*"}
    while True:
        try:
            async with _ws_connect(FEED_URL, headers) as ws:
                state.upstox_ws = ws
                print("[Feed] ✓ Connected to Upstox")
                await _sub(ws, INDEX_KEYS, "full")
                await asyncio.sleep(0.3)
                await _sub(ws, COMMODITY_KEYS, "ltpc")
                await asyncio.sleep(0.3)
                for i in range(0, len(FO_STOCKS), 100):
                    await _sub(ws, FO_STOCKS[i:i+100], "ltpc")
                    await asyncio.sleep(0.2)
                # Subscribe already-known option keys
                opt_keys = loc_engine.get_option_keys()
                if opt_keys:
                    await _sub(ws, opt_keys, "full")
                    state.subscribed_option_keys.update(opt_keys)
                print(f"[Feed] Subscribed {len(INDEX_KEYS)+len(COMMODITY_KEYS)+len(FO_STOCKS)} spot + {len(opt_keys)} option keys")

                async for raw in ws:
                    state.frame_count += 1
                    is_bin = isinstance(raw, bytes)
                    msg = decode_v3(raw) if is_bin else (json.loads(raw) if raw else None)
                    if msg and (msg.get("feeds") or msg.get("marketInfo")):
                        state.decode_ok += 1
                        for k, v in msg.get("feeds",{}).items():
                            _route_to_loc(k, v)
                        await broadcast(msg)
                        # Check for new option keys to subscribe after chain loads
                        await _subscribe_option_keys()

        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[Feed] Error: {e}")
        finally:
            state.upstox_ws = None
        await asyncio.sleep(5)


@app.on_event("startup")
async def startup():
    print(f"  RAIMA Markets v5  |  {'MOCK' if USE_MOCK else 'LIVE'}  |  ws={websockets.__version__}")
    if USE_MOCK:
        from backend.mock_feed import start_mock_feed
        state.feed_task = asyncio.create_task(start_mock_feed(broadcast))
    elif state.access_token:
        loc_engine.access_token = state.access_token
        state.feed_task = asyncio.create_task(start_feed())
        # Wait for feed to connect then load expiries
        asyncio.create_task(_delayed_init())
    else:
        print("[!] No token — POST /auth/token to start")

async def _delayed_init():
    """Wait a few seconds for feed to connect, then load expiries."""
    await asyncio.sleep(5)
    await init_expiries()
    state.chain_task = asyncio.create_task(periodic_chain_refresh())


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
