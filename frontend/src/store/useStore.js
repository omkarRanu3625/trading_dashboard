import{create}from'zustand'
const useStore=create((set,get)=>({
  // Auth
  authed:!!sessionStorage.getItem("raima_auth"),
  setAuthed:(v)=>{if(v)sessionStorage.setItem("raima_auth","1");else sessionStorage.removeItem("raima_auth");set({authed:v})},
  // Connection
  wsState:"CONNECTING",setWsState:(v)=>set({wsState:v}),
  mode:"live",setMode:(v)=>set({mode:v}),
  frames:0,tickCount:0,
  // Market data
  marketData:{},  // key → {ltpc,efeed,ts,...}
  marketStatus:{},
  locResults:{},  // sym → loc result
  expiryCache:{}, // sym → {all,default,...}
  symCe:{},       // sym → {ltp,close,high,low,strike,iv}
  symPe:{},       // sym → {ltp,close,high,low,strike,iv}
  locHistory:{},  // sym → [{ts,ltp,bop,...}]
  ohlcCache:{},   // key → candles[]
  watchlists:{},
  symCe:{},
  symPe:{},

  onSnapshot:(d)=>set({
    marketData:{...d.market_data||{}},
    marketStatus:d.market_status||{},
    locResults:{...d.loc_results||{}},
    expiryCache:d.expiry_cache||{},
    symCe:d.sym_ce||{},symPe:d.sym_pe||{},
    mode:d.mode||"live",
    symCe:d.sym_ce||{},
    symPe:d.sym_pe||{},
  }),

  onLiveFeed:(msg)=>set(s=>{
    const md={...s.marketData}
    for(const[k,v] of Object.entries(msg.feeds||{})){md[k]={...md[k],...v,ts:msg.currentTs}}
    return{marketData:md,locResults:{...s.locResults,...(msg.loc_results||{})},
      frames:s.frames+1,tickCount:s.tickCount+(Object.keys(msg.feeds||{}).length)}
  }),

  onMarketInfo:(msg)=>set({marketStatus:msg.marketInfo?.segmentStatus||{}}),

  setLocHistory:(sym,hist)=>set(s=>({locHistory:{...s.locHistory,[sym]:hist}})),
  setOhlc:(key,candles)=>set(s=>({ohlcCache:{...s.ohlcCache,[key]:candles}})),
  setWatchlists:(wl)=>set({watchlists:wl}),
  addWatchlist:(name)=>set(s=>({watchlists:{...s.watchlists,[name]:[]}})),
  addToWatchlist:(name,key)=>set(s=>{
    const wl={...s.watchlists};wl[name]=[...(wl[name]||[])].filter(k=>k!==key).concat(key);return{watchlists:wl}
  }),
  removeFromWatchlist:(name,key)=>set(s=>{
    const wl={...s.watchlists};wl[name]=(wl[name]||[]).filter(k=>k!==key);return{watchlists:wl}
  }),
  deleteWatchlist:(name)=>set(s=>{const wl={...s.watchlists};delete wl[name];return{watchlists:wl}}),
}))
export default useStore

// Expose symCe/symPe getters as part of snapshot
