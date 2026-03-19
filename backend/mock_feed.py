"""
mock_feed.py – Standalone mock market data server for development.
Simulates realistic price movements without Upstox credentials.

Run standalone:  python mock_feed.py
Or import and call start_mock_feed(broadcast_fn) from main.py
"""

import asyncio
import json
import random
import time
from typing import Callable

# Realistic base prices (as of early 2025)
MOCK_INDICES = {
    "NSE_INDEX|Nifty 50":        {"base": 23170.45, "name": "NIFTY (NSE)",       "category": "index"},
    "NSE_INDEX|Nifty Bank":      {"base": 53769.90, "name": "BANKNIFTY (NSE)",   "category": "index"},
    "NSE_INDEX|Nifty Fin Service":{"base": 25154.85, "name": "FINNIFTY (NSE)",   "category": "index"},
    "NSE_INDEX|NIFTY MID SELECT":{"base": 12630.05, "name": "MIDCPNIFTY (NSE)",  "category": "index"},
    "BSE_INDEX|SENSEX":          {"base": 74563.92, "name": "SENSEX (BSE)",      "category": "index"},
    "BSE_INDEX|BANKEX":          {"base": 60462.88, "name": "BANKEX (BSE)",      "category": "index"},
}

MOCK_COMMODITIES = {
    "MCX_FO|CRUDEOIL":    {"base": 9076.00, "name": "CRUDEOIL (MCX)", "category": "commodity"},
    "MCX_FO|GOLD":        {"base": 158400,  "name": "GOLD (MCX)",     "category": "commodity"},
    "MCX_FO|SILVER":      {"base": 259279,  "name": "SILVER (MCX)",   "category": "commodity"},
    "MCX_FO|NATURALGAS":  {"base": 292.20,  "name": "NATURALGAS (MCX)","category": "commodity"},
    "MCX_FO|COPPER":      {"base": 1186.00, "name": "COPPER (MCX)",   "category": "commodity"},
}

MOCK_STOCKS = {
    "NSE_EQ|RELIANCE":    {"base": 2850.00, "name": "RELIANCE",      "category": "stock"},
    "NSE_EQ|TCS":         {"base": 3950.00, "name": "TCS",           "category": "stock"},
    "NSE_EQ|INFY":        {"base": 1780.00, "name": "INFY",          "category": "stock"},
    "NSE_EQ|HDFCBANK":    {"base": 1720.00, "name": "HDFCBANK",      "category": "stock"},
    "NSE_EQ|ICICIBANK":   {"base": 1290.00, "name": "ICICIBANK",     "category": "stock"},
    "NSE_EQ|DALBHARAT":   {"base": 1890.00, "name": "DALBHARAT",     "category": "stock"},
    "NSE_EQ|TECHM":       {"base": 1332.00, "name": "TECHM",         "category": "stock"},
    "NSE_EQ|VOLTAS":      {"base": 1405.00, "name": "VOLTAS",        "category": "stock"},
    "NSE_EQ|TATAPOWER":   {"base": 394.50,  "name": "TATAPOWER",     "category": "stock"},
    "NSE_EQ|JSWSTEEL":    {"base": 1120.00, "name": "JSWSTEEL",      "category": "stock"},
}

ALL_INSTRUMENTS = {**MOCK_INDICES, **MOCK_COMMODITIES, **MOCK_STOCKS}

# Track current prices
_current_prices = {k: v["base"] for k, v in ALL_INSTRUMENTS.items()}
_trend = {k: random.choice([-1, 1]) for k in ALL_INSTRUMENTS}
_trend_counter = {k: 0 for k in ALL_INSTRUMENTS}


def _simulate_price(key: str) -> float:
    """Simulate realistic price movement with trend persistence."""
    info = ALL_INSTRUMENTS[key]
    base = info["base"]
    current = _current_prices[key]

    # Flip trend occasionally
    _trend_counter[key] += 1
    if _trend_counter[key] > random.randint(5, 30):
        _trend[key] *= -1
        _trend_counter[key] = 0

    # Volatility relative to price
    vol = base * 0.0008
    change = (random.random() * vol * _trend[key]) + (random.random() - 0.5) * vol * 0.5
    current += change

    # Keep within ±5% of base
    current = max(base * 0.95, min(base * 1.05, current))
    _current_prices[key] = round(current, 2)
    return _current_prices[key]


def generate_snapshot() -> dict:
    """Generate a full market snapshot."""
    feeds = {}
    for key, info in ALL_INSTRUMENTS.items():
        ltp = _simulate_price(key)
        cp  = info["base"]
        feeds[key] = {
            "ltpc": {
                "ltp": ltp,
                "ltt": str(int(time.time() * 1000)),
                "ltq": str(random.randint(10, 5000)),
                "cp":  cp,
            },
            "meta": {
                "name":     info["name"],
                "category": info["category"],
            }
        }
    return {
        "type": "live_feed",
        "feeds": feeds,
        "currentTs": str(int(time.time() * 1000)),
    }


def generate_market_status() -> dict:
    return {
        "type": "market_info",
        "currentTs": str(int(time.time() * 1000)),
        "marketInfo": {
            "segmentStatus": {
                "NSE_EQ":    "NORMAL_OPEN",
                "NSE_FO":    "NORMAL_OPEN",
                "NSE_INDEX": "NORMAL_OPEN",
                "BSE_EQ":    "NORMAL_OPEN",
                "BSE_INDEX": "NORMAL_OPEN",
                "MCX_FO":    "NORMAL_OPEN",
                "MCX_INDEX": "NORMAL_OPEN",
            }
        }
    }


async def start_mock_feed(broadcast_fn: Callable):
    """
    Simulate live market data feed.
    Call this instead of start_upstox_feed() during development.
    """
    print("[MockFeed] Starting simulated market data...")

    # First message: market status
    await broadcast_fn(generate_market_status())
    await asyncio.sleep(0.5)

    # Second message: full snapshot
    await broadcast_fn(generate_snapshot())

    tick = 0
    while True:
        await asyncio.sleep(1.0)  # Tick every second

        # Send 3-5 random instrument updates per tick
        keys = random.sample(list(ALL_INSTRUMENTS.keys()), k=random.randint(3, 6))
        feeds = {}
        for key in keys:
            ltp = _simulate_price(key)
            cp  = ALL_INSTRUMENTS[key]["base"]
            feeds[key] = {
                "ltpc": {
                    "ltp": ltp,
                    "ltt": str(int(time.time() * 1000)),
                    "ltq": str(random.randint(10, 5000)),
                    "cp":  cp,
                },
                "meta": ALL_INSTRUMENTS[key],
            }

        await broadcast_fn({
            "type": "live_feed",
            "feeds": feeds,
            "currentTs": str(int(time.time() * 1000)),
        })

        tick += 1
        if tick % 30 == 0:
            print(f"[MockFeed] {tick} ticks sent, {len(feeds)} instruments updated")


if __name__ == "__main__":
    # Standalone test
    async def print_broadcast(msg):
        print(json.dumps(msg, indent=2)[:200])

    asyncio.run(start_mock_feed(print_broadcast))
