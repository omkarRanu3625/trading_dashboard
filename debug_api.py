"""
debug_api.py — Run this LOCALLY to verify all Upstox API endpoints.
Usage:
    cd trading_dashboard
    .venv\Scripts\activate    (Windows)
    python debug_api.py
"""
import asyncio, httpx, json, os
from dotenv import load_dotenv
from datetime import date, timedelta

load_dotenv()
TOKEN = os.getenv("UPSTOX_ACCESS_TOKEN","")
HDR   = {"Authorization": f"Bearer {TOKEN}", "Accept": "application/json"}

# MCX current month key
M = ["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"]
d = date.today()
CRUDE_KEY = f"MCX_FO|CRUDEOIL{str(d.year)[2:]}{M[d.month-1]}FUT"

print(f"Token: {TOKEN[:40]}...")
print(f"MCX crude key: {CRUDE_KEY}")
print("="*60)

async def test():
    async with httpx.AsyncClient(timeout=20) as c:

        # ── 1. Profile ───────────────────────────────────────────
        print("\n1. USER PROFILE")
        r = await c.get("https://api.upstox.com/v2/user/profile", headers=HDR)
        d = r.json()
        print(f"   HTTP {r.status_code} | name={d.get('data',{}).get('user_name','?')}")

        # ── 2. NIFTY Expiry ──────────────────────────────────────
        print("\n2. NIFTY EXPIRY LIST")
        r = await c.get("https://api.upstox.com/v2/option/contract",
                        params={"instrument_key": "NSE_INDEX|Nifty 50"}, headers=HDR)
        d = r.json()
        expiries = d.get("data", [])
        if isinstance(expiries, dict): expiries = expiries.get("expiry", [])
        print(f"   HTTP {r.status_code} | found {len(expiries)} expiries")
        print(f"   First 4: {expiries[:4]}")

        # ── 3. BANKNIFTY Expiry ──────────────────────────────────
        print("\n3. BANKNIFTY EXPIRY LIST")
        r = await c.get("https://api.upstox.com/v2/option/contract",
                        params={"instrument_key": "NSE_INDEX|Nifty Bank"}, headers=HDR)
        d = r.json()
        expiries_bnk = d.get("data", [])
        if isinstance(expiries_bnk, dict): expiries_bnk = expiries_bnk.get("expiry", [])
        print(f"   HTTP {r.status_code} | found {len(expiries_bnk)} expiries: {expiries_bnk[:3]}")

        # ── 4. SENSEX Expiry ─────────────────────────────────────
        print("\n4. SENSEX EXPIRY (BSE)")
        r = await c.get("https://api.upstox.com/v2/option/contract",
                        params={"instrument_key": "BSE_INDEX|SENSEX"}, headers=HDR)
        d = r.json()
        exp_sx = d.get("data", [])
        if isinstance(exp_sx, dict): exp_sx = exp_sx.get("expiry", [])
        print(f"   HTTP {r.status_code} | found {len(exp_sx)} expiries: {exp_sx[:3]}")

        # ── 5. CRUDEOIL Expiry (MCX) ─────────────────────────────
        print(f"\n5. CRUDEOIL EXPIRY (MCX key={CRUDE_KEY})")
        r = await c.get("https://api.upstox.com/v2/option/contract",
                        params={"instrument_key": CRUDE_KEY}, headers=HDR)
        d = r.json()
        exp_crude = d.get("data", [])
        if isinstance(exp_crude, dict): exp_crude = exp_crude.get("expiry", [])
        print(f"   HTTP {r.status_code} | found {len(exp_crude)}: {exp_crude[:3]}")

        # ── 6. NIFTY Option Chain ────────────────────────────────
        nifty_expiry = expiries[0] if expiries else date.today().isoformat()
        print(f"\n6. NIFTY OPTION CHAIN (expiry={nifty_expiry})")
        r = await c.get("https://api.upstox.com/v2/option/chain",
                        params={"instrument_key": "NSE_INDEX|Nifty 50",
                                "expiry_date": nifty_expiry}, headers=HDR)
        d = r.json()
        rows = d.get("data", [])
        print(f"   HTTP {r.status_code} | {len(rows)} strikes")
        if rows:
            row = rows[len(rows)//2]  # middle row (near ATM)
            strike = row.get("strike_price")
            ce = row.get("call_options",{})
            pe = row.get("put_options",{})
            ce_md = ce.get("market_data",{})
            pe_md = pe.get("market_data",{})
            print(f"   Sample strike {strike}:")
            print(f"   CE key: {ce.get('instrument_key','MISSING')}")
            print(f"   CE ltp={ce_md.get('ltp',0)} close={ce_md.get('prev_close_price',0)} high={ce_md.get('high_price',0)}")
            print(f"   PE key: {pe.get('instrument_key','MISSING')}")
            print(f"   PE ltp={pe_md.get('ltp',0)} close={pe_md.get('prev_close_price',0)} high={pe_md.get('high_price',0)}")

        # ── 7. Market quote NIFTY + RELIANCE ────────────────────
        print("\n7. MARKET QUOTE (NIFTY + RELIANCE ISIN)")
        r = await c.get("https://api.upstox.com/v2/market-quote/quotes",
                        params={"instrument_key": "NSE_INDEX|Nifty 50,NSE_EQ|INE002A01018"},
                        headers=HDR)
        d = r.json()
        for k, v in d.get("data",{}).items():
            ohlc = v.get("ohlc",{})
            print(f"   {k}: ltp={v.get('last_price',0)} close={ohlc.get('close',0)} high={ohlc.get('high',0)}")

        # ── 8. OHLC quote stocks ─────────────────────────────────
        print("\n8. OHLC QUOTE (RELIANCE + TCS ISIN)")
        r = await c.get("https://api.upstox.com/v2/market-quote/ohlc",
                        params={"instrument_key": "NSE_EQ|INE002A01018,NSE_EQ|INE467B01029",
                                "interval": "1d"}, headers=HDR)
        d = r.json()
        print(f"   HTTP {r.status_code}")
        for k, v in d.get("data",{}).items():
            ohlc = v.get("ohlc",{})
            print(f"   {k}: ltp={v.get('last_price',0)} close={ohlc.get('close',0)}")

        # ── 9. Test specific CE/PE option quote ──────────────────
        if rows and len(rows) > 0:
            mid_row = rows[len(rows)//2]
            ce_key = mid_row.get("call_options",{}).get("instrument_key","")
            pe_key = mid_row.get("put_options",{}).get("instrument_key","")
            if ce_key and pe_key:
                print(f"\n9. OPTION QUOTE (CE+PE near ATM)")
                r = await c.get("https://api.upstox.com/v2/market-quote/quotes",
                                params={"instrument_key": f"{ce_key},{pe_key}"}, headers=HDR)
                d = r.json()
                print(f"   HTTP {r.status_code}")
                for k, v in d.get("data",{}).items():
                    ohlc = v.get("ohlc",{})
                    print(f"   {k[:40]}: ltp={v.get('last_price',0)} close={ohlc.get('close',0)}")

        print("\n" + "="*60)
        print("✓ Debug complete. Check each endpoint's HTTP code and data.")
        print("  If ltp=0 for options — market is closed (weekend/holiday).")
        print("  prev_close_price is used for LOC calculations in that case.")

asyncio.run(test())
