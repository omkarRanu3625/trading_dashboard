"""Mock feed — simulates live Upstox data for local dev/testing"""
import asyncio, json, math, random, time

MOCK_SYMBOLS = {
    "NSE_INDEX|Nifty 50":          {"base":23200,"name":"NIFTY"},
    "NSE_INDEX|Nifty Bank":        {"base":48500,"name":"BANKNIFTY"},
    "NSE_INDEX|Nifty Fin Service": {"base":21800,"name":"FINNIFTY"},
    "NSE_INDEX|NIFTY MID SELECT":  {"base":11200,"name":"MIDCPNIFTY"},
    "NSE_INDEX|Nifty Next 50":     {"base":64000,"name":"NXTFTY"},
    "BSE_INDEX|SENSEX":            {"base":76800,"name":"SENSEX"},
    "BSE_INDEX|BANKEX":            {"base":58000,"name":"BANKEX"},
    "MCX_FO|CRUDEOIL25APRFUT":    {"base":7320,"name":"CRUDEOIL"},
    "MCX_FO|NATURALGAS25APRFUT":  {"base":285,"name":"NATGAS"},
    "MCX_FO|GOLD25APRFUT":        {"base":93400,"name":"GOLD"},
    "MCX_FO|SILVER25MAYFUT":      {"base":97200,"name":"SILVER"},
    "NSE_EQ|RELIANCE":  {"base":1380}, "NSE_EQ|TCS":       {"base":3520},
    "NSE_EQ|HDFCBANK":  {"base":1685}, "NSE_EQ|INFY":      {"base":1540},
    "NSE_EQ|ICICIBANK": {"base":1310}, "NSE_EQ|BHARTIARTL":{"base":1720},
    "NSE_EQ|SBIN":      {"base":785},  "NSE_EQ|ITC":       {"base":415},
    "NSE_EQ|KOTAKBANK": {"base":1890}, "NSE_EQ|LT":        {"base":3320},
    "NSE_EQ|AXISBANK":  {"base":1145}, "NSE_EQ|BAJFINANCE":{"base":6890},
    "NSE_EQ|WIPRO":     {"base":305},  "NSE_EQ|TECHM":     {"base":1480},
    "NSE_EQ|NTPC":      {"base":335},  "NSE_EQ|SUNPHARMA": {"base":1780},
    "NSE_EQ|TATASTEEL": {"base":168},  "NSE_EQ|MARUTI":    {"base":11200},
    "NSE_EQ|TITAN":     {"base":3450}, "NSE_EQ|ONGC":      {"base":267},
    "NSE_EQ|PFC":       {"base":398},  "NSE_EQ|DRREDDY":   {"base":1245},
    "NSE_EQ|ADANIENT":  {"base":2450}, "NSE_EQ|ADANIPORTS":{"base":1230},
    "NSE_EQ|POWERGRID": {"base":302},  "NSE_EQ|COALINDIA": {"base":388},
    "NSE_EQ|DLF":       {"base":692},  "NSE_EQ|TATAPOWER": {"base":368},
    "NSE_EQ|JSWSTEEL":  {"base":920},  "NSE_EQ|DALBHARAT": {"base":1850},
}

# ITM-2 option mock data per symbol
MOCK_OPTIONS = {
    "NIFTY":      {"ce_step":50,  "ce_premium":580,  "pe_premium":520},
    "BANKNIFTY":  {"ce_step":100, "ce_premium":1240, "pe_premium":1180},
    "FINNIFTY":   {"ce_step":50,  "ce_premium":420,  "pe_premium":390},
    "MIDCPNIFTY": {"ce_step":25,  "ce_premium":380,  "pe_premium":350},
    "SENSEX":     {"ce_step":100, "ce_premium":1820, "pe_premium":1750},
    "BANKEX":     {"ce_step":100, "ce_premium":890,  "pe_premium":840},
    "CRUDEOIL":   {"ce_step":50,  "ce_premium":145,  "pe_premium":130},
    "NATURALGAS": {"ce_step":10,  "ce_premium":8.5,  "pe_premium":7.8},
    "GOLD":       {"ce_step":100, "ce_premium":520,  "pe_premium":480},
    "SILVER":     {"ce_step":1000,"ce_premium":1200, "pe_premium":1100},
}

SYM_TO_KEY = {
    "NIFTY":"NSE_INDEX|Nifty 50","BANKNIFTY":"NSE_INDEX|Nifty Bank",
    "FINNIFTY":"NSE_INDEX|Nifty Fin Service","MIDCPNIFTY":"NSE_INDEX|NIFTY MID SELECT",
    "SENSEX":"BSE_INDEX|SENSEX","BANKEX":"BSE_INDEX|BANKEX",
    "CRUDEOIL":"MCX_FO|CRUDEOIL25APRFUT","NATURALGAS":"MCX_FO|NATURALGAS25APRFUT",
    "GOLD":"MCX_FO|GOLD25APRFUT","SILVER":"MCX_FO|SILVER25MAYFUT",
}
SPOT_KEY_TO_SYM = {v:k for k,v in SYM_TO_KEY.items()}

prices = {k: v["base"] for k, v in MOCK_SYMBOLS.items()}
closes = {k: v["base"] for k, v in MOCK_SYMBOLS.items()}
opt_prices = {sym: {"ce_ltp": d["ce_premium"], "pe_ltp": d["pe_premium"]} 
              for sym, d in MOCK_OPTIONS.items()}

async def start_mock_feed(broadcast_fn):
    print("[Mock] Starting mock feed...")
    t = 0
    while True:
        await asyncio.sleep(0.8)
        t += 1
        feeds = {}
        ts = int(time.time() * 1000)

        # Update spot prices
        for key, info in MOCK_SYMBOLS.items():
            base = info["base"]
            drift = math.sin(t * 0.03 + base * 0.001) * 0.004
            noise = (random.random() - 0.5) * 0.002
            prices[key] = max(base * 0.85, prices[key] * (1 + drift + noise))
            ltp = round(prices[key], 2)
            cp = closes.get(key, ltp)
            feeds[key] = {
                "ltpc": {"ltp": ltp, "cp": cp},
                "efeed": {
                    "ltp": ltp, "cp": cp,
                    "high": round(ltp * 1.005, 2),
                    "low":  round(ltp * 0.995, 2),
                    "uc":   round(ltp * 1.02, 2),
                    "lc":   round(ltp * 0.98, 2),
                }
            }

        # Broadcast spot data first
        await broadcast_fn({"type": "live_feed", "feeds": feeds, "currentTs": str(ts)})

        # Simulate LOC engine updates by injecting loc_update messages
        # (In real mode, LOC engine does this. In mock, we simulate it.)
        if t % 3 == 0:  # Every ~2.4s update options
            for sym, opts in MOCK_OPTIONS.items():
                spot_key = SYM_TO_KEY.get(sym)
                if not spot_key: continue
                ltp = prices.get(spot_key, opts.get("ce_step", 50) * 460)
                step = opts["ce_step"]
                atm = round(round(ltp / step) * step, 2)
                ce_s = atm - 2 * step
                pe_s = atm + 2 * step
                base_ce = opts["ce_premium"]; base_pe = opts["pe_premium"]
                noise = (random.random() - 0.5) * 0.05
                ce_ltp = round(base_ce * (1 + noise + math.sin(t * 0.05) * 0.03), 2)
                pe_ltp = round(base_pe * (1 + noise - math.sin(t * 0.05) * 0.03), 2)
                ce_cl = round(base_ce * 0.97, 2); pe_cl = round(base_pe * 0.97, 2)
                ce_hi = round(ce_ltp * 1.02, 2); ce_lo = round(ce_ltp * 0.95, 2)
                pe_hi = round(pe_ltp * 1.02, 2); pe_lo = round(pe_ltp * 0.95, 2)
                cp = closes.get(spot_key, ltp)
                hi = round(ltp * 1.005, 2); lo = round(ltp * 0.995, 2)

                # Use the same 25-formula calc
                from backend.main import calc_loc_25
                try:
                    loc = calc_loc_25(ltp, cp, hi, lo, ce_ltp, ce_cl, ce_hi, ce_lo,
                                      pe_ltp, pe_cl, pe_hi, pe_lo)
                    loc.update({"symbol": sym, "ce_strike": ce_s, "pe_strike": pe_s,
                                "ce_ltp": ce_ltp, "pe_ltp": pe_ltp,
                                "ce_iv": round(18 + noise * 10, 1),
                                "pe_iv": round(20 + noise * 10, 1), "expiry": "2025-03-27"})
                    await broadcast_fn({"type": "live_feed", "feeds": {},
                                        "currentTs": str(ts), "loc_results": {sym: loc}})
                except Exception as e:
                    pass

        # Market info every 30s
        if t % 37 == 0:
            await broadcast_fn({"type": "market_info", "marketInfo": {
                "segmentStatus": {"NSE_CM": "NORMAL_OPEN", "BSE_CM": "NORMAL_OPEN",
                                   "MCX_FO": "NORMAL_OPEN", "NSE_FO": "NORMAL_OPEN"}}})
