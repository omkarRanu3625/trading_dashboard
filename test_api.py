"""
test_api.py — Run this locally to diagnose all Upstox API issues
Usage: python test_api.py
"""
import asyncio, json, sys
import httpx

TOKEN = "eyJ0eXAiOiJKV1QiLCJrZXlfaWQiOiJza192MS4wIiwiYWxnIjoiSFMyNTYifQ.eyJzdWIiOiI1QUNaTjIiLCJqdGkiOiI2OWM1ZmQzNzEzZDE4YTVmYmU3N2JiNDciLCJpc011bHRpQ2xpZW50IjpmYWxzZSwiaXNQbHVzUGxhbiI6dHJ1ZSwiaWF0IjoxNzc0NTgzMDk1LCJpc3MiOiJ1ZGFwaS1nYXRld2F5LXNlcnZpY2UiLCJleHAiOjE3NzQ2NDg4MDB9.rKFEw_3L7bHRMOr4xK0VqG9Kx6uItfwojd25hz8pAA4"
HDR = {"Authorization": f"Bearer {TOKEN}", "Accept": "application/json"}
BASE = "https://api.upstox.com/v2"

results = {}

async def get(path, params=None, label=""):
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(f"{BASE}{path}", headers=HDR, params=params or {})
        print(f"\n{'='*60}")
        print(f"[{label}] {path} → HTTP {r.status_code}")
        try:
            d = r.json()
            print(json.dumps(d, indent=2)[:1500])
            results[label] = {"status": r.status_code, "data": d}
            return d
        except:
            print(r.text[:500])
            results[label] = {"status": r.status_code, "raw": r.text[:200]}
            return {}

async def main():
    print("RAIMA Markets — Upstox API Diagnostics")
    print("="*60)

    # 1. Profile
    d = await get("/user/profile", label="Profile")
    if d.get("status") == "error":
        print("\n❌ TOKEN INVALID OR EXPIRED. Get fresh token from Upstox.")
        return

    # 2. Spot quotes — Indices
    index_keys = [
        "NSE_INDEX|Nifty 50", "NSE_INDEX|Nifty Bank",
        "BSE_INDEX|SENSEX", "NSE_INDEX|Nifty Fin Service",
    ]
    await get("/market-quote/quotes",
              {"instrument_key": ",".join(index_keys)},
              label="Index Quotes")

    # 3. MCX commodity — test different month formats
    from datetime import date, timedelta
    MONTHS = ["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"]
    d = date.today()
    nm = date.today() + timedelta(days=32)
    curr_mcx = [
        f"MCX_FO|CRUDEOIL{str(d.year)[2:]}{MONTHS[d.month-1]}FUT",
        f"MCX_FO|NATURALGAS{str(d.year)[2:]}{MONTHS[d.month-1]}FUT",
        f"MCX_FO|GOLD{str(d.year)[2:]}{MONTHS[d.month-1]}FUT",
        f"MCX_FO|SILVER{str(nm.year)[2:]}{MONTHS[nm.month-1]}FUT",  # silver is next month
    ]
    print(f"\n[MCX] Testing keys: {curr_mcx}")
    await get("/market-quote/quotes",
              {"instrument_key": ",".join(curr_mcx)},
              label="MCX Quotes")

    # 4. NSE EQ stocks — test ISIN format
    isin_keys = [
        "NSE_EQ|INE002A01018",  # RELIANCE
        "NSE_EQ|INE467B01029",  # TCS
        "NSE_EQ|INE040A01034",  # HDFCBANK
        "NSE_EQ|INE062A01020",  # SBIN
    ]
    await get("/market-quote/quotes",
              {"instrument_key": ",".join(isin_keys)},
              label="Stock Quotes (ISIN)")

    # 5. Expiry list for NIFTY
    d = await get("/option/contract",
                  {"instrument_key": "NSE_INDEX|Nifty 50"},
                  label="NIFTY Expiries")

    # 6. Option chain for NIFTY — current expiry
    expiries = []
    if isinstance(d.get("data"), list):
        expiries = sorted(d["data"])
    elif isinstance(d.get("data"), dict):
        expiries = sorted(d["data"].get("expiry", []))

    if expiries:
        exp = expiries[0]
        print(f"\n[Chain] Using expiry: {exp}")
        chain_d = await get("/option/chain",
                            {"instrument_key": "NSE_INDEX|Nifty 50", "expiry_date": exp},
                            label=f"NIFTY Option Chain ({exp})")
        # Show first few strikes
        rows = chain_d.get("data", [])
        if rows:
            mid = len(rows) // 2
            sample = rows[max(0, mid-2):mid+3]
            print(f"\n[Chain Sample] {len(rows)} strikes total. Middle 5:")
            for row in sample:
                ce = row.get("call_options", {}).get("market_data", {})
                pe = row.get("put_options", {}).get("market_data", {})
                ce_key = row.get("call_options", {}).get("instrument_key", "")
                pe_key = row.get("put_options", {}).get("instrument_key", "")
                print(f"  Strike {row.get('strike_price')}: "
                      f"CE ltp={ce.get('ltp',0)} close={ce.get('prev_close_price',0)} key={ce_key[-20:] if ce_key else 'none'} | "
                      f"PE ltp={pe.get('ltp',0)} close={pe.get('prev_close_price',0)} key={pe_key[-20:] if pe_key else 'none'}")

    # 7. SENSEX expiry
    await get("/option/contract",
              {"instrument_key": "BSE_INDEX|SENSEX"},
              label="SENSEX Expiries")

    # 8. MCX CRUDEOIL expiry
    await get("/option/contract",
              {"instrument_key": curr_mcx[0]},
              label="CRUDEOIL Expiries")

    # 9. OHLC for stocks
    await get("/market-quote/ohlc",
              {"instrument_key": ",".join(isin_keys), "interval": "1d"},
              label="Stock OHLC (ISIN)")

    # 10. Save full results
    with open("api_test_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n\n{'='*60}")
    print("✅ Full results saved to api_test_results.json")
    print("Share this file if you need further debugging.")

asyncio.run(main())
