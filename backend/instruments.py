"""
instruments.py v10 — All bugs fixed
Bug fixes:
1. v3 OHLC response: parse live_ohlc/prev_ohlc not val.get("ohlc")
2. Per-item None check in fetch_quotes_rest
3. Separate index quote via /v2/market-quote/quotes (not ohlc)
4. Option chain: pick closest strike to spot_price field in response
"""
import asyncio, time
from datetime import date, timedelta
import httpx

UPSTOX_CONTRACTS  = "https://api.upstox.com/v2/option/contract"
UPSTOX_CHAIN      = "https://api.upstox.com/v2/option/chain"
UPSTOX_QUOTE_V2   = "https://api.upstox.com/v2/market-quote/quotes"
UPSTOX_OHLC_V3    = "https://api.upstox.com/v3/market-quote/ohlc"
UPSTOX_OHLC_V2    = "https://api.upstox.com/v2/market-quote/ohlc"
UPSTOX_INTRADAY   = "https://api.upstox.com/v3/historical-candle/intraday"

STRIKE_STEPS = {
    "NIFTY":50,"BANKNIFTY":100,"FINNIFTY":50,"MIDCPNIFTY":25,
    "SENSEX":100,"BANKEX":100,"CRUDEOIL":50,"NATURALGAS":10,
    "GOLD":100,"SILVER":1000,"COPPER":5,
}
MONTHLY_SYMBOLS = {"GOLD","SILVER","COPPER"}

_M = ["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"]

def mcx_key(sym: str, months_ahead: int = 0) -> str:
    d = date.today() + timedelta(days=30 * months_ahead)
    return f"MCX_FO|{sym.upper()}{str(d.year)[2:]}{_M[d.month-1]}FUT"

INDEX_SPOT = {
    "NIFTY":      "NSE_INDEX|Nifty 50",
    "BANKNIFTY":  "NSE_INDEX|Nifty Bank",
    "FINNIFTY":   "NSE_INDEX|Nifty Fin Service",
    "MIDCPNIFTY": "NSE_INDEX|NIFTY MID SELECT",
    "SENSEX":     "BSE_INDEX|SENSEX",
    "BANKEX":     "BSE_INDEX|BANKEX",
}

def get_spot_keys() -> dict:
    keys = dict(INDEX_SPOT)
    for s in ["CRUDEOIL","NATURALGAS","GOLD","SILVER"]:
        keys[s] = mcx_key(s, 0)
    return keys

def get_itm2_strikes(spot: float, symbol: str) -> tuple:
    step = STRIKE_STEPS.get(symbol.upper(), 50)
    atm  = round(round(spot / step) * step, 2)
    return atm - 2*step, atm + 2*step

def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Accept": "application/json"}

# ── Fallback expiry ──────────────────────────────────────────────
def _last_thu(year, month):
    if month == 12: nm = date(year+1,1,1)
    else:           nm = date(year,month+1,1)
    last = nm - timedelta(days=1)
    return last - timedelta(days=(last.weekday()-3)%7)

def calculate_expiries_fallback(symbol: str, count: int = 8) -> list:
    today = date.today(); sym = symbol.upper(); result = []
    if sym in MONTHLY_SYMBOLS:
        for i in range(3):
            m=today.month+i; y=today.year+(m-1)//12; m=((m-1)%12)+1
            lt=_last_thu(y,m)
            if lt >= today: result.append(lt.isoformat())
    else:
        d=today; n=0
        while n < count:
            days=(3-d.weekday())%7 or 7
            d+=timedelta(days=days)
            result.append(d.isoformat()); n+=1
    return sorted(set(result))

# ── Expiry list ──────────────────────────────────────────────────
async def fetch_expiry_list(symbol: str, token: str) -> list:
    """Extract unique expiry dates from /v2/option/contract response."""
    spot_keys = get_spot_keys()
    spot_key  = spot_keys.get(symbol.upper(), "")
    if not spot_key: return calculate_expiries_fallback(symbol)
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(UPSTOX_CONTRACTS, params={"instrument_key": spot_key}, headers=_h(token))
            print(f"[Expiry] {symbol} HTTP {r.status_code}")
            if r.status_code == 200:
                contracts = r.json().get("data", [])
                if isinstance(contracts, list):
                    expiries = sorted(set(
                        x["expiry"] for x in contracts
                        if isinstance(x, dict) and x.get("expiry")
                    ))
                    if expiries:
                        print(f"[Expiry] {symbol}: {expiries[:4]}")
                        return expiries
    except Exception as e:
        print(f"[Expiry] {symbol}: {e}")
    return calculate_expiries_fallback(symbol)

# ── Option chain ─────────────────────────────────────────────────
async def fetch_option_chain(symbol: str, expiry: str, token: str) -> dict:
    """
    Fetch full option chain. Returns {strike: {CE:{...}, PE:{...}}}.
    Also returns the spot price from underlying_spot_price field.
    MCX not supported — returns {} for MCX symbols.
    """
    spot_keys = get_spot_keys()
    spot_key  = spot_keys.get(symbol.upper(), "")
    if not spot_key or not expiry: return {}
    if spot_key.startswith("MCX"): return {}  # MCX chain not supported

    try:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.get(UPSTOX_CHAIN,
                            params={"instrument_key": spot_key, "expiry_date": expiry},
                            headers=_h(token))
            print(f"[Chain] {symbol}/{expiry} HTTP {r.status_code}")
            if r.status_code != 200:
                print(f"[Chain] error: {r.text[:200]}"); return {}
            rows = r.json().get("data", [])
            if not rows: print(f"[Chain] {symbol} empty"); return {}

            chain = {}
            spot_from_chain = 0.0  # Upstox returns underlying_spot_price
            for row in rows:
                strike = float(row.get("strike_price", 0))
                if not strike: continue
                # Get spot price from first row
                if not spot_from_chain:
                    spot_from_chain = float(row.get("underlying_spot_price", 0))

                ce = row.get("call_options", {})
                pe = row.get("put_options", {})
                ce_md = ce.get("market_data", {}) or {}
                pe_md = pe.get("market_data", {}) or {}

                def _p(d, *ks):
                    for k in ks:
                        v = d.get(k) if d else None
                        if v is not None:
                            try:
                                fv = float(v)
                                if fv != 0: return fv
                            except: pass
                    return 0.0

                chain[strike] = {
                    "CE": {
                        "ltp":   _p(ce_md, "ltp"),
                        "close": _p(ce_md, "close_price"),
                        "high":  _p(ce_md, "high_price"),
                        "low":   _p(ce_md, "low_price"),
                        "oi":    _p(ce_md, "oi"),
                        "iv":    float((ce.get("option_greeks") or {}).get("iv", 0)),
                        "key":   ce.get("instrument_key", ""),
                    },
                    "PE": {
                        "ltp":   _p(pe_md, "ltp"),
                        "close": _p(pe_md, "close_price"),
                        "high":  _p(pe_md, "high_price"),
                        "low":   _p(pe_md, "low_price"),
                        "oi":    _p(pe_md, "oi"),
                        "iv":    float((pe.get("option_greeks") or {}).get("iv", 0)),
                        "key":   pe.get("instrument_key", ""),
                    },
                    "_spot": spot_from_chain,
                }

            # Find sample near ATM
            if chain and spot_from_chain:
                atm = min(chain.keys(), key=lambda s: abs(s - spot_from_chain))
                print(f"[Chain] {symbol}/{expiry}: {len(chain)} strikes, "
                      f"spot={spot_from_chain}, ATM={atm}, "
                      f"CE_ltp={chain[atm]['CE']['ltp']}, "
                      f"CE_key={chain[atm]['CE']['key'][:25] if chain[atm]['CE']['key'] else 'MISSING'}")
            return chain
    except Exception as e:
        print(f"[Chain] {symbol}/{expiry}: {e}"); return {}

# ── OHLC snapshot for stocks (v3 format) ─────────────────────────
async def fetch_quotes_rest(keys: list, token: str) -> dict:
    """
    Fetch OHLC for stocks/commodities using /v3/market-quote/ohlc.
    v3 Response per key:
    {
      "last_price": 1234,
      "instrument_token": "NSE_EQ|INE...",
      "live_ohlc": {"open":x,"high":x,"low":x,"close":x,"volume":x,"ts":x},
      "prev_ohlc": {"open":x,"high":x,"low":x,"close":x,"volume":x,"ts":x}
    }
    Falls back to v2 format if needed.
    NOTE: Do NOT pass INDEX keys here — indices use /quotes not /ohlc
    """
    if not keys or not token: return {}
    results = {}

    # Filter out index keys — they need different endpoint
    stock_keys = [k for k in keys if not k.startswith("NSE_INDEX") and not k.startswith("BSE_INDEX")]

    for i in range(0, len(stock_keys), 50):
        chunk = stock_keys[i:i+50]
        if not chunk: continue
        try:
            async with httpx.AsyncClient(timeout=20) as c:
                r = await c.get(UPSTOX_OHLC_V3,
                                params={"instrument_key": ",".join(chunk), "interval": "1d"},
                                headers=_h(token))
                if r.status_code == 200:
                    resp_json = r.json()
                    data = resp_json.get("data") if resp_json else None
                    if data is None:
                        print(f"[OHLC-v3] null data response")
                        continue
                    for resp_key, val in data.items():
                        if val is None: continue
                        try:
                            norm = resp_key.replace(":", "|", 1)
                            ltp  = float(val.get("last_price") or 0)
                            # v3 has live_ohlc and prev_ohlc
                            live = val.get("live_ohlc") or {}
                            prev = val.get("prev_ohlc") or {}
                            # prev_ohlc.close = yesterday's close (for change%)
                            cp = float(prev.get("close") or 0)
                            if not ltp: ltp = float(live.get("close") or cp or 0)
                            o  = float(live.get("open")  or prev.get("open")  or ltp)
                            h  = float(live.get("high")  or prev.get("high")  or ltp)
                            l  = float(live.get("low")   or prev.get("low")   or ltp)
                            if l == 0 and ltp: l = ltp
                            results[norm] = {
                                "ltpc":  {"ltp": ltp, "cp": cp},
                                "efeed": {"ltp": ltp, "cp": cp, "open": o, "high": h, "low": l},
                            }
                        except Exception as ex:
                            print(f"[OHLC-v3] item error {resp_key}: {ex}")
                    print(f"[OHLC-v3] chunk {i//50+1}: +{len(data)} items, total={len(results)}")
                elif r.status_code == 429:
                    print("[OHLC] Rate limited, waiting 2s...")
                    await asyncio.sleep(2); continue
                else:
                    print(f"[OHLC-v3] HTTP {r.status_code} → trying v2...")
                    # Fallback to v2
                    r2 = await c.get(UPSTOX_OHLC_V2,
                                     params={"instrument_key": ",".join(chunk), "interval": "1d"},
                                     headers=_h(token))
                    if r2.status_code == 200:
                        data2 = (r2.json() or {}).get("data") or {}
                        for resp_key, val in data2.items():
                            if not val: continue
                            norm = resp_key.replace(":", "|", 1)
                            ohlc = val.get("ohlc") or {}
                            ltp  = float(val.get("last_price") or ohlc.get("close") or 0)
                            cp   = float(ohlc.get("close") or 0)
                            results[norm] = {
                                "ltpc":  {"ltp": ltp, "cp": cp},
                                "efeed": {"ltp": ltp, "cp": cp,
                                          "open": float(ohlc.get("open") or ltp),
                                          "high": float(ohlc.get("high") or ltp),
                                          "low":  float(ohlc.get("low")  or ltp)},
                            }
        except Exception as e:
            print(f"[OHLC] chunk error: {e}")
        await asyncio.sleep(0.3)
    return results


async def fetch_index_quotes(index_keys: list, token: str) -> dict:
    """
    Fetch index LTP+OHLC via /v2/market-quote/quotes.
    Indices don't support the /ohlc endpoint.
    """
    if not index_keys or not token: return {}
    results = {}
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(UPSTOX_QUOTE_V2,
                            params={"instrument_key": ",".join(index_keys)},
                            headers=_h(token))
            if r.status_code == 200:
                data = (r.json() or {}).get("data") or {}
                for resp_key, val in data.items():
                    if not val: continue
                    norm = resp_key.replace(":", "|", 1)
                    ohlc = val.get("ohlc") or {}
                    ltp  = float(val.get("last_price") or 0)
                    cp   = float(ohlc.get("close") or 0)
                    o    = float(ohlc.get("open")  or ltp)
                    h    = float(ohlc.get("high")  or ltp)
                    l    = float(ohlc.get("low")   or ltp)
                    results[norm] = {
                        "ltpc":  {"ltp": ltp, "cp": cp},
                        "efeed": {"ltp": ltp, "cp": cp, "open": o, "high": h, "low": l},
                    }
                print(f"[IndexQuote] {len(results)} indices loaded")
    except Exception as e:
        print(f"[IndexQuote] {e}")
    return results


async def fetch_option_ohlc_rest(ce_key: str, pe_key: str, token: str) -> dict:
    """Get full OHLC for CE and PE option keys via /v2/market-quote/quotes."""
    if not token: return {}
    keys = [k for k in [ce_key, pe_key] if k]
    if not keys: return {}
    result = {}
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(UPSTOX_QUOTE_V2,
                            params={"instrument_key": ",".join(keys)},
                            headers=_h(token))
            if r.status_code == 200:
                data = (r.json() or {}).get("data") or {}
                for orig_key in keys:
                    # Upstox returns with colon: "NSE_FO:NIFTY..."
                    colon_key = orig_key.replace("|", ":", 1)
                    val = data.get(orig_key) or data.get(colon_key) or {}
                    if val:
                        ohlc = val.get("ohlc") or {}
                        result[orig_key] = {
                            "ltp":   float(val.get("last_price") or 0),
                            "close": float(ohlc.get("close") or 0),
                            "high":  float(ohlc.get("high")  or 0),
                            "low":   float(ohlc.get("low")   or 0),
                            "open":  float(ohlc.get("open")  or 0),
                            "oi":    float(val.get("oi")      or 0),
                        }
    except Exception as e:
        print(f"[OptOHLC] {e}")
    return result


async def validate_mcx_keys(token: str) -> dict:
    """Find which MCX month actually has data."""
    result = {}
    for sym in ["CRUDEOIL","NATURALGAS","GOLD","SILVER"]:
        found = False
        for months in [0, 1, 2]:
            key = mcx_key(sym, months)
            try:
                async with httpx.AsyncClient(timeout=8) as c:
                    r = await c.get(UPSTOX_QUOTE_V2, params={"instrument_key": key}, headers=_h(token))
                    if r.status_code == 200:
                        data = (r.json() or {}).get("data") or {}
                        # Check if any key in response matches (colon vs pipe format)
                        matched = any(
                            key.split("|")[-1] in k
                            for k in data.keys()
                        )
                        if matched and data:
                            result[sym] = key
                            print(f"[MCX] {sym} → {key} ✓")
                            found = True; break
            except Exception as e:
                print(f"[MCX] {sym} {key}: {e}")
        if not found:
            result[sym] = mcx_key(sym, 1)  # default next month
            print(f"[MCX] {sym} → next month fallback {result[sym]}")
    return result


async def fetch_intraday_candles(key: str, token: str,
                                  unit: str = "minutes", interval: int = 1) -> list:
    """Fetch today's intraday candles via /v3/historical-candle/intraday."""
    if not token: return []
    encoded = key.replace("|", "%7C")
    url = f"{UPSTOX_INTRADAY}/{encoded}/{unit}/{interval}"
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(url, headers=_h(token))
            if r.status_code == 200:
                raw = (r.json() or {}).get("data", {})
                if raw is None: return []
                candles_raw = raw.get("candles", []) or []
                result = []
                for candle in candles_raw:
                    if len(candle) < 5: continue
                    try:
                        from datetime import datetime
                        ts = int(datetime.fromisoformat(str(candle[0])).timestamp()*1000)
                    except:
                        ts = int(time.time()*1000)
                    result.append({
                        "t": ts,
                        "o": float(candle[1] or 0),
                        "h": float(candle[2] or 0),
                        "l": float(candle[3] or 0),
                        "c": float(candle[4] or 0),
                        "v": int(candle[5])  if len(candle)>5 else 0,
                    })
                return result
    except Exception as e:
        print(f"[Candle] {key}: {e}")
    return []


def get_current_and_next_expiry(expiries: list, symbol: str) -> dict:
    today  = date.today()
    future = sorted([e for e in expiries if e >= today.isoformat()])
    result = {"all": expiries, "default": future[0] if future else None}
    if symbol.upper() in MONTHLY_SYMBOLS:
        this_m = today.strftime("%Y-%m")
        next_m = (today.replace(day=28)+timedelta(days=4)).strftime("%Y-%m")
        cm = [e for e in future if e.startswith(this_m)]
        nm = [e for e in future if e.startswith(next_m)]
        result["current_month"] = cm[-1] if cm else None
        result["next_month"]    = nm[-1] if nm else None
    else:
        result["current_week"] = future[0] if len(future)>0 else None
        result["next_week"]    = future[1] if len(future)>1 else None
        result["far_week"]     = future[2] if len(future)>2 else None
    return result
