"""
Run this LOCALLY on your machine:
  python diagnose.py

Tests every Upstox endpoint and shows exact response data.
"""
import asyncio, json, sys, os
from datetime import date, timedelta

try:
    import httpx
except ImportError:
    print("Installing httpx..."); os.system("pip install httpx")
    import httpx

TOKEN = os.getenv("UPSTOX_ACCESS_TOKEN", "")
if not TOKEN:
    # Try .env file
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        for line in open(env_path):
            if line.startswith("UPSTOX_ACCESS_TOKEN="):
                TOKEN = line.split("=", 1)[1].strip().strip('"')
if not TOKEN:
    print("Paste your access token:")
    TOKEN = input("> ").strip()

HDR = {"Authorization": f"Bearer {TOKEN}", "Accept": "application/json"}
M   = ["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"]

async def run():
    async with httpx.AsyncClient(timeout=15) as c:

        def show(label, r, keys=None):
            print(f"\n{'='*55}")
            print(f"  {label}  HTTP {r.status_code}")
            print(f"{'='*55}")
            if r.status_code == 200:
                d = r.json().get("data", {})
                if keys:
                    for k in keys:
                        v = d
                        for part in k.split("."):
                            v = (v or {}).get(part)
                        print(f"  {k} = {v}")
                else:
                    print(json.dumps(d, indent=2)[:600])
            else:
                print(f"  ERROR: {r.text[:400]}")
            return r

        # ── 1. Profile ─────────────────────────────────────────────
        r = await c.get("https://api.upstox.com/v2/user/profile", headers=HDR)
        show("PROFILE", r)

        # ── 2. All index quotes ────────────────────────────────────
        idx_keys = "NSE_INDEX|Nifty 50,NSE_INDEX|Nifty Bank,NSE_INDEX|Nifty Fin Service,BSE_INDEX|SENSEX,BSE_INDEX|BANKEX"
        r = await c.get("https://api.upstox.com/v2/market-quote/quotes",
                        params={"instrument_key": idx_keys}, headers=HDR)
        print(f"\n{'='*55}\n  INDEX QUOTES  HTTP {r.status_code}\n{'='*55}")
        if r.status_code == 200:
            for k, v in r.json().get("data", {}).items():
                ohlc = v.get("ohlc", {})
                print(f"  {k}: ltp={v.get('last_price')} O={ohlc.get('open')} H={ohlc.get('high')} L={ohlc.get('low')} C={ohlc.get('close')}")
        else:
            print(f"  {r.text[:300]}")

        # ── 3. MCX keys (test current + next month) ────────────────
        today = date.today()
        nm    = today.month % 12 + 1
        ny    = today.year + (1 if today.month == 12 else 0)
        mcx_tests = []
        for sym in ["CRUDEOIL", "NATURALGAS", "GOLD", "SILVER"]:
            mcx_tests.append(f"MCX_FO|{sym}{str(today.year)[2:]}{M[today.month-1]}FUT")
            mcx_tests.append(f"MCX_FO|{sym}{str(ny)[2:]}{M[nm-1]}FUT")
        # Also try APR specifically
        mcx_tests.append("MCX_FO|CRUDEOIL26APRFUT")
        mcx_tests.append("MCX_FO|NATURALGAS26APRFUT")

        print(f"\n{'='*55}\n  MCX QUOTES\n{'='*55}")
        for key in mcx_tests:
            r = await c.get("https://api.upstox.com/v2/market-quote/quotes",
                            params={"instrument_key": key}, headers=HDR)
            if r.status_code == 200:
                for k, v in r.json().get("data", {}).items():
                    print(f"  ✓ {key}: ltp={v.get('last_price')} close={v.get('ohlc',{}).get('close')}")
            else:
                print(f"  ✗ {key}: HTTP {r.status_code}")

        # ── 4. Reliance ISIN key ───────────────────────────────────
        r = await c.get("https://api.upstox.com/v2/market-quote/quotes",
                        params={"instrument_key": "NSE_EQ|INE002A01018"}, headers=HDR)
        print(f"\n{'='*55}\n  RELIANCE ISIN KEY  HTTP {r.status_code}\n{'='*55}")
        if r.status_code == 200:
            for k, v in r.json().get("data", {}).items():
                ohlc = v.get("ohlc", {})
                print(f"  resp_key={k}")
                print(f"  ltp={v.get('last_price')} O={ohlc.get('open')} H={ohlc.get('high')} L={ohlc.get('low')} C={ohlc.get('close')}")
        else:
            print(f"  {r.text[:300]}")

        # ── 5. OHLC endpoint ──────────────────────────────────────
        r = await c.get("https://api.upstox.com/v2/market-quote/ohlc",
                        params={"instrument_key": "NSE_EQ|INE002A01018,NSE_INDEX|Nifty 50", "interval": "1d"},
                        headers=HDR)
        print(f"\n{'='*55}\n  OHLC ENDPOINT  HTTP {r.status_code}\n{'='*55}")
        if r.status_code == 200:
            for k, v in r.json().get("data", {}).items():
                ohlc = v.get("ohlc", {})
                print(f"  {k}: ltp={v.get('last_price')} O={ohlc.get('open')} H={ohlc.get('high')} L={ohlc.get('low')} C={ohlc.get('close')}")
        else:
            print(f"  {r.text[:300]}")

        # ── 6. Expiry lists ────────────────────────────────────────
        expiry_map = {}
        print(f"\n{'='*55}\n  EXPIRY LISTS\n{'='*55}")
        for sym, key in [("NIFTY","NSE_INDEX|Nifty 50"), ("BANKNIFTY","NSE_INDEX|Nifty Bank"),
                          ("SENSEX","BSE_INDEX|SENSEX"), ("CRUDEOIL","MCX_FO|CRUDEOIL26APRFUT")]:
            r = await c.get("https://api.upstox.com/v2/option/contract",
                            params={"instrument_key": key}, headers=HDR)
            if r.status_code == 200:
                raw = r.json().get("data", [])
                if isinstance(raw, dict): raw = raw.get("expiry", [])
                expiries = sorted([e for e in raw if isinstance(e, str)])
                expiry_map[sym] = expiries
                print(f"  {sym}: {expiries[:5]}")
            else:
                print(f"  {sym}: HTTP {r.status_code} → {r.text[:100]}")

        # ── 7. Option chain (Nifty) ────────────────────────────────
        nifty_expiries = expiry_map.get("NIFTY", [])
        if not nifty_expiries:
            # fallback to calculated
            d = today
            for _ in range(5):
                days = (3 - d.weekday()) % 7 or 7
                d += timedelta(days=days)
                nifty_expiries.append(d.isoformat())

        for exp in nifty_expiries[:2]:
            r = await c.get("https://api.upstox.com/v2/option/chain",
                            params={"instrument_key": "NSE_INDEX|Nifty 50", "expiry_date": exp},
                            headers=HDR)
            print(f"\n{'='*55}\n  NIFTY OPTION CHAIN ({exp})  HTTP {r.status_code}\n{'='*55}")
            if r.status_code == 200:
                rows = r.json().get("data", [])
                print(f"  Total strikes: {len(rows)}")
                # Get spot price
                sr = await c.get("https://api.upstox.com/v2/market-quote/quotes",
                                 params={"instrument_key": "NSE_INDEX|Nifty 50"}, headers=HDR)
                spot = 0
                if sr.status_code == 200:
                    for k, v in sr.json().get("data", {}).items():
                        spot = v.get("last_price", 0)
                print(f"  Spot LTP: {spot}")

                if rows and spot:
                    # ATM
                    atm = round(round(spot / 50) * 50, 2)
                    itm2_ce = atm - 100
                    itm2_pe = atm + 100
                    print(f"  ATM={atm}  ITM-2 CE@{itm2_ce}  PE@{itm2_pe}")

                    for row in rows:
                        s = float(row.get("strike_price", 0))
                        if s in [itm2_ce, itm2_pe, atm]:
                            label = "ATM" if s == atm else ("CE ITM-2" if s == itm2_ce else "PE ITM-2")
                            ce = row.get("call_options", {}); pe = row.get("put_options", {})
                            ce_md = ce.get("market_data", {}); pe_md = pe.get("market_data", {})
                            print(f"\n  [{label}] Strike {s}:")
                            print(f"    CE: ltp={ce_md.get('ltp',0)} close={ce_md.get('prev_close_price',0)} "
                                  f"H={ce_md.get('high_price',0)} L={ce_md.get('low_price',0)} "
                                  f"iv={ce.get('option_greeks',{}).get('iv',0)}")
                            print(f"    CE key: {ce.get('instrument_key','')}")
                            print(f"    PE: ltp={pe_md.get('ltp',0)} close={pe_md.get('prev_close_price',0)} "
                                  f"H={pe_md.get('high_price',0)} L={pe_md.get('low_price',0)}")
                            print(f"    PE key: {pe.get('instrument_key','')}")
            else:
                print(f"  {r.text[:300]}")

        # ── 8. WebSocket auth check ────────────────────────────────
        r = await c.get("https://api.upstox.com/v3/feed/market-data-feed/authorize", headers=HDR)
        print(f"\n{'='*55}\n  WS AUTH CHECK  HTTP {r.status_code}\n{'='*55}")
        if r.status_code == 200:
            d = r.json()
            ws_url = d.get("data", {}).get("authorized_redirect_uri", "")
            print(f"  WS URL: {ws_url[:80]}")
        else:
            print(f"  {r.text[:200]}")

        print(f"\n{'='*55}")
        print("  DIAGNOSTIC COMPLETE")
        print(f"{'='*55}")
        print("\n  Paste the output above back to Claude for fixes.\n")

asyncio.run(run())
