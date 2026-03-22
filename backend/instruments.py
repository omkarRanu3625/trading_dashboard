"""
instruments.py — Upstox Instrument & Option Chain Helper
Handles expiry fetch, option chain fetch, ITM-2 resolution
"""
import asyncio, json, time
from datetime import date, timedelta
from typing import Optional
import httpx

UPSTOX_OPTION_CHAIN = "https://api.upstox.com/v2/option/chain"
UPSTOX_EXPIRY_URL   = "https://api.upstox.com/v2/option/contract"
UPSTOX_MARKET_QUOTE = "https://api.upstox.com/v2/market-quote/quotes"

# Strike step sizes per underlying
STRIKE_STEPS = {
    "NIFTY":      50,   "BANKNIFTY":  100,  "FINNIFTY":   50,
    "MIDCPNIFTY": 25,   "SENSEX":     100,  "BANKEX":     100,
    "CRUDEOIL":   50,   "NATURALGAS": 10,   "GOLD":       100,
    "SILVER":     1000, "COPPER":     5,
}

# Upstox instrument keys for SPOT feed
SPOT_KEYS = {
    "NIFTY":      "NSE_INDEX|Nifty 50",
    "BANKNIFTY":  "NSE_INDEX|Nifty Bank",
    "FINNIFTY":   "NSE_INDEX|Nifty Fin Service",
    "MIDCPNIFTY": "NSE_INDEX|NIFTY MID SELECT",
    "SENSEX":     "BSE_INDEX|SENSEX",
    "BANKEX":     "BSE_INDEX|BANKEX",
    "CRUDEOIL":   "MCX_FO|CRUDEOIL25APRFUT",
    "NATURALGAS": "MCX_FO|NATURALGAS25APRFUT",
    "GOLD":       "MCX_FO|GOLD25APRFUT",
    "SILVER":     "MCX_FO|SILVER25MAYFUT",
}

# Exchange for options
OPTION_EXCHANGE = {
    "NIFTY": "NSE", "BANKNIFTY": "NSE", "FINNIFTY": "NSE",
    "MIDCPNIFTY": "NSE", "SENSEX": "BSE", "BANKEX": "BSE",
    "CRUDEOIL": "MCX", "NATURALGAS": "MCX", "GOLD": "MCX", "SILVER": "MCX",
}

WEEKLY_SYMBOLS  = {"NIFTY","BANKNIFTY","FINNIFTY","MIDCPNIFTY","SENSEX","BANKEX","CRUDEOIL","NATURALGAS"}
MONTHLY_SYMBOLS = {"GOLD","SILVER","COPPER"}


def get_atm_strike(spot: float, symbol: str) -> float:
    step = STRIKE_STEPS.get(symbol.upper(), 50)
    return round(round(spot / step) * step, 2)


def get_itm2_strikes(spot: float, symbol: str) -> tuple:
    """CE ITM-2 = ATM - 2*step, PE ITM-2 = ATM + 2*step"""
    step = STRIKE_STEPS.get(symbol.upper(), 50)
    atm  = get_atm_strike(spot, symbol)
    return atm - 2*step, atm + 2*step


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Accept": "application/json"}


async def fetch_expiry_list(symbol: str, access_token: str) -> list:
    """Fetch expiry dates for a symbol from Upstox /v2/option/contract"""
    spot_key = SPOT_KEYS.get(symbol.upper(), "")
    if not spot_key:
        print(f"[Expiry] No spot key for {symbol}")
        return []
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                UPSTOX_EXPIRY_URL,
                params={"instrument_key": spot_key},
                headers=_headers(access_token)
            )
            print(f"[Expiry] {symbol} status={r.status_code} body={r.text[:200]}")
            d = r.json()
            # Upstox returns: {"status":"success","data":["2025-03-27","2025-04-03",...]}
            expiries = d.get("data", [])
            if isinstance(expiries, list):
                return sorted([e for e in expiries if isinstance(e, str)])
            return []
    except Exception as e:
        print(f"[Expiry] Error for {symbol}: {e}")
        return []


async def fetch_option_chain(symbol: str, expiry: str, access_token: str) -> dict:
    """
    Fetch option chain for symbol+expiry.
    Returns: {strike: {CE:{ltp,close,high,low,oi,iv}, PE:{...},
                        instrument_key_ce, instrument_key_pe}}
    """
    spot_key = SPOT_KEYS.get(symbol.upper(), "")
    if not spot_key or not expiry:
        return {}
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(
                UPSTOX_OPTION_CHAIN,
                params={"instrument_key": spot_key, "expiry_date": expiry},
                headers=_headers(access_token)
            )
            print(f"[Chain] {symbol} {expiry} status={r.status_code}")
            if r.status_code != 200:
                print(f"[Chain] Error body: {r.text[:300]}")
                return {}
            data = r.json()
            chain = {}
            rows = data.get("data", [])
            if not rows:
                print(f"[Chain] Empty data for {symbol} {expiry}")
                return {}
            for row in rows:
                strike = float(row.get("strike_price", 0))
                ce     = row.get("call_options", {})
                pe     = row.get("put_options", {})
                ce_md  = ce.get("market_data", {})
                pe_md  = pe.get("market_data", {})
                chain[strike] = {
                    "CE": {
                        "ltp":    ce_md.get("ltp", 0),
                        "close":  ce_md.get("prev_close_price", ce_md.get("close_price", 0)),
                        "high":   ce_md.get("high_price", 0),
                        "low":    ce_md.get("low_price", 0),
                        "oi":     ce_md.get("oi", 0),
                        "volume": ce_md.get("volume", 0),
                        "iv":     ce.get("option_greeks", {}).get("iv", 0),
                    },
                    "PE": {
                        "ltp":    pe_md.get("ltp", 0),
                        "close":  pe_md.get("prev_close_price", pe_md.get("close_price", 0)),
                        "high":   pe_md.get("high_price", 0),
                        "low":    pe_md.get("low_price", 0),
                        "oi":     pe_md.get("oi", 0),
                        "volume": pe_md.get("volume", 0),
                        "iv":     pe.get("option_greeks", {}).get("iv", 0),
                    },
                    "instrument_key_ce": ce.get("instrument_key", ""),
                    "instrument_key_pe": pe.get("instrument_key", ""),
                }
            print(f"[Chain] {symbol} loaded {len(chain)} strikes")
            return chain
    except Exception as e:
        print(f"[Chain] Error {symbol} {expiry}: {e}")
        return {}


def get_current_and_next_expiry(expiries: list, symbol: str) -> dict:
    """Categorize expiries into current_week, next_week etc."""
    today = date.today()
    result = {"all": expiries, "default": None}
    future = sorted([e for e in expiries if e >= today.isoformat()])
    if not future:
        return result
    result["default"] = future[0]
    sym_up = symbol.upper()
    if sym_up in WEEKLY_SYMBOLS:
        result["current_week"] = future[0] if len(future) > 0 else None
        result["next_week"]    = future[1] if len(future) > 1 else None
        result["far_week"]     = future[2] if len(future) > 2 else None
    else:
        this_m = today.strftime("%Y-%m")
        next_m = (today.replace(day=28) + timedelta(days=4)).strftime("%Y-%m")
        cm = [e for e in future if e.startswith(this_m)]
        nm = [e for e in future if e.startswith(next_m)]
        result["current_month"] = cm[-1] if cm else None
        result["next_month"]    = nm[-1] if nm else None
    return result
