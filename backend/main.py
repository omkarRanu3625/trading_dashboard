"""
RAIMA Markets Dashboard – Full Backend
FastAPI + Upstox V3 Feed + LOC Calculator Engine
"""
import asyncio, inspect, json, math, os, sys, time, struct as _struct
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
USE_MOCK = "--mock" in sys.argv or os.getenv("MOCK_MODE","false").lower()=="true"

app = FastAPI(title="RAIMA Markets", version="3.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])
static_dir = Path(__file__).parent.parent / "frontend" / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

API_KEY      = os.getenv("UPSTOX_API_KEY","")
API_SECRET   = os.getenv("UPSTOX_API_SECRET","")
REDIRECT_URI = os.getenv("UPSTOX_REDIRECT_URI","http://localhost:8000/auth/callback")
ACCESS_TOKEN = os.getenv("UPSTOX_ACCESS_TOKEN","")
FEED_URL     = "wss://api.upstox.com/v3/feed/market-data-feed"

INDEX_KEYS = [
    "NSE_INDEX|Nifty 50","NSE_INDEX|Nifty Bank",
    "NSE_INDEX|Nifty Fin Service","NSE_INDEX|NIFTY MID SELECT",
    "NSE_INDEX|Nifty Next 50","BSE_INDEX|SENSEX","BSE_INDEX|BANKEX",
]
COMMODITY_KEYS = [
    "MCX_FO|CRUDEOIL25APRFUT","MCX_FO|GOLD25APRFUT",
    "MCX_FO|SILVER25MAYFUT","MCX_FO|NATURALGAS25APRFUT","MCX_FO|COPPER25APRFUT",
]
TOP_STOCKS = [
    "NSE_EQ|RELIANCE","NSE_EQ|TCS","NSE_EQ|HDFCBANK","NSE_EQ|INFY",
    "NSE_EQ|ICICIBANK","NSE_EQ|BHARTIARTL","NSE_EQ|SBIN","NSE_EQ|HINDUNILVR",
    "NSE_EQ|ITC","NSE_EQ|KOTAKBANK","NSE_EQ|LT","NSE_EQ|AXISBANK",
    "NSE_EQ|ASIANPAINT","NSE_EQ|DMART","NSE_EQ|BAJFINANCE",
    "NSE_EQ|WIPRO","NSE_EQ|ULTRACEMCO","NSE_EQ|TITAN","NSE_EQ|TECHM",
    "NSE_EQ|POWERGRID","NSE_EQ|NTPC","NSE_EQ|TATAPOWER","NSE_EQ|JSWSTEEL",
    "NSE_EQ|VOLTAS","NSE_EQ|DALBHARAT","NSE_EQ|PFC","NSE_EQ|DRREDDY",
    "NSE_EQ|SUNPHARMA","NSE_EQ|ONGC","NSE_EQ|TATACONSUM",
]

# ── Proto decoder (same as before) ──────────────────────────────
try:
    from MarketDataFeed_pb2 import FeedResponse as _FR; PROTO_OK=True
except: PROTO_OK=False

def _rv(b,p):
    r=0;s=0
    while p<len(b):
        x=b[p];p+=1;r|=(x&127)<<s
        if not(x&128):break
        s+=7
    return r,p

def _parse_ltpc(d):
    o={};i=0
    while i<len(d):
        t=d[i];i+=1;fn=t>>3;wt=t&7
        if wt==1 and i+8<=len(d):
            v=_struct.unpack_from('<d',d,i)[0];i+=8
            if fn==1:o["ltp"]=round(v,2)
            elif fn==4:o["cp"]=round(v,2)
        elif wt==0:v,i=_rv(d,i);fn==2 and o.update({"ltt":str(v)}) or fn==3 and o.update({"ltq":str(v)})
        elif wt==2:ln,i=_rv(d,i);i+=ln
        elif wt==5 and i+4<=len(d):i+=4
        else:break
    return o

def _parse_efeed(d):
    o={};i=0
    dm={1:"atp",2:"cp",6:"uc",7:"lc",8:"high52",9:"low52",10:"ltp"}
    im={3:"vtt",4:"tbq",5:"tsq"}
    while i<len(d):
        t=d[i];i+=1;fn=t>>3;wt=t&7
        if wt==1 and i+8<=len(d):
            v=_struct.unpack_from('<d',d,i)[0];i+=8
            if fn in dm:o[dm[fn]]=round(v,2)
        elif wt==0:
            v,i=_rv(d,i)
            if fn in im:o[im[fn]]=v
        elif wt==2:ln,i=_rv(d,i);i+=ln
        elif wt==5 and i+4<=len(d):i+=4
        else:break
    return o

def _parse_mf(d):
    o={};i=0
    while i<len(d):
        t=d[i];i+=1;fn=t>>3;wt=t&7
        if wt==2:
            ln,i=_rv(d,i);ch=d[i:i+ln];i+=ln
            if fn==1:
                lt=_parse_ltpc(ch)
                if lt and lt.get("ltp") and "ltpc" not in o:o["ltpc"]=lt
            elif fn==2:
                inn=_parse_mf(ch)
                for k,v in inn.items():
                    if k not in o:o[k]=v
                    elif k=="ltpc" and isinstance(v,dict):
                        for fk,fv in v.items():
                            if fk not in o["ltpc"]:o["ltpc"][fk]=fv
            elif fn==4:
                ef=_parse_efeed(ch)
                if ef:
                    o["efeed"]=ef
                    if "ltpc" not in o:o["ltpc"]={}
                    lv=ef.get("ltp")
                    cv=ef.get("cp")
                    if lv and lv!=0:o["ltpc"]["ltp"]=lv
                    if cv and cv!=0 and "cp" not in o["ltpc"]:o["ltpc"]["cp"]=cv
        elif wt==1 and i+8<=len(d):i+=8
        elif wt==0:_,i=_rv(d,i)
        elif wt==5 and i+4<=len(d):i+=4
        else:break
    return o

def _parse_fd(d):
    o={};i=0
    while i<len(d):
        t=d[i];i+=1;fn=t>>3;wt=t&7
        if wt==2:
            ln,i=_rv(d,i);ch=d[i:i+ln];i+=ln
            if fn==1:o["ltpc"]=_parse_ltpc(ch)
            elif fn==2:o.update(_parse_mf(ch))
        elif wt==0:_,i=_rv(d,i)
        elif wt==1 and i+8<=len(d):i+=8
        elif wt==5 and i+4<=len(d):i+=4
        else:break
    return o

def _parse_me(d):
    k="";v={};i=0
    while i<len(d):
        t=d[i];i+=1;fn=t>>3;wt=t&7
        if wt==2:
            ln,i=_rv(d,i);ch=d[i:i+ln];i+=ln
            if fn==1:k=ch.decode("utf-8","replace")
            elif fn==2:v=_parse_fd(ch)
        elif wt==0:_,i=_rv(d,i)
        elif wt==1 and i+8<=len(d):i+=8
        elif wt==5 and i+4<=len(d):i+=4
        else:break
    return k,v

def _parse_mi(d):
    seg={};i=0;ST={0:"CLOSED",1:"NORMAL_OPEN",2:"NORMAL_OPEN",3:"PREOPEN",4:"CLOSED"}
    while i<len(d):
        t=d[i];i+=1;fn=t>>3;wt=t&7
        if wt==2:
            ln,i=_rv(d,i);ch=d[i:i+ln];i+=ln
            if fn==1:
                si=0;sn="";sv=0
                while si<len(ch):
                    st=ch[si];si+=1;sf=st>>3;sw=st&7
                    if sw==2:
                        sln,si=_rv(ch,si)
                        if sf==1:sn=ch[si:si+sln].decode("utf-8","replace")
                        si+=sln
                    elif sw==0:sv,si=_rv(ch,si)
                    else:break
                if sn:seg[sn]=ST.get(sv,"NORMAL_OPEN")
        elif wt==0:_,i=_rv(d,i)
        elif wt==1 and i+8<=len(d):i+=8
        elif wt==5 and i+4<=len(d):i+=4
        else:break
    return seg

def decode_v3(raw):
    try: return json.loads(raw.decode("utf-8"))
    except: pass
    try:
        r={"type":"unknown","feeds":{},"currentTs":str(int(time.time()*1000))}
        i=0;mt=0
        while i<len(raw):
            t=raw[i];i+=1;fn=t>>3;wt=t&7
            if wt==0:
                v,i=_rv(raw,i)
                if fn==1:mt=v
                elif fn==3:r["currentTs"]=str(v)
            elif wt==2:
                ln,i=_rv(raw,i);ch=raw[i:i+ln];i+=ln
                if fn==2:
                    k,v=_parse_me(ch)
                    if k and v:r["feeds"][k]=v
                elif fn==4:
                    segs=_parse_mi(ch)
                    r["marketInfo"]={"segmentStatus":segs}
            elif wt==1 and i+8<=len(raw):i+=8
            elif wt==5 and i+4<=len(raw):i+=4
            else:break
        if mt==2 or r.get("marketInfo"):r["type"]="market_info"
        elif mt==1 or r["feeds"]:r["type"]="live_feed"
        return r if (r["feeds"] or r.get("marketInfo")) else None
    except: return None


# ══════════════════════════════════════════════════════════════════
#  LOC CALCULATOR ENGINE
# ══════════════════════════════════════════════════════════════════

def calc_loc(spot_ltp, spot_close, spot_high, spot_low,
             ce_ltp, ce_close, ce_high, ce_low,
             pe_ltp, pe_close, pe_high, pe_low):
    """19-formula LOC calculation engine."""
    try:
        s = spot_ltp or 1  # avoid div/0
        # 1) CEH/SH
        ceh_sh = max(ce_high or 0, ce_close or 0) / max(spot_high or 1, spot_close or 1)
        # 2) CEL/SL
        cel_sl = min(ce_low or 0, ce_close or 0) / min(spot_low or 1, spot_close or 1) if min(spot_low or 1, spot_close or 1) != 0 else 0
        # 3) PEH/SL
        peh_sl = max(pe_high or 0, pe_close or 0) / min(spot_low or 1, spot_close or 1) if min(spot_low or 1, spot_close or 1) != 0 else 0
        # 4) PEL/SH
        pel_sh = min(pe_low or 0, pe_close or 0) / max(spot_high or 1, spot_close or 1)
        # 5) C-CE/S
        c_ce_s = (ce_ltp or 0) / s
        # 6) C-PE/S
        c_pe_s = (pe_ltp or 0) / s
        # 7) Call Move
        call_move = ceh_sh - cel_sl
        # 8) Put Move
        put_move = peh_sl - pel_sh
        # 9) Call CP
        call_cp = call_move / 2
        # 10) Put CP
        put_cp = put_move / 2
        # 11) Call CP Diff (AB)
        ab = c_ce_s - call_cp
        # 12) Put CP Diff (AC)
        ac = c_pe_s - put_cp
        # 13) Different
        different = put_move - call_move
        # 15) DSL
        if ab > 0 and ac < 0: dsl = abs(ab) + abs(ac)
        elif ab < 0 and ac > 0: dsl = abs(ab) + abs(ac)
        elif ab < 0 and ac < 0 and ab > ac: dsl = abs(ac) - abs(ab)
        elif ab < 0 and ac < 0 and ab < ac: dsl = abs(ab)
        else: dsl = abs(ab - ac)
        # 16) DSP
        dsp = dsl * s
        # 17) BOP
        if ab < ac: bop = s + dsp
        elif ab > ac: bop = s - ac
        else: bop = s
        # 18) CEP
        if ab < 0: cep = s + abs(ab) * s
        elif ab > 0: cep = s - abs(ab) * s
        else: cep = s
        # 19) PEP
        if ac < 0: pep = s - abs(ac) * s
        elif ac > 0: pep = s + abs(ac) * s
        else: pep = s
        # 14) Zone
        if s > bop and s > cep and s > pep: zone = "CALL"
        elif s < bop and s < cep and s < pep: zone = "PUT"
        else: zone = "WAIT"
        return {
            "ceh_sh": round(ceh_sh,4), "cel_sl": round(cel_sl,4),
            "peh_sl": round(peh_sl,4), "pel_sh": round(pel_sh,4),
            "c_ce_s": round(c_ce_s,4), "c_pe_s": round(c_pe_s,4),
            "call_move": round(call_move,4), "put_move": round(put_move,4),
            "call_cp": round(call_cp,4), "put_cp": round(put_cp,4),
            "call_cp_diff": round(ab,4), "put_cp_diff": round(ac,4),
            "different": round(different,4),
            "dsl": round(dsl,4), "dsp": round(dsp,2),
            "bop": round(bop,2), "cep": round(cep,2), "pep": round(pep,2),
            "zone": zone,
            "change": round(s - (spot_close or s), 2),
            "distance": round(abs(s - bop), 2),
            "direction": "UP" if s > (spot_close or s) else "DOWN",
        }
    except Exception as e:
        return {"error": str(e)}


# ══════════════════════════════════════════════════════════════════
#  APP STATE
# ══════════════════════════════════════════════════════════════════
class AppState:
    access_token: str = ACCESS_TOKEN
    market_data: dict = {}     # key → {ltpc, efeed, ts}
    market_status: dict = {}
    ohlc_history: dict = {}    # key → list of {ts,o,h,l,c,v}
    loc_data: dict = {}        # symbol → loc calc results
    connected_clients: Set[WebSocket] = set()
    upstox_ws = None
    feed_task = None
    frame_count: int = 0
    decode_ok: int = 0

state = AppState()


# ══════════════════════════════════════════════════════════════════
#  OHLC HISTORY BUILDER (1-min candles from ticks)
# ══════════════════════════════════════════════════════════════════
def _update_ohlc(key, ltp, ts_ms):
    if not ltp or ltp == 0: return
    minute = (int(ts_ms) // 60000) * 60000
    hist = state.ohlc_history.setdefault(key, [])
    if hist and hist[-1]["t"] == minute:
        c = hist[-1]
        c["h"] = max(c["h"], ltp)
        c["l"] = min(c["l"], ltp)
        c["c"] = ltp
        c["v"] = c.get("v", 0) + 1
    else:
        hist.append({"t": minute, "o": ltp, "h": ltp, "l": ltp, "c": ltp, "v": 1})
        if len(hist) > 390:  # keep 1 day
            hist.pop(0)


# ══════════════════════════════════════════════════════════════════
#  ROUTES
# ══════════════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
async def root():
    return (Path(__file__).parent.parent/"frontend"/"index.html").read_text(encoding="utf-8")

@app.get("/auth/login")
async def login():
    if not API_KEY: raise HTTPException(400,"API_KEY not set")
    return RedirectResponse(f"https://api.upstox.com/v2/login/authorization/dialog?"
                            f"client_id={API_KEY}&redirect_uri={REDIRECT_URI}&response_type=code")

@app.get("/auth/callback")
async def callback(code: str):
    async with httpx.AsyncClient() as c:
        r = await c.post("https://api.upstox.com/v2/login/authorization/token",
            data={"code":code,"client_id":API_KEY,"client_secret":API_SECRET,
                  "redirect_uri":REDIRECT_URI,"grant_type":"authorization_code"},
            headers={"Accept":"application/json"})
    d = r.json()
    if "access_token" not in d: raise HTTPException(400,str(d))
    state.access_token = d["access_token"]
    asyncio.create_task(start_feed())
    return RedirectResponse("/?auth=success")

@app.post("/auth/token")
async def set_token(payload: dict):
    t = payload.get("access_token","")
    if not t: raise HTTPException(400,"access_token required")
    state.access_token = t
    if state.feed_task and not state.feed_task.done(): state.feed_task.cancel()
    state.feed_task = asyncio.create_task(start_feed())
    return {"status":"ok"}

@app.get("/api/market-data")
async def market_data():
    return {"market_data":state.market_data,"market_status":state.market_status,
            "timestamp":int(time.time()*1000),"mode":"mock" if USE_MOCK else "live"}

@app.get("/api/status")
async def status():
    return {"auth":bool(state.access_token) or USE_MOCK,
            "feed_connected":state.upstox_ws is not None,
            "instruments":len(state.market_data),"frames":state.frame_count,
            "decoded":state.decode_ok,"mode":"mock" if USE_MOCK else "live"}

@app.get("/api/ohlc/{instrument_key:path}")
async def get_ohlc(instrument_key: str):
    """Return OHLC candle history for charting."""
    data = state.ohlc_history.get(instrument_key, [])
    return {"key": instrument_key, "candles": data}

@app.get("/api/loc/{symbol}")
async def get_loc(symbol: str, expiry: str = ""):
    """Return LOC calculation for a symbol."""
    return state.loc_data.get(symbol, {"error": "No data yet"})

@app.post("/api/loc/calculate")
async def calc_loc_endpoint(payload: dict):
    """Manual LOC calculation from provided inputs."""
    result = calc_loc(**payload)
    return result

@app.get("/api/instruments")
async def get_instruments():
    """Return categorized list of all tracked instruments."""
    return {
        "indices": INDEX_KEYS,
        "commodities": COMMODITY_KEYS,
        "stocks": TOP_STOCKS,
    }

@app.post("/api/subscribe")
async def subscribe(payload: dict):
    keys = payload.get("instrumentKeys",[]); mode = payload.get("mode","full")
    if state.upstox_ws and keys: await _sub(state.upstox_ws, keys, mode)
    return {"status":"ok","subscribed":keys}


# ══════════════════════════════════════════════════════════════════
#  BROWSER WEBSOCKET
# ══════════════════════════════════════════════════════════════════

@app.websocket("/ws/feed")
async def ws_browser(ws: WebSocket):
    await ws.accept(); state.connected_clients.add(ws)
    try:
        await ws.send_text(json.dumps({"type":"snapshot","market_data":state.market_data,
                                        "market_status":state.market_status,
                                        "mode":"mock" if USE_MOCK else "live"}))
        while True:
            await asyncio.sleep(20)
            await ws.send_text(json.dumps({"type":"ping","ts":int(time.time()*1000)}))
    except (WebSocketDisconnect,Exception): pass
    finally: state.connected_clients.discard(ws)

async def broadcast(msg: dict):
    if msg.get("type")=="live_feed":
        for k,v in msg.get("feeds",{}).items():
            ltpc = v.get("ltpc",{})
            ltp = ltpc.get("ltp",0)
            ts = int(msg.get("currentTs",0) or time.time()*1000)
            state.market_data[k] = {**v, "ts": str(ts)}
            if ltp: _update_ohlc(k, ltp, ts)
    elif msg.get("type")=="market_info":
        si = msg.get("marketInfo",{}).get("segmentStatus",{})
        if si: state.market_status = si
    if not state.connected_clients: return
    t = json.dumps(msg); dead = set()
    for ws in list(state.connected_clients):
        try: await ws.send_text(t)
        except: dead.add(ws)
    state.connected_clients -= dead


# ══════════════════════════════════════════════════════════════════
#  UPSTOX LIVE FEED
# ══════════════════════════════════════════════════════════════════

def _sub_msg(keys, mode):
    return json.dumps({"guid":f"d{int(time.time())}","method":"sub",
                        "data":{"mode":mode,"instrumentKeys":keys}}).encode()
async def _sub(ws,keys,mode="full"): await ws.send(_sub_msg(keys,mode))

def _ws_connect(url,headers):
    sig=inspect.signature(websockets.connect);p=sig.parameters
    kw=dict(ping_interval=20,ping_timeout=10)
    if "extra_headers" in p: kw["extra_headers"]=headers
    else: kw["additional_headers"]=headers
    return websockets.connect(url,**kw)

async def start_feed():
    if USE_MOCK:
        from backend.mock_feed import start_mock_feed
        await start_mock_feed(broadcast); return
    headers={"Authorization":f"Bearer {state.access_token}","Accept":"*/*"}
    while True:
        try:
            async with _ws_connect(FEED_URL,headers) as ws:
                state.upstox_ws=ws
                print("[Feed] ✓ Connected")
                await _sub(ws,INDEX_KEYS,"full")
                await asyncio.sleep(0.3)
                await _sub(ws,COMMODITY_KEYS,"ltpc")
                await asyncio.sleep(0.3)
                await _sub(ws,TOP_STOCKS[:50],"ltpc")
                async for raw in ws:
                    state.frame_count+=1
                    is_bin=isinstance(raw,bytes)
                    msg=decode_v3(raw) if is_bin else (json.loads(raw) if raw else None)
                    if msg and (msg.get("feeds") or msg.get("marketInfo")):
                        state.decode_ok+=1
                        await broadcast(msg)
        except asyncio.CancelledError: break
        except Exception as e: print(f"[Feed] {e}")
        finally: state.upstox_ws=None
        await asyncio.sleep(5)


@app.on_event("startup")
async def startup():
    print(f"  RAIMA Markets v3  |  {'MOCK' if USE_MOCK else 'LIVE'}  |  ws={websockets.__version__}")
    if USE_MOCK:
        from backend.mock_feed import start_mock_feed
        state.feed_task=asyncio.create_task(start_mock_feed(broadcast))
    elif state.access_token:
        state.feed_task=asyncio.create_task(start_feed())
    else: print("[!] No token")

if __name__=="__main__":
    import uvicorn
    uvicorn.run("main:app",host="0.0.0.0",port=8000,reload="--reload" in sys.argv)
