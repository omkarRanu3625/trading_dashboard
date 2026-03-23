"""
RAIMA Markets Dashboard v7
Fixes:
- Stocks update live (correct ISIN key routing)
- CE/PE fetch via market-quote REST when chain ltp=0
- Commodities section populates
- Change% shows correctly
"""
import asyncio, inspect, json, os, time, struct as _struct
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

app = FastAPI(title="RAIMA Markets v7")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])
static_dir = Path(__file__).parent.parent / "frontend" / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

API_KEY      = os.getenv("UPSTOX_API_KEY",    "8e11a453-2de7-4b87-9e02-986a0661d762")
API_SECRET   = os.getenv("UPSTOX_API_SECRET", "fuy5zne695")
REDIRECT_URI = os.getenv("UPSTOX_REDIRECT_URI","https://trading-dashboard-15ld.onrender.com/auth/callback")
ACCESS_TOKEN = os.getenv("UPSTOX_ACCESS_TOKEN","")
FEED_URL     = "wss://api.upstox.com/v3/feed/market-data-feed"
PASSWORD     = os.getenv("DASHBOARD_PASSWORD","raima2024")

from .instruments import (
    SPOT_KEYS, get_current_and_next_expiry, get_itm2_strikes,
    fetch_expiry_list, fetch_option_chain, calculate_expiries_fallback
)
from .instrument_keys import NSE_EQ_KEYS, FO_STOCK_KEYS, ISIN_TO_SYMBOL
from .loc_engine import LOCEngine

LOC_SYMBOLS = ["NIFTY","BANKNIFTY","FINNIFTY","MIDCPNIFTY","SENSEX",
               "CRUDEOIL","NATURALGAS","GOLD","SILVER"]

INDEX_KEYS = [
    "NSE_INDEX|Nifty 50","NSE_INDEX|Nifty Bank","NSE_INDEX|Nifty Fin Service",
    "NSE_INDEX|NIFTY MID SELECT","NSE_INDEX|Nifty Next 50",
    "BSE_INDEX|SENSEX","BSE_INDEX|BANKEX",
]

def _mcx_key(sym, months=0):
    from datetime import date, timedelta
    M=["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"]
    d = date.today() + timedelta(days=30*months)
    return f"MCX_FO|{sym}{str(d.year)[2:]}{M[d.month-1]}FUT"

# MCX commodity keys (current + next month)
_MCX_SYMS = ["CRUDEOIL","NATURALGAS","GOLD","SILVER"]
COMMODITY_KEYS = list(dict.fromkeys(
    [_mcx_key(s) for s in _MCX_SYMS] + [_mcx_key(s,1) for s in _MCX_SYMS]
))
print(f"[MCX] Keys: {COMMODITY_KEYS[:4]}")

# Build SPOT_KEYS_DYNAMIC with correct MCX month
SPOT_KEYS_DYNAMIC = dict(SPOT_KEYS)
for s in _MCX_SYMS:
    SPOT_KEYS_DYNAMIC[s] = _mcx_key(s)

# Reverse map: feed_key → symbol name
FEED_KEY_TO_SYM: dict = {}
for sym, key in SPOT_KEYS_DYNAMIC.items():
    FEED_KEY_TO_SYM[key] = sym
# Also map next-month MCX
for s in _MCX_SYMS:
    FEED_KEY_TO_SYM[_mcx_key(s,1)] = s

# ISIN reverse map for display: feed key → symbol
ISIN_REVERSE = {v: k for k, v in NSE_EQ_KEYS.items()}

# Option key → (symbol, CE/PE)
option_key_map: dict = {}


# ══════════════════════════════════════════════════════════════════
#  PROTO DECODER
# ══════════════════════════════════════════════════════════════════

def _rv(b, p):
    r=0; s=0
    while p<len(b):
        x=b[p]; p+=1; r|=(x&127)<<s
        if not(x&128): break
        s+=7
    return r, p

def _parse_ltpc(d):
    o={}; i=0
    while i<len(d):
        t=d[i]; i+=1; fn=t>>3; wt=t&7
        if wt==1 and i+8<=len(d):
            v=_struct.unpack_from('<d',d,i)[0]; i+=8
            if fn==1: o["ltp"]=round(v,2)
            elif fn==4: o["cp"]=round(v,2)
        elif wt==0:
            v,i=_rv(d,i)
            if fn==2: o["ltt"]=str(v)
        elif wt==2: ln,i=_rv(d,i); i+=ln
        elif wt==5 and i+4<=len(d): i+=4
        else: break
    return o

def _parse_efeed(d):
    o={}; i=0
    dm={1:"atp",2:"cp",6:"uc",7:"lc",8:"high52",9:"low52",10:"ltp",11:"high",12:"low"}
    while i<len(d):
        t=d[i]; i+=1; fn=t>>3; wt=t&7
        if wt==1 and i+8<=len(d):
            v=_struct.unpack_from('<d',d,i)[0]; i+=8
            if fn in dm: o[dm[fn]]=round(v,2)
        elif wt==0: _,i=_rv(d,i)
        elif wt==2: ln,i=_rv(d,i); i+=ln
        elif wt==5 and i+4<=len(d): i+=4
        else: break
    return o

def _parse_mf(d):
    o={}; i=0
    while i<len(d):
        t=d[i]; i+=1; fn=t>>3; wt=t&7
        if wt==2:
            ln,i=_rv(d,i); ch=d[i:i+ln]; i+=ln
            if fn==1:
                lt=_parse_ltpc(ch)
                if lt and lt.get("ltp") and "ltpc" not in o: o["ltpc"]=lt
            elif fn==2:
                inn=_parse_mf(ch)
                for k,v in inn.items():
                    if k not in o: o[k]=v
                    elif k=="ltpc" and isinstance(v,dict):
                        for fk,fv in v.items():
                            o["ltpc"].setdefault(fk,fv)
            elif fn==4:
                ef=_parse_efeed(ch)
                if ef:
                    o["efeed"]=ef
                    if "ltpc" not in o: o["ltpc"]={}
                    lv=ef.get("ltp"); cv=ef.get("cp")
                    if lv and lv!=0: o["ltpc"]["ltp"]=lv
                    if cv and cv!=0 and "cp" not in o["ltpc"]: o["ltpc"]["cp"]=cv
        elif wt==1 and i+8<=len(d): i+=8
        elif wt==0: _,i=_rv(d,i)
        elif wt==5 and i+4<=len(d): i+=4
        else: break
    return o

def _parse_fd(d):
    o={}; i=0
    while i<len(d):
        t=d[i]; i+=1; fn=t>>3; wt=t&7
        if wt==2:
            ln,i=_rv(d,i); ch=d[i:i+ln]; i+=ln
            if fn==1: o["ltpc"]=_parse_ltpc(ch)
            elif fn==2: o.update(_parse_mf(ch))
        elif wt==0: _,i=_rv(d,i)
        elif wt==1 and i+8<=len(d): i+=8
        elif wt==5 and i+4<=len(d): i+=4
        else: break
    return o

def _parse_me(d):
    k=""; v={}; i=0
    while i<len(d):
        t=d[i]; i+=1; fn=t>>3; wt=t&7
        if wt==2:
            ln,i=_rv(d,i); ch=d[i:i+ln]; i+=ln
            if fn==1: k=ch.decode("utf-8","replace")
            elif fn==2: v=_parse_fd(ch)
        elif wt==0: _,i=_rv(d,i)
        elif wt==1 and i+8<=len(d): i+=8
        elif wt==5 and i+4<=len(d): i+=4
        else: break
    return k,v

def _parse_mi(d):
    seg={}; i=0
    ST={0:"CLOSED",1:"NORMAL_OPEN",2:"NORMAL_OPEN",3:"PREOPEN",4:"CLOSED"}
    while i<len(d):
        t=d[i]; i+=1; fn=t>>3; wt=t&7
        if wt==2:
            ln,i=_rv(d,i); ch=d[i:i+ln]; i+=ln
            if fn==1:
                si=0; sn=""; sv=0
                while si<len(ch):
                    st=ch[si]; si+=1; sf=st>>3; sw=st&7
                    if sw==2:
                        sln,si=_rv(ch,si)
                        if sf==1: sn=ch[si:si+sln].decode("utf-8","replace")
                        si+=sln
                    elif sw==0: sv,si=_rv(ch,si)
                    else: break
                if sn: seg[sn]=ST.get(sv,"NORMAL_OPEN")
        elif wt==0: _,i=_rv(d,i)
        elif wt==1 and i+8<=len(d): i+=8
        elif wt==5 and i+4<=len(d): i+=4
        else: break
    return seg

def decode_v3(raw):
    try: return json.loads(raw.decode("utf-8"))
    except: pass
    try:
        r={"type":"unknown","feeds":{},"currentTs":str(int(time.time()*1000))}
        i=0; mt=0
        while i<len(raw):
            t=raw[i]; i+=1; fn=t>>3; wt=t&7
            if wt==0:
                v,i=_rv(raw,i)
                if fn==1: mt=v
                elif fn==3: r["currentTs"]=str(v)
            elif wt==2:
                ln,i=_rv(raw,i); ch=raw[i:i+ln]; i+=ln
                if fn==2:
                    k,v=_parse_me(ch)
                    if k and v: r["feeds"][k]=v
                elif fn==4:
                    r["marketInfo"]={"segmentStatus":_parse_mi(ch)}
            elif wt==1 and i+8<=len(raw): i+=8
            elif wt==5 and i+4<=len(raw): i+=4
            else: break
        if mt==2 or r.get("marketInfo"): r["type"]="market_info"
        elif mt==1 or r["feeds"]: r["type"]="live_feed"
        return r if (r["feeds"] or r.get("marketInfo")) else None
    except: return None

def extract_ltp_cp(fv: dict):
    ltpc=fv.get("ltpc",{}); ef=fv.get("efeed",{})
    ltp = ltpc.get("ltp",0)
    cp  = ltpc.get("cp",0) or ef.get("cp",0)
    high = ef.get("high",0) or ltp
    low  = ef.get("low",0)  or ltp
    return ltp, cp, high, low


# ══════════════════════════════════════════════════════════════════
#  APP STATE
# ══════════════════════════════════════════════════════════════════

class AppState:
    access_token:  str = ACCESS_TOKEN
    market_data:   dict = {}
    market_status: dict = {}
    ohlc_history:  dict = {}
    loc_history:   dict = {}
    loc_history_last: dict = {}
    connected_clients: Set[WebSocket] = set()
    upstox_ws  = None
    feed_task  = None
    chain_task = None
    frame_count: int = 0
    decode_ok:   int = 0
    sessions:    dict = {}
    expiry_cache: dict = {}
    subscribed_option_keys: set = set()
    # Track previous close for change% calculation
    prev_close_cache: dict = {}

state = AppState()
loc_engine = LOCEngine()

async def on_loc_updated(symbol: str, result: dict):
    _record_loc_history(symbol, result)
    spot_key = SPOT_KEYS_DYNAMIC.get(symbol,"")
    await broadcast({"type":"loc_update","symbol":symbol,"spot_key":spot_key,"loc":result})

loc_engine.on_loc_update = on_loc_updated
for sym in LOC_SYMBOLS:
    loc_engine.register(sym)

def _update_ohlc(key, ltp, ts_ms):
    if not ltp: return
    minute=(int(ts_ms)//60000)*60000
    hist=state.ohlc_history.setdefault(key,[])
    if hist and hist[-1]["t"]==minute:
        c=hist[-1]; c["h"]=max(c["h"],ltp); c["l"]=min(c["l"],ltp); c["c"]=ltp; c["v"]=c.get("v",0)+1
    else:
        hist.append({"t":minute,"o":ltp,"h":ltp,"l":ltp,"c":ltp,"v":1})
        if len(hist)>390: hist.pop(0)

def _record_loc_history(symbol, loc):
    if not loc or loc.get("error"): return
    now=int(time.time()//60)*60000
    if state.loc_history_last.get(symbol)==now: return
    state.loc_history_last[symbol]=now
    hist=state.loc_history.setdefault(symbol,[])
    keep=["ltp","bop","cep","pep","ul","ll","zone","change","direction",
          "ce_strike","pe_strike","ce_ltp","pe_ltp","ce_iv","pe_iv"]
    hist.insert(0,{"ts":int(time.time()*1000),**{k:loc[k] for k in keep if k in loc}})
    if len(hist)>60: hist.pop()


# ══════════════════════════════════════════════════════════════════
#  REST API HELPERS
# ══════════════════════════════════════════════════════════════════

def _hdr(token: str) -> dict:
    return {"Authorization":f"Bearer {token}","Accept":"application/json"}

async def fetch_market_quote_batch(keys: list, token: str) -> dict:
    """
    GET /v2/market-quote/quotes for multiple instruments.
    Returns {orig_key: {ltp, cp, high, low, open, volume}}
    """
    if not keys or not token: return {}
    results = {}
    for i in range(0, len(keys), 50):
        chunk = keys[i:i+50]
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.get(
                    "https://api.upstox.com/v2/market-quote/quotes",
                    params={"instrument_key": ",".join(chunk)},
                    headers=_hdr(token)
                )
                if r.status_code == 200:
                    data = r.json().get("data",{})
                    for resp_key, val in data.items():
                        # resp_key like "NSE_EQ:INE002A01018" or "NSE_INDEX:Nifty 50"
                        orig = resp_key.replace(":","|",1)
                        ohlc = val.get("ohlc",{})
                        ltp  = val.get("last_price",0) or ohlc.get("close",0)
                        cp   = ohlc.get("close",0) or val.get("close",0)
                        results[orig] = {
                            "ltp": ltp, "cp": cp,
                            "high": ohlc.get("high",ltp),
                            "low":  ohlc.get("low",ltp),
                            "open": ohlc.get("open",ltp),
                            "volume": val.get("volume",0),
                        }
        except Exception as e:
            print(f"[Quote] Error: {e}")
        await asyncio.sleep(0.2)
    return results

async def fetch_ohlc_snapshot(keys: list, token: str) -> dict:
    """
    GET /v2/market-quote/ohlc (1d interval) for bulk price data.
    Returns {orig_key: {ltpc:{ltp,cp}, efeed:{high,low,...}}}
    """
    if not keys or not token: return {}
    results = {}
    for i in range(0, len(keys), 50):
        chunk = keys[i:i+50]
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.get(
                    "https://api.upstox.com/v2/market-quote/ohlc",
                    params={"instrument_key": ",".join(chunk), "interval":"1d"},
                    headers=_hdr(token)
                )
                if r.status_code == 200:
                    data = r.json().get("data",{})
                    for resp_key, val in data.items():
                        orig = resp_key.replace(":","|",1)
                        ohlc = val.get("ohlc",{})
                        ltp  = val.get("last_price",0) or ohlc.get("close",0)
                        cp   = ohlc.get("close",0)
                        # Store prev close for change% calculation
                        state.prev_close_cache[orig] = cp
                        results[orig] = {
                            "ltpc":  {"ltp": ltp, "cp": cp},
                            "efeed": {
                                "high": ohlc.get("high",ltp),
                                "low":  ohlc.get("low",ltp),
                                "atp":  ltp, "cp": cp,
                            },
                        }
                elif r.status_code == 429:
                    print(f"[OHLC] Rate limited, waiting 2s...")
                    await asyncio.sleep(2)
                else:
                    print(f"[OHLC] HTTP {r.status_code}: {r.text[:100]}")
        except Exception as e:
            print(f"[OHLC] Error: {e}")
        await asyncio.sleep(0.3)
    print(f"[OHLC] Loaded {len(results)} quotes")
    return results

async def fetch_option_quotes_by_keys(ce_key: str, pe_key: str, token: str) -> tuple:
    """
    Fetch CE and PE option prices directly via market-quote API.
    Used as fallback when chain has ltp=0 (market closed / weekend).
    Returns (ce_price, pe_price)
    """
    if not ce_key and not pe_key: return 0, 0
    keys = [k for k in [ce_key, pe_key] if k]
    quotes = await fetch_market_quote_batch(keys, token)
    ce_price = quotes.get(ce_key, {}).get("ltp",0) or quotes.get(ce_key, {}).get("cp",0)
    pe_price = quotes.get(pe_key, {}).get("ltp",0) or quotes.get(pe_key, {}).get("cp",0)
    return ce_price, pe_price


# ══════════════════════════════════════════════════════════════════
#  EXPIRY & CHAIN MANAGEMENT
# ══════════════════════════════════════════════════════════════════

async def init_expiries():
    print("[Expiry] Loading expiry lists...")
    for sym in LOC_SYMBOLS:
        try:
            expiries = []
            if state.access_token:
                expiries = await fetch_expiry_list(sym, state.access_token)
            if not expiries:
                expiries = calculate_expiries_fallback(sym)
            info = get_current_and_next_expiry(expiries, sym)
            state.expiry_cache[sym] = info
            default = info.get("default")
            if default:
                loc_engine.set_expiry(sym, default)
                print(f"[Expiry] {sym} → {default}")
        except Exception as e:
            print(f"[Expiry] {sym}: {e}")
    await broadcast({"type":"expiry_update","expiry_cache":state.expiry_cache})

async def init_market_snapshot():
    """Fetch initial prices for all stocks and MCX via REST."""
    if not state.access_token: return
    print("[Snapshot] Fetching initial OHLC...")
    all_keys = list(dict.fromkeys(FO_STOCK_KEYS + COMMODITY_KEYS[:4]))
    data = await fetch_ohlc_snapshot(all_keys, state.access_token)
    for key, val in data.items():
        state.market_data[key] = {**val, "ts": str(int(time.time()*1000))}
    print(f"[Snapshot] Loaded {len(data)} instruments")
    # Push to all connected clients
    await broadcast({"type":"snapshot_update","market_data":state.market_data})

async def refresh_ce_pe_prices():
    """
    After loading chain, fetch CE/PE prices via market-quote API.
    This works even on weekends when chain ltp=0.
    """
    if not state.access_token: return
    for sym, st in loc_engine.symbols.items():
        if not st.ce.instrument_key and not st.pe.instrument_key: continue
        ce_p, pe_p = await fetch_option_quotes_by_keys(
            st.ce.instrument_key, st.pe.instrument_key, state.access_token
        )
        if ce_p or pe_p:
            if ce_p:
                st.ce.ltp   = ce_p if ce_p else st.ce.ltp
                st.ce.close = st.ce.close or ce_p
            if pe_p:
                st.pe.ltp   = pe_p if pe_p else st.pe.ltp
                st.pe.close = st.pe.close or pe_p
            print(f"[Options] {sym} REST prices: CE={ce_p} PE={pe_p}")
            loc_engine._recalc(sym)
        await asyncio.sleep(0.2)

async def periodic_chain_refresh():
    while True:
        await asyncio.sleep(60)
        if not state.access_token: continue
        await loc_engine.refresh_all_chains()
        await asyncio.sleep(1)
        await refresh_ce_pe_prices()
        await _subscribe_option_keys()

async def _subscribe_option_keys():
    if not state.upstox_ws: return
    new_keys = [k for k in loc_engine.get_option_keys()
                if k and k not in state.subscribed_option_keys]
    if new_keys:
        await _sub(state.upstox_ws, new_keys, "full")
        state.subscribed_option_keys.update(new_keys)
        for st in loc_engine.symbols.values():
            if st.ce.instrument_key:
                option_key_map[st.ce.instrument_key] = (st.symbol, "CE")
            if st.pe.instrument_key:
                option_key_map[st.pe.instrument_key] = (st.symbol, "PE")
        print(f"[Options] Subscribed {len(new_keys)} option keys to feed")


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
    raise HTTPException(401,"Invalid password")

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
    if not t: raise HTTPException(400,"access_token required")
    state.access_token = t
    loc_engine.access_token = t
    asyncio.create_task(_restart_all())
    return {"status":"ok","message":"Feed starting..."}

async def _restart_all():
    print("[Restart] Starting feed...")
    if state.feed_task and not state.feed_task.done():
        state.feed_task.cancel()
        await asyncio.sleep(1)
    state.feed_task = asyncio.create_task(start_feed())
    await asyncio.sleep(4)
    await init_expiries()
    await asyncio.sleep(1)
    await init_market_snapshot()
    await asyncio.sleep(2)
    await refresh_ce_pe_prices()
    if state.chain_task and not state.chain_task.done():
        state.chain_task.cancel()
    state.chain_task = asyncio.create_task(periodic_chain_refresh())
    print("[Restart] Done")

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
    return st.loc_result or {"error":"No data yet"}

@app.get("/api/loc-history/{symbol}")
async def loc_history(symbol: str):
    return {"symbol":symbol,"history":state.loc_history.get(symbol.upper(),[])}

@app.get("/api/expiry/{symbol}")
async def get_expiry(symbol: str):
    return state.expiry_cache.get(symbol.upper(), {"error":"Not loaded","all":[]})

@app.post("/api/expiry/{symbol}")
async def set_expiry(symbol: str, payload: dict):
    expiry = payload.get("expiry",""); sym = symbol.upper()
    if sym not in state.expiry_cache: state.expiry_cache[sym] = {}
    state.expiry_cache[sym]["selected"] = expiry
    loc_engine.set_expiry(sym, expiry)
    # Fetch chain and option prices for new expiry
    asyncio.create_task(_refresh_expiry_chain(sym, expiry))
    return {"status":"ok","symbol":sym,"expiry":expiry}

async def _refresh_expiry_chain(sym: str, expiry: str):
    chain = await fetch_option_chain(sym, expiry, state.access_token)
    if chain:
        loc_engine.update_chain(sym, chain)
    await asyncio.sleep(0.5)
    await refresh_ce_pe_prices()
    await _subscribe_option_keys()

@app.get("/api/status")
async def get_status():
    return {
        "auth": bool(state.access_token) or USE_MOCK,
        "feed_connected": state.upstox_ws is not None,
        "instruments": len(state.market_data),
        "frames": state.frame_count,
        "decoded": state.decode_ok,
        "mode": "mock" if USE_MOCK else "live",
        "option_keys": len(state.subscribed_option_keys),
        "expiry_loaded": list(state.expiry_cache.keys()),
    }

@app.get("/api/debug/chain/{symbol}")
async def debug_chain(symbol: str):
    st = loc_engine.get_state(symbol.upper())
    if not st: return {"error":"not registered"}
    return {
        "symbol": symbol, "expiry": st.expiry,
        "spot_ltp": st.spot.ltp, "last_atm": st.last_atm,
        "ce_strike": st.ce_strike, "ce_ltp": st.ce.ltp,
        "ce_close":  st.ce.close,  "ce_key": st.ce.instrument_key,
        "pe_strike": st.pe_strike, "pe_ltp": st.pe.ltp,
        "pe_close":  st.pe.close,  "pe_key": st.pe.instrument_key,
        "chain_size": len(st.option_chain), "loc": st.loc_result,
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
    watchlists.pop(name,None)
    return {"status":"ok"}


# ══════════════════════════════════════════════════════════════════
#  BROWSER WEBSOCKET
# ══════════════════════════════════════════════════════════════════

@app.websocket("/ws/feed")
async def ws_browser(ws: WebSocket):
    await ws.accept(); state.connected_clients.add(ws)
    try:
        await ws.send_text(json.dumps({
            "type":"snapshot",
            "market_data": state.market_data,
            "market_status": state.market_status,
            "loc_results": loc_engine.get_all_results(),
            "expiry_cache": state.expiry_cache,
            "mode": "mock" if USE_MOCK else "live",
        }))
        while True:
            await asyncio.sleep(20)
            await ws.send_text(json.dumps({"type":"ping","ts":int(time.time()*1000)}))
    except (WebSocketDisconnect, Exception): pass
    finally: state.connected_clients.discard(ws)

async def broadcast(msg: dict):
    # Update server-side state
    if msg.get("type") == "live_feed":
        for k, v in msg.get("feeds",{}).items():
            ltp, cp, high, low = extract_ltp_cp(v)
            ts = int(msg.get("currentTs",0) or time.time()*1000)
            # Preserve prev_close from snapshot if feed doesn't provide it
            if cp == 0 and k in state.prev_close_cache:
                cp = state.prev_close_cache[k]
                if "ltpc" in v: v["ltpc"]["cp"] = cp
            state.market_data[k] = {**state.market_data.get(k,{}), **v, "ts":str(ts)}
            if ltp: _update_ohlc(k, ltp, ts)
            _route_to_loc(k, ltp, cp, high, low, ts)
    elif msg.get("type") == "market_info":
        si = msg.get("marketInfo",{}).get("segmentStatus",{})
        if si: state.market_status = si
    elif msg.get("type") == "snapshot_update":
        # REST snapshot arrived — merge with existing data
        for k, v in msg.get("market_data",{}).items():
            if k not in state.market_data:
                state.market_data[k] = v
            else:
                # Only update if feed hasn't already updated this key
                existing = state.market_data[k]
                if existing.get("ltpc",{}).get("ltp",0) == 0:
                    state.market_data[k] = {**existing, **v}

    if not state.connected_clients: return
    t = json.dumps(msg); dead = set()
    for ws in list(state.connected_clients):
        try: await ws.send_text(t)
        except: dead.add(ws)
    state.connected_clients -= dead


# ══════════════════════════════════════════════════════════════════
#  LOC ENGINE ROUTING
# ══════════════════════════════════════════════════════════════════

def _route_to_loc(key: str, ltp: float, cp: float, high: float, low: float, ts: int):
    if not ltp: return
    # Is it a spot index/commodity?
    sym = FEED_KEY_TO_SYM.get(key)
    if sym and sym in LOC_SYMBOLS:
        loc_engine.update_spot(symbol=sym, ltp=ltp, close=cp, high=high, low=low, ts=ts)
        return
    # Is it an option?
    if key in option_key_map:
        sym, opt_type = option_key_map[key]
        loc_engine.update_option_from_feed(
            symbol=sym, opt_type=opt_type,
            ltp=ltp, close=cp, high=high, low=low
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
    kw = dict(ping_interval=20, ping_timeout=10)
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
                print("[Feed] ✓ Connected to Upstox V3")

                # 1. Indices (full mode for OHLC+efeed)
                await _sub(ws, INDEX_KEYS, "full")
                await asyncio.sleep(0.3)

                # 2. MCX commodities (full mode)
                await _sub(ws, COMMODITY_KEYS[:4], "full")
                await asyncio.sleep(0.3)

                # 3. F&O stocks with ISIN keys (full mode for live OHLC)
                stock_keys = list(dict.fromkeys(FO_STOCK_KEYS))
                for i in range(0, len(stock_keys), 100):
                    await _sub(ws, stock_keys[i:i+100], "full")
                    await asyncio.sleep(0.2)

                # 4. Option keys (if already known from chain)
                opt_keys = loc_engine.get_option_keys()
                if opt_keys:
                    await _sub(ws, opt_keys, "full")
                    state.subscribed_option_keys.update(opt_keys)
                    for st in loc_engine.symbols.values():
                        if st.ce.instrument_key:
                            option_key_map[st.ce.instrument_key] = (st.symbol,"CE")
                        if st.pe.instrument_key:
                            option_key_map[st.pe.instrument_key] = (st.symbol,"PE")

                print(f"[Feed] Subscribed: {len(INDEX_KEYS)} idx + {len(COMMODITY_KEYS[:4])} mcx "
                      f"+ {len(stock_keys)} stocks + {len(opt_keys)} options")

                tick_count = 0
                async for raw in ws:
                    state.frame_count += 1
                    is_bin = isinstance(raw, bytes)
                    msg = decode_v3(raw) if is_bin else (json.loads(raw) if raw else None)
                    if msg and (msg.get("feeds") or msg.get("marketInfo")):
                        state.decode_ok += 1
                        await broadcast(msg)
                        tick_count += 1
                        # Periodically subscribe any new option keys
                        if tick_count % 200 == 0:
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
    print(f"  RAIMA Markets v7  |  {'MOCK' if USE_MOCK else 'LIVE'}  |  ws={websockets.__version__}")
    if USE_MOCK:
        from backend.mock_feed import start_mock_feed
        state.feed_task = asyncio.create_task(start_mock_feed(broadcast))
        asyncio.create_task(_delayed_init())
    elif state.access_token:
        loc_engine.access_token = state.access_token
        state.feed_task = asyncio.create_task(start_feed())
        asyncio.create_task(_delayed_init())
    else:
        print("[!] No token — POST /auth/token")
        asyncio.create_task(_delayed_init())

async def _delayed_init():
    await asyncio.sleep(3)
    await init_expiries()
    if state.access_token:
        await asyncio.sleep(1)
        await init_market_snapshot()
        await asyncio.sleep(2)
        await refresh_ce_pe_prices()
    state.chain_task = asyncio.create_task(periodic_chain_refresh())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
