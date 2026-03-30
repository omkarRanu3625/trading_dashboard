"""
loc_engine.py v10 — Fixed CE@0 PE@0 bug
Critical fix: _load_from_chain now uses spot_price from chain response
(underlying_spot_price field) to calculate ITM-2 strikes,
so we don't need to wait for WS spot tick before options are set.
"""
import asyncio, time
from dataclasses import dataclass, field
from typing import Optional, Callable, Dict
from .instruments import get_itm2_strikes, STRIKE_STEPS

@dataclass
class SpotData:
    ltp:float=0; close:float=0; high:float=0; low:float=0; open:float=0; ts:int=0

@dataclass
class OptionData:
    ltp:float=0; close:float=0; high:float=0; low:float=0
    oi:float=0; iv:float=0; instrument_key:str=""

@dataclass
class SymbolState:
    symbol:str=""
    spot:SpotData=field(default_factory=SpotData)
    ce:OptionData=field(default_factory=OptionData)
    pe:OptionData=field(default_factory=OptionData)
    ce_strike:float=0; pe_strike:float=0
    expiry:str=""
    option_chain:dict=field(default_factory=dict)
    loc_result:dict=field(default_factory=dict)
    last_atm:float=0
    chain_spot:float=0   # ← spot price from chain response


def calc_loc_25(s, sc, sh, sl, so,
                ce_ltp, ce_close, ce_high, ce_low,
                pe_ltp, pe_close, pe_high, pe_low) -> dict:
    """All 25 LOC formulas."""
    s = s or 1; sc = sc or s; sh = sh or s; sl = sl or s

    def sd(a, b): return (a/b) if b else 0

    f1 = sd(max(ce_high or 0, ce_close or 0), max(sh, sc))
    f2 = sd(min(ce_low  or 0, ce_close or 0), min(sl, sc) or 1)
    f3 = sd(max(pe_high or 0, pe_close or 0), min(sl, sc) or 1)
    f4 = sd(min(pe_low  or 0, pe_close or 0), max(sh, sc))
    f5 = sd(ce_ltp or 0, s)
    f6 = sd(pe_ltp or 0, s)
    f7 = f1-f2; f8 = f3-f4; f9 = f7/2; f10 = f8/2
    ab = f5-f9; ac = f6-f10; f13 = f8-f7

    if   ab>0 and ac<0:             f15=abs(ab)+abs(ac)
    elif ab<0 and ac>0:             f15=abs(ab)+abs(ac)
    elif ab<0 and ac<0 and ab>ac:  f15=abs(ac)-abs(ab)
    elif ab<0 and ac<0 and ab<ac:  f15=abs(ab)
    else:                           f15=abs(ab-ac)

    f16=f15*s
    f17=s+f16 if ab<ac else(s-ac if ab>ac else s)
    f18=s+abs(ab)*s if ab<0 else(s-abs(ab)*s if ab>0 else s)
    f19=s-abs(ac)*s if ac<0 else(s+abs(ac)*s if ac>0 else s)
    f20=f17*1.001; f21=f17*0.999; f22=f20-f18; f23=f21-f19
    f24=s+f22;    f25=s+f23

    zone=("CALL" if s>f17 and s>f18 and s>f19 else
          "PUT"  if s<f17 and s<f18 and s<f19 else "WAIT")
    chg=round(s-sc,2)
    r2=lambda x:round(x,2); r4=lambda x:round(x,4)
    return {
        "ltp":r2(s),"cp":r2(sc),"change":chg,"pct":round(chg/sc*100,2) if sc else 0,
        "bop":r2(f17),"cep":r2(f18),"pep":r2(f19),
        "ul":r2(f24),"ll":r2(f25),"ful":r2(f20),"fll":r2(f21),
        "ful_diff":r2(f22),"fll_diff":r2(f23),"dsl":r4(f15),"dsp":r2(f16),
        "call_move":r4(f7),"put_move":r4(f8),"call_cp":r4(f9),"put_cp":r4(f10),
        "call_cp_diff":r4(ab),"put_cp_diff":r4(ac),"different":r4(f13),
        "ceh_sh":r4(f1),"cel_sl":r4(f2),"peh_sl":r4(f3),"pel_sh":r4(f4),
        "c_ce_s":r4(f5),"c_pe_s":r4(f6),
        "zone":zone,"direction":"UP" if chg>=0 else "DOWN","distance":r2(abs(s-f17)),
    }


class LOCEngine:
    def __init__(self):
        self.symbols:Dict[str,SymbolState]={}
        self.access_token:str=""
        self.on_loc_update:Optional[Callable]=None
        self.chain_fetch_time:Dict[str,float]={}

    def register(self, symbol:str):
        if symbol not in self.symbols:
            self.symbols[symbol]=SymbolState(symbol=symbol)

    def get_state(self, symbol:str)->Optional[SymbolState]:
        return self.symbols.get(symbol)

    def set_expiry(self, symbol:str, expiry:str):
        st=self.symbols.get(symbol)
        if st:
            st.expiry=expiry
            asyncio.create_task(self._refresh_chain(symbol))

    def update_spot(self, symbol:str, ltp:float, close:float,
                    high:float, low:float, ts:int, open_:float=0):
        st=self.symbols.get(symbol)
        if not st: return
        st.spot.ltp=ltp; st.spot.close=close or ltp
        st.spot.high=high or ltp; st.spot.low=low or ltp
        st.spot.open=open_ or ltp; st.spot.ts=ts

        # Check if ATM changed → swap ITM-2 strikes
        step=STRIKE_STEPS.get(symbol.upper(),50)
        new_atm=round(round(ltp/step)*step,2)
        if new_atm != st.last_atm:
            st.last_atm=new_atm
            ce_s,pe_s=get_itm2_strikes(ltp,symbol)
            if ce_s!=st.ce_strike or pe_s!=st.pe_strike:
                print(f"[LOC] {symbol} ATM→CE:{ce_s} PE:{pe_s}")
                st.ce_strike=ce_s; st.pe_strike=pe_s
                self._load_from_chain(symbol)
                asyncio.create_task(self._refresh_chain(symbol))
        self._recalc(symbol)

    def update_option_from_feed(self, symbol:str, opt_type:str,
                                 ltp:float, close:float, high:float, low:float):
        st=self.symbols.get(symbol)
        if not st: return
        opt=st.ce if opt_type=="CE" else st.pe
        if ltp:   opt.ltp=ltp
        if close: opt.close=close
        if high:  opt.high=max(opt.high,high) if opt.high else high
        if low and low>0: opt.low=min(opt.low,low) if opt.low else low
        self._recalc(symbol)

    def update_chain(self, symbol:str, chain:dict):
        st=self.symbols.get(symbol)
        if not st: return
        st.option_chain=chain

        # ── KEY FIX: Use spot_price from chain response ──────────
        # The chain rows contain underlying_spot_price — use it to
        # calculate ITM-2 even if WS spot hasn't arrived yet
        if chain:
            # Get spot price embedded in chain
            chain_spot=0.0
            for row in chain.values():
                sp = row.get("_spot",0)
                if sp:
                    chain_spot=sp; break

            if chain_spot:
                st.chain_spot=chain_spot
                # Use chain spot to set initial strikes if WS hasn't arrived
                effective_spot = st.spot.ltp or chain_spot
                ce_s,pe_s=get_itm2_strikes(effective_spot, symbol)
                st.ce_strike=ce_s; st.pe_strike=pe_s
                st.last_atm=round(round(effective_spot/STRIKE_STEPS.get(symbol.upper(),50))*STRIKE_STEPS.get(symbol.upper(),50),2)

                # Also set spot data from chain if WS hasn't arrived
                if not st.spot.ltp:
                    st.spot.ltp=chain_spot; st.spot.close=chain_spot

        self._load_from_chain(symbol)

    def _load_from_chain(self, symbol:str):
        st=self.symbols.get(symbol)
        if not st or not st.option_chain: return
        if not st.ce_strike:
            # Can't load without strikes — will retry when spot arrives
            print(f"[LOC] {symbol}: no strikes yet, deferring chain load")
            return

        ce_row=st.option_chain.get(st.ce_strike,{})
        pe_row=st.option_chain.get(st.pe_strike,{})

        def _best(*vals):
            for v in vals:
                try:
                    fv=float(v)
                    if fv!=0: return fv
                except: pass
            return 0.0

        if ce_row.get("CE"):
            c=ce_row["CE"]
            ce_ltp=_best(c.get("ltp",0),c.get("close",0))
            st.ce.ltp=ce_ltp; st.ce.close=_best(c.get("close",0),ce_ltp)
            st.ce.high=_best(c.get("high",0),ce_ltp)
            st.ce.low =_best(c.get("low",0), ce_ltp)
            st.ce.oi  =float(c.get("oi",0)); st.ce.iv=float(c.get("iv",0))
            st.ce.instrument_key=c.get("key","")

        if pe_row.get("PE"):
            p=pe_row["PE"]
            pe_ltp=_best(p.get("ltp",0),p.get("close",0))
            st.pe.ltp=pe_ltp; st.pe.close=_best(p.get("close",0),pe_ltp)
            st.pe.high=_best(p.get("high",0),pe_ltp)
            st.pe.low =_best(p.get("low",0), pe_ltp)
            st.pe.oi  =float(p.get("oi",0)); st.pe.iv=float(p.get("iv",0))
            st.pe.instrument_key=p.get("key","")

        print(f"[LOC] {symbol} loaded: "
              f"CE@{st.ce_strike}=ltp:{st.ce.ltp} close:{st.ce.close} key:{st.ce.instrument_key[:25] if st.ce.instrument_key else 'MISSING'} | "
              f"PE@{st.pe_strike}=ltp:{st.pe.ltp} close:{st.pe.close} key:{st.pe.instrument_key[:25] if st.pe.instrument_key else 'MISSING'}")
        self._recalc(symbol)

    def _recalc(self, symbol:str):
        st=self.symbols.get(symbol)
        if not st: return
        # Use chain_spot as fallback if WS spot hasn't arrived
        spot_ltp = st.spot.ltp or st.chain_spot
        if not spot_ltp: return

        res=calc_loc_25(
            spot_ltp, st.spot.close or spot_ltp,
            st.spot.high or spot_ltp, st.spot.low or spot_ltp, st.spot.open or spot_ltp,
            st.ce.ltp, st.ce.close, st.ce.high, st.ce.low,
            st.pe.ltp, st.pe.close, st.pe.high, st.pe.low,
        )
        res.update({
            "symbol":symbol,"ce_strike":st.ce_strike,"pe_strike":st.pe_strike,
            "expiry":st.expiry,
            "ce_ltp":round(st.ce.ltp,2),"pe_ltp":round(st.pe.ltp,2),
            "ce_iv":round(st.ce.iv,2),"pe_iv":round(st.pe.iv,2),
        })
        st.loc_result=res
        if self.on_loc_update:
            asyncio.create_task(self.on_loc_update(symbol,res))

    def recalc(self, symbol:str):
        return self._recalc(symbol)

    async def _refresh_chain(self, symbol:str):
        if not self.access_token: return
        st=self.symbols.get(symbol)
        if not st or not st.expiry: return
        cache_key=f"{symbol}|{st.expiry}"
        if time.time()-self.chain_fetch_time.get(cache_key,0)<55: return
        self.chain_fetch_time[cache_key]=time.time()
        from .instruments import fetch_option_chain
        chain=await fetch_option_chain(symbol,st.expiry,self.access_token)
        if chain: self.update_chain(symbol,chain)

    async def refresh_all_chains(self):
        for sym in list(self.symbols.keys()):
            await self._refresh_chain(sym)
            await asyncio.sleep(0.5)

    def get_all_results(self)->dict:
        return {s:st.loc_result for s,st in self.symbols.items() if st.loc_result}

    def get_option_keys(self)->list:
        keys=[]
        for st in self.symbols.values():
            if st.ce.instrument_key: keys.append(st.ce.instrument_key)
            if st.pe.instrument_key: keys.append(st.pe.instrument_key)
        return [k for k in keys if k]
