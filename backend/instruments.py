"""
instruments.py — Upstox Instrument & Option Chain Helper
Includes fallback expiry calculation when API returns empty (weekends/holidays)
"""
import asyncio, json, time
from datetime import date, timedelta
from typing import Optional
import httpx

UPSTOX_OPTION_CHAIN = "https://api.upstox.com/v2/option/chain"
UPSTOX_EXPIRY_URL   = "https://api.upstox.com/v2/option/contract"
UPSTOX_MARKET_QUOTE = "https://api.upstox.com/v2/market-quote/quotes"

STRIKE_STEPS = {
    "NIFTY":50,"BANKNIFTY":100,"FINNIFTY":50,"MIDCPNIFTY":25,
    "SENSEX":100,"BANKEX":100,"CRUDEOIL":50,"NATURALGAS":10,
    "GOLD":100,"SILVER":1000,"COPPER":5,
}

def _mcx_fut(sym: str, months_ahead: int = 0) -> str:
    MONTHS = ["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"]
    d = date.today() + timedelta(days=30 * months_ahead)
    return f"MCX_FO|{sym}{str(d.year)[2:]}{MONTHS[d.month-1]}FUT"

SPOT_KEYS = {
    "NIFTY":      "NSE_INDEX|Nifty 50",
    "BANKNIFTY":  "NSE_INDEX|Nifty Bank",
    "FINNIFTY":   "NSE_INDEX|Nifty Fin Service",
    "MIDCPNIFTY": "NSE_INDEX|NIFTY MID SELECT",
    "SENSEX":     "BSE_INDEX|SENSEX",
    "BANKEX":     "BSE_INDEX|BANKEX",
    "CRUDEOIL":   _mcx_fut("CRUDEOIL"),
    "NATURALGAS": _mcx_fut("NATURALGAS"),
    "GOLD":       _mcx_fut("GOLD"),
    "SILVER":     _mcx_fut("SILVER"),
}

OPTION_EXCHANGE = {
    "NIFTY":"NSE","BANKNIFTY":"NSE","FINNIFTY":"NSE","MIDCPNIFTY":"NSE",
    "SENSEX":"BSE","BANKEX":"BSE","CRUDEOIL":"MCX","NATURALGAS":"MCX",
    "GOLD":"MCX","SILVER":"MCX",
}
WEEKLY_SYMBOLS  = {"NIFTY","BANKNIFTY","FINNIFTY","MIDCPNIFTY","SENSEX","BANKEX","CRUDEOIL","NATURALGAS"}
MONTHLY_SYMBOLS = {"GOLD","SILVER","COPPER"}


def get_atm_strike(spot: float, symbol: str) -> float:
    step = STRIKE_STEPS.get(symbol.upper(), 50)
    return round(round(spot / step) * step, 2)


def get_itm2_strikes(spot: float, symbol: str) -> tuple:
    step = STRIKE_STEPS.get(symbol.upper(), 50)
    atm  = get_atm_strike(spot, symbol)
    return atm - 2*step, atm + 2*step


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Accept": "application/json"}


# ── Fallback expiry calculation (no API needed) ──────────────────

def _next_thursday(from_date: date = None) -> date:
    """Get next Thursday on or after from_date."""
    d = from_date or date.today()
    days = (3 - d.weekday()) % 7
    if days == 0 and d.weekday() != 3:
        days = 7
    return d + timedelta(days=days if days > 0 else 7)

def _last_thursday_of_month(year: int, month: int) -> date:
    """Last Thursday of given month."""
    if month == 12:
        nm = date(year+1, 1, 1)
    else:
        nm = date(year, month+1, 1)
    last = nm - timedelta(days=1)
    off  = (last.weekday() - 3) % 7
    return last - timedelta(days=off)

def calculate_expiries_fallback(symbol: str, num_weeks: int = 8) -> list:
    """
    Calculate upcoming expiry dates without API call.
    NSE weekly: every Thursday
    MCX/monthly: last Thursday of each month
    """
    today   = date.today()
    sym_up  = symbol.upper()
    expiries = []

    if sym_up in MONTHLY_SYMBOLS:
        # Monthly expiry — last Thursday of next few months
        for i in range(3):
            m = today.month + i
            y = today.year + (m - 1) // 12
            m = ((m - 1) % 12) + 1
            lt = _last_thursday_of_month(y, m)
            if lt >= today:
                expiries.append(lt.isoformat())
    else:
        # Weekly expiry — next N Thursdays
        d = today
        count = 0
        while count < num_weeks:
            # Find next Thursday
            days_to_thu = (3 - d.weekday()) % 7
            if days_to_thu == 0:
                days_to_thu = 7
            d = d + timedelta(days=days_to_thu)
            expiries.append(d.isoformat())
            count += 1

    return sorted(set(expiries))


async def fetch_expiry_list(symbol: str, access_token: str) -> list:
    """
    Fetch expiry dates from Upstox API.
    Falls back to calculated expiries if API returns empty (weekends/holidays).
    """
    spot_key = SPOT_KEYS.get(symbol.upper(), "")
    if not spot_key:
        print(f"[Expiry] No spot key for {symbol}, using fallback")
        return calculate_expiries_fallback(symbol)

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                UPSTOX_EXPIRY_URL,
                params={"instrument_key": spot_key},
                headers=_headers(access_token)
            )
            print(f"[Expiry] {symbol} → HTTP {r.status_code}")

            if r.status_code == 200:
                d = r.json()
                expiries = d.get("data", [])
                if isinstance(expiries, dict):
                    expiries = expiries.get("expiry", [])

                if isinstance(expiries, list) and expiries:
                    result = sorted([e for e in expiries if isinstance(e, str)])
                    print(f"[Expiry] {symbol} API: {len(result)} dates → {result[:3]}")
                    return result
                else:
                    print(f"[Expiry] {symbol} API empty — using calculated fallback")
            else:
                print(f"[Expiry] {symbol} HTTP {r.status_code} — using fallback")

    except Exception as e:
        print(f"[Expiry] {symbol} error: {e} — using fallback")

    # Fallback: calculate from today
    fallback = calculate_expiries_fallback(symbol)
    print(f"[Expiry] {symbol} fallback: {fallback[:3]}")
    return fallback


async def fetch_option_chain(symbol: str, expiry: str, access_token: str) -> dict:
    """
    Fetch full option chain for symbol+expiry.
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
            print(f"[Chain] {symbol} {expiry} → HTTP {r.status_code}")
            if r.status_code != 200:
                print(f"[Chain] Error: {r.text[:200]}")
                return {}

            data = r.json()
            rows = data.get("data", [])
            if not rows:
                print(f"[Chain] {symbol} {expiry} — empty chain")
                return {}

            chain = {}
            for row in rows:
                strike = float(row.get("strike_price", 0))
                ce     = row.get("call_options", {})
                pe     = row.get("put_options", {})
                ce_md  = ce.get("market_data", {})
                pe_md  = pe.get("market_data", {})

                def _price(d, *keys):
                    for k in keys:
                        v = d.get(k, 0)
                        if v: return v
                    return 0

                chain[strike] = {
                    "CE": {
                        "ltp":    _price(ce_md, "ltp", "last_price"),
                        "close":  _price(ce_md, "prev_close_price", "close_price", "close"),
                        "high":   _price(ce_md, "high_price", "high"),
                        "low":    _price(ce_md, "low_price", "low"),
                        "oi":     _price(ce_md, "oi", "open_interest"),
                        "volume": _price(ce_md, "volume"),
                        "iv":     ce.get("option_greeks", {}).get("iv", 0),
                    },
                    "PE": {
                        "ltp":    _price(pe_md, "ltp", "last_price"),
                        "close":  _price(pe_md, "prev_close_price", "close_price", "close"),
                        "high":   _price(pe_md, "high_price", "high"),
                        "low":    _price(pe_md, "low_price", "low"),
                        "oi":     _price(pe_md, "oi", "open_interest"),
                        "volume": _price(pe_md, "volume"),
                        "iv":     pe.get("option_greeks", {}).get("iv", 0),
                    },
                    "instrument_key_ce": ce.get("instrument_key", ""),
                    "instrument_key_pe": pe.get("instrument_key", ""),
                }

            print(f"[Chain] {symbol} {expiry}: {len(chain)} strikes loaded")
            return chain

    except Exception as e:
        print(f"[Chain] Error {symbol} {expiry}: {e}")
        return {}


def get_current_and_next_expiry(expiries: list, symbol: str) -> dict:
    """Categorize expiries with labels."""
    today  = date.today()
    result = {"all": expiries, "default": None}
    future = sorted([e for e in expiries if e >= today.isoformat()])
    if not future:
        return result

    result["default"] = future[0]
    sym_up = symbol.upper()

    if sym_up in MONTHLY_SYMBOLS:
        this_m = today.strftime("%Y-%m")
        next_m = (today.replace(day=28) + timedelta(days=4)).strftime("%Y-%m")
        cm = [e for e in future if e.startswith(this_m)]
        nm = [e for e in future if e.startswith(next_m)]
        result["current_month"] = cm[-1] if cm else None
        result["next_month"]    = nm[-1] if nm else None
    else:
        result["current_week"]  = future[0] if len(future) > 0 else None
        result["next_week"]     = future[1] if len(future) > 1 else None
        result["far_week"]      = future[2] if len(future) > 2 else None

    return result
