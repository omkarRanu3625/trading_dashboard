import{useEffect,useRef}from'react'
import useStore from'../store/useStore'
import{setMcxKeyMap}from'../utils'

export default function useWebSocket(){
  const ws=useRef(null); const timer=useRef(null)
  const{setWsState,onSnapshot,onLiveFeed,onLiveLoc,onMarketInfo,setMode}=useStore()

  function connect(){
    setWsState("CONNECTING")
    const proto=location.protocol==="https:"?"wss":"ws"
    const url=`${proto}://${location.host}/ws/feed`
    try{
      const w=new WebSocket(url); ws.current=w
      w.onopen=()=>setWsState("OPEN")
      w.onmessage=e=>{
        try{
          const msg=JSON.parse(e.data)
          if(msg.type==="snapshot")         onSnapshot(msg)
          else if(msg.type==="live_feed")   onLiveFeed(msg)
          else if(msg.type==="loc_update")  onLiveLoc(msg)
          else if(msg.type==="market_info") onMarketInfo(msg)
          else if(msg.type==="snapshot_update"){
            // Partial snapshot - merge market_data, update metadata only if present
            const s=useStore.getState()
            const merged={...s.marketData,...(msg.market_data||{})}
            const upd={marketData:merged, instrCount:Object.keys(merged).length}
            if(msg.commodity_keys?.length) upd.commodityKeys=msg.commodity_keys
            if(msg.spot_keys&&Object.keys(msg.spot_keys).length){upd.spotKeys=msg.spot_keys;setMcxKeyMap(msg.spot_keys)}
            if(msg.expiry_cache&&Object.keys(msg.expiry_cache).length) upd.expiryCache=msg.expiry_cache
            if(msg.loc_results&&Object.keys(msg.loc_results).length) upd.locResults={...s.locResults,...msg.loc_results}
            if(msg.market_status&&Object.keys(msg.market_status).length) upd.marketStatus=msg.market_status
            useStore.setState(upd)
          }
        }catch(err){console.warn("WS parse:",err)}
      }
      w.onclose=()=>{
        setWsState("RECONNECTING")
        timer.current=setTimeout(connect,3000)
      }
      w.onerror=()=>w.close()
    }catch{timer.current=setTimeout(connect,5000)}
  }

  useEffect(()=>{
    connect()
    return()=>{ws.current?.close(); clearTimeout(timer.current)}
  },[])
  return ws
}
