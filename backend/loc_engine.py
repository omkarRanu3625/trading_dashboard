"""
loc_engine.py — Complete Dynamic LOC Engine
Auto-fetches and updates CE/PE ITM-2 data from Upstox
"""
import asyncio, time
from dataclasses import dataclass, field
from typing import Optional, Callable, Dict
from .instruments import get_itm2_strikes, STRIKE_STEPS


@dataclass
class SpotData:
    ltp:   float = 0
    close: float = 0
    high:  float = 0
    low:   float = 0
    ts:    int   = 0


@dataclass
class OptionData:
    ltp:    float = 0
    close:  float = 0
    high:   float = 0
    low:    float = 0
    oi:     float = 0
    iv:     float = 0
    instrument_key: str = ""


@dataclass
class SymbolState:
    symbol:       str = ""
    spot:         SpotData = field(default_factory=SpotData)
    ce:           OptionData = field(default_factory=OptionData)
    pe:           OptionData = field(default_factory=OptionData)
    ce_strike:    float = 0
    pe_strike:    float = 0
    expiry:       str = ""
    expiries:     dict = field(default_factory=dict)
    option_chain: dict = field(default_factory=dict)
    loc_result:   dict = field(default_factory=dict)
    last_atm:     float = 0


def calc_loc_25(spot: SpotData, ce: OptionData, pe: OptionData) -> dict:
    """All 25 LOC formulas."""
    s  = spot.ltp   or 1
    sc = spot.close or s
    sh = spot.high  or s
    sl = spot.low   or s

    def sd(a, b): return (a/b) if b else 0

    # 1-4
    f1 = sd(max(ce.high, ce.close), max(sh, sc))
    f2 = sd(min(ce.low,  ce.close), min(sl, sc) or 1)
    f3 = sd(max(pe.high, pe.close), min(sl, sc) or 1)
    f4 = sd(min(pe.low,  pe.close), max(sh, sc))
    # 5-6
    f5 = sd(ce.ltp, s)
    f6 = sd(pe.ltp, s)
    # 7-10
    f7  = f1 - f2
    f8  = f3 - f4
    f9  = f7 / 2
    f10 = f8 / 2
    # 11-13
    ab  = f5 - f9
    ac  = f6 - f10
    f13 = f8 - f7
    # 15 DSL
    if   ab > 0 and ac < 0:              f15 = abs(ab) + abs(ac)
    elif ab < 0 and ac > 0:              f15 = abs(ab) + abs(ac)
    elif ab < 0 and ac < 0 and ab > ac:  f15 = abs(ac) - abs(ab)
    elif ab < 0 and ac < 0 and ab < ac:  f15 = abs(ab)
    else:                                f15 = abs(ab - ac)
    # 16-19
    f16 = f15 * s
    if   ab < ac: f17 = s + f16
    elif ab > ac: f17 = s - ac
    else:         f17 = s
    f18 = s + abs(ab)*s if ab < 0 else (s - abs(ab)*s if ab > 0 else s)
    f19 = s - abs(ac)*s if ac < 0 else (s + abs(ac)*s if ac > 0 else s)
    # 20-25
    f20 = f17 * 1.001
    f21 = f17 * 0.999
    f22 = f20 - f18
    f23 = f21 - f19
    f24 = s + f22
    f25 = s + f23
    # Zone
    if   s > f17 and s > f18 and s > f19: zone = "CALL"
    elif s < f17 and s < f18 and s < f19: zone = "PUT"
    else:                                  zone = "WAIT"

    chg = round(s - sc, 2)
    r2  = lambda x: round(x, 2)
    r4  = lambda x: round(x, 4)

    return {
        "ltp": r2(s), "cp": r2(sc), "change": chg,
        "pct": round(chg/sc*100, 2) if sc else 0,
        "bop": r2(f17), "cep": r2(f18), "pep": r2(f19),
        "ul": r2(f24),  "ll":  r2(f25),
        "ful": r2(f20), "fll": r2(f21),
        "ful_diff": r2(f22), "fll_diff": r2(f23),
        "dsl": r4(f15), "dsp": r2(f16),
        "call_move": r4(f7),  "put_move": r4(f8),
        "call_cp":   r4(f9),  "put_cp":   r4(f10),
        "call_cp_diff": r4(ab), "put_cp_diff": r4(ac),
        "ceh_sh": r4(f1), "cel_sl": r4(f2),
        "peh_sl": r4(f3), "pel_sh": r4(f4),
        "c_ce_s": r4(f5), "c_pe_s": r4(f6),
        "different": r4(f13),
        "zone": zone,
        "direction": "UP" if chg >= 0 else "DOWN",
        "distance": r2(abs(s - f17)),
        "ce_strike": 0, "pe_strike": 0,
        "ce_ltp": r2(ce.ltp), "pe_ltp": r2(pe.ltp),
        "ce_iv":  r2(ce.iv),  "pe_iv":  r2(pe.iv),
    }


class LOCEngine:
    def __init__(self):
        self.symbols: Dict[str, SymbolState] = {}
        self.access_token: str = ""
        self.on_loc_update: Optional[Callable] = None
        self.chain_fetch_time: Dict[str, float] = {}

    def register(self, symbol: str):
        if symbol not in self.symbols:
            self.symbols[symbol] = SymbolState(symbol=symbol)

    def get_state(self, symbol: str) -> Optional[SymbolState]:
        return self.symbols.get(symbol)

    def set_expiry(self, symbol: str, expiry: str):
        st = self.symbols.get(symbol)
        if st:
            st.expiry = expiry
            print(f"[LOC] {symbol} expiry → {expiry}")
            asyncio.create_task(self._refresh_chain(symbol))

    def update_spot(self, symbol: str, ltp: float, close: float,
                    high: float, low: float, ts: int):
        st = self.symbols.get(symbol)
        if not st: return
        st.spot.ltp   = ltp
        st.spot.close = close or ltp
        st.spot.high  = high  or ltp
        st.spot.low   = low   or ltp
        st.spot.ts    = ts

        # Check ATM change → swap ITM-2 (debounced)
        step = STRIKE_STEPS.get(symbol.upper(), 50)
        new_atm = round(round(ltp / step) * step, 2)
        if new_atm != st.last_atm:
            st.last_atm = new_atm
            ce_s, pe_s = get_itm2_strikes(ltp, symbol)
            if ce_s != st.ce_strike or pe_s != st.pe_strike:
                print(f"[LOC] {symbol} ITM-2 shift → CE:{ce_s} PE:{pe_s}")
                st.ce_strike = ce_s
                st.pe_strike = pe_s
                self._load_from_chain(symbol)
                # Fetch fresh chain for new strikes in background
                asyncio.create_task(self._refresh_chain(symbol))

        self._recalc(symbol)

    def update_option_from_feed(self, symbol: str, opt_type: str,
                                ltp: float, close: float,
                                high: float, low: float, iv: float = 0):
        """Update CE or PE data from live WebSocket feed."""
        st = self.symbols.get(symbol)
        if not st: return
        opt = st.ce if opt_type == "CE" else st.pe
        if ltp: opt.ltp   = ltp
        if close: opt.close = close
        if high:  opt.high  = high
        if low:   opt.low   = low
        if iv:    opt.iv    = iv
        self._recalc(symbol)

    def update_chain(self, symbol: str, chain: dict):
        st = self.symbols.get(symbol)
        if not st: return
        st.option_chain = chain
        # Also set initial strikes if not set yet
        if st.spot.ltp and not st.ce_strike:
            ce_s, pe_s = get_itm2_strikes(st.spot.ltp, symbol)
            st.ce_strike = ce_s
            st.pe_strike = pe_s
        self._load_from_chain(symbol)

    def _load_from_chain(self, symbol: str):
        st = self.symbols.get(symbol)
        if not st or not st.option_chain: return
        ce_row = st.option_chain.get(st.ce_strike, {})
        pe_row = st.option_chain.get(st.pe_strike, {})

        def best_price(*vals):
            """Return first non-zero value."""
            for v in vals:
                if v and v != 0: return v
            return 0

        if ce_row.get("CE"):
            c = ce_row["CE"]
            ce_ltp   = best_price(c.get("ltp",0), c.get("close",0))
            ce_close = best_price(c.get("close",0), c.get("ltp",0))
            st.ce.ltp    = ce_ltp
            st.ce.close  = ce_close
            st.ce.high   = best_price(c.get("high",0), ce_ltp)
            st.ce.low    = best_price(c.get("low",0),  ce_ltp)
            st.ce.oi     = c.get("oi", 0)
            st.ce.iv     = c.get("iv", 0)
            st.ce.instrument_key = ce_row.get("instrument_key_ce", "")

        if pe_row.get("PE"):
            p = pe_row["PE"]
            pe_ltp   = best_price(p.get("ltp",0), p.get("close",0))
            pe_close = best_price(p.get("close",0), p.get("ltp",0))
            st.pe.ltp    = pe_ltp
            st.pe.close  = pe_close
            st.pe.high   = best_price(p.get("high",0), pe_ltp)
            st.pe.low    = best_price(p.get("low",0),  pe_ltp)
            st.pe.oi     = p.get("oi", 0)
            st.pe.iv     = p.get("iv", 0)
            st.pe.instrument_key = pe_row.get("instrument_key_pe", "")

        print(f"[LOC] {symbol} ITM-2 data: "
              f"CE@{st.ce_strike} ltp={st.ce.ltp} close={st.ce.close} key={st.ce.instrument_key[:20] if st.ce.instrument_key else 'none'} | "
              f"PE@{st.pe_strike} ltp={st.pe.ltp} close={st.pe.close} key={st.pe.instrument_key[:20] if st.pe.instrument_key else 'none'}")
        self._recalc(symbol)

    def _recalc(self, symbol: str):
        st = self.symbols.get(symbol)
        if not st or not st.spot.ltp: return
        result = calc_loc_25(st.spot, st.ce, st.pe)
        result["ce_strike"] = st.ce_strike
        result["pe_strike"] = st.pe_strike
        result["expiry"]    = st.expiry
        result["symbol"]    = symbol
        st.loc_result = result
        if self.on_loc_update:
            asyncio.create_task(self.on_loc_update(symbol, result))

    # Public alias for external callers
    def recalc(self, symbol: str):
        return self._recalc(symbol)

    async def _refresh_chain(self, symbol: str):
        if not self.access_token: return
        st = self.symbols.get(symbol)
        if not st or not st.expiry: return
        cache_key = f"{symbol}|{st.expiry}"
        if time.time() - self.chain_fetch_time.get(cache_key, 0) < 55:
            return
        self.chain_fetch_time[cache_key] = time.time()
        from .instruments import fetch_option_chain
        chain = await fetch_option_chain(symbol, st.expiry, self.access_token)
        if chain:
            self.update_chain(symbol, chain)

    async def refresh_all_chains(self):
        """Called every 60 seconds from main."""
        for symbol in list(self.symbols.keys()):
            await self._refresh_chain(symbol)

    def get_all_results(self) -> dict:
        return {sym: st.loc_result for sym, st in self.symbols.items() if st.loc_result}

    def get_option_keys(self) -> list:
        keys = []
        for st in self.symbols.values():
            if st.ce.instrument_key: keys.append(st.ce.instrument_key)
            if st.pe.instrument_key: keys.append(st.pe.instrument_key)
        return [k for k in keys if k]
