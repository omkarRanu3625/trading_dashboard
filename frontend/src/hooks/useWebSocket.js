import{useEffect,useRef}from'react'
import useStore from'../store/useStore'

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
            // Partial snapshot - merge into existing
            onSnapshot({...msg, market_data:{...useStore.getState().marketData,...(msg.market_data||{})}})
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
