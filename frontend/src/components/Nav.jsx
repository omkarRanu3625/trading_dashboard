import{useState,useEffect}from'react'
import useStore from'../store/useStore'
const TABS=[
  {id:"dashboard",label:"Dashboard"},
  {id:"stocks",label:"F&O Stocks"},
  {id:"loc",label:"LOC Table"},
  {id:"calculator",label:"Calculator"},
  {id:"history",label:"History"},
  {id:"watchlist",label:"Watchlist"},
]
const s={
  nav:{display:"flex",alignItems:"center",padding:"0 16px",height:50,background:"#0b1018",
    borderBottom:"1px solid #162033",position:"sticky",top:0,zIndex:200,gap:0},
  logo:{display:"flex",alignItems:"center",gap:7,marginRight:16,flexShrink:0},
  tabs:{display:"flex",gap:1,flex:1,overflowX:"auto"},
  tab:{padding:"5px 13px",fontSize:11,fontWeight:500,color:"#4a5568",cursor:"pointer",
    borderRadius:5,border:"none",background:"none",whiteSpace:"nowrap",flexShrink:0,transition:".15s"},
  tabActive:{color:"#ffc94d",background:"rgba(255,201,77,.1)",border:"1px solid rgba(255,201,77,.2)"},
  right:{display:"flex",alignItems:"center",gap:8,marginLeft:"auto",flexShrink:0},
  dot:{width:7,height:7,borderRadius:"50%",flexShrink:0},
  clock:{fontFamily:"'JetBrains Mono',monospace",fontSize:11,color:"#ffc94d",
    padding:"3px 8px",background:"rgba(255,201,77,.06)",border:"1px solid rgba(255,201,77,.15)",borderRadius:4},
  btn:{padding:"3px 10px",borderRadius:4,border:"1px solid #162033",background:"none",color:"#4a5568",fontSize:10},
  modal:{position:"fixed",inset:0,background:"rgba(0,0,0,.8)",zIndex:500,display:"flex",alignItems:"center",justifyContent:"center"},
  mbox:{background:"#0b1018",border:"1px solid #162033",borderRadius:12,padding:26,maxWidth:380,width:"90%"},
}
export default function Nav({activePage,setActivePage}){
  const{wsState,frames,mode}=useStore()
  const[clock,setClock]=useState("")
  const[showModal,setShowModal]=useState(false)
  const[token,setToken]=useState("")
  useEffect(()=>{const t=setInterval(()=>setClock(new Date().toLocaleTimeString("en-IN",{hour12:false})),1000);return()=>clearInterval(t)},[])
  async function submitToken(){
    if(!token)return
    const r=await fetch("/auth/token",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({access_token:token})})
    const d=await r.json()
    if(d.status==="ok"){setShowModal(false);alert("Token set — feed connecting...")}
  }
  const dotColor=wsState==="OPEN"?"#00e676":wsState==="CONNECTING"?"#ffc94d":"#ff3d5a"
  return(
    <>
    <nav style={s.nav}>
      <div style={s.logo}>
        <span style={{fontSize:20}}>🐂</span>
        <span style={{fontFamily:"'JetBrains Mono',monospace",fontSize:13,fontWeight:700,color:"#ffc94d"}}>RAIMA</span>
      </div>
      <div style={s.tabs}>
        {TABS.map(t=>(
          <button key={t.id} style={{...s.tab,...(activePage===t.id?s.tabActive:{})}}
            onClick={()=>setActivePage(t.id)}>{t.label}</button>
        ))}
      </div>
      <div style={s.right}>
        <div style={{...s.dot,background:dotColor,boxShadow:wsState==="OPEN"?`0 0 8px ${dotColor}`:"none",
          animation:wsState==="OPEN"?"blink 2s infinite":"none"}}/>
        <span style={{fontSize:9,color:"#4a5568",fontFamily:"'JetBrains Mono',monospace"}}>
          {wsState==="OPEN"?`LIVE · ${mode.toUpperCase()}`:wsState}</span>
        <div style={s.clock}>{clock}</div>
        <button style={s.btn} onClick={()=>setShowModal(true)}>⚙ Token</button>
      </div>
    </nav>
    {showModal&&(
      <div style={s.modal} onClick={e=>{if(e.target===e.currentTarget)setShowModal(false)}}>
        <div style={s.mbox}>
          <h2 style={{fontFamily:"'JetBrains Mono',monospace",fontSize:14,color:"#ffc94d",marginBottom:8}}>🔐 Upstox Token</h2>
          <p style={{fontSize:11,color:"#4a5568",marginBottom:14,lineHeight:1.6}}>Paste your Upstox access token to stream live market data.</p>
          <input style={{width:"100%",padding:"8px 10px",marginBottom:10,fontSize:10}} placeholder="Paste token..."
            value={token} onChange={e=>setToken(e.target.value)}/>
          <div style={{display:"flex",gap:7}}>
            <button onClick={submitToken} style={{padding:"6px 14px",background:"#ffc94d",color:"#000",fontWeight:700,border:"none",borderRadius:4,fontSize:10}}>Set Token</button>
            <button onClick={()=>location.href="/auth/upstox/login"} style={{padding:"6px 14px",background:"none",color:"#4a5568",border:"1px solid #162033",borderRadius:4,fontSize:10}}>OAuth Login</button>
            <button onClick={()=>setShowModal(false)} style={{padding:"6px 14px",background:"none",color:"#4a5568",border:"1px solid #162033",borderRadius:4,fontSize:10}}>Cancel</button>
          </div>
        </div>
      </div>
    )}
    </>
  )
}
