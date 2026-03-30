import{useState,useEffect}from'react'
import useStore from'../store/useStore'
import{fmt,pct,sign,arr,absn,getMeta}from'../utils'
export default function Watchlist({onOpenChart}){
  const{watchlists,addWatchlist,deleteWatchlist,removeFromWatchlist,marketData,locResults,setWatchlists}=useStore()
  const[active,setActive]=useState(null)
  const[newName,setNewName]=useState("")
  useEffect(()=>{fetch("/api/watchlist").then(r=>r.json()).then(d=>setWatchlists(d)).catch(()=>{})},[])
  function create(){
    if(!newName.trim())return
    addWatchlist(newName.trim());setActive(newName.trim());setNewName("")
    fetch("/api/watchlist",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({name:newName.trim(),keys:[]})})
  }
  const keys=active&&watchlists[active]?watchlists[active]:[]
  return(
    <div style={{padding:"14px 18px 60px"}}>
      <div style={{display:"grid",gridTemplateColumns:"260px 1fr",gap:14}}>
        <div style={{background:"#0f1624",border:"1px solid #162033",borderRadius:8,padding:12}}>
          <div style={{fontFamily:"'JetBrains Mono',monospace",fontSize:9,color:"#4a5568",textTransform:"uppercase",marginBottom:10}}>My Watchlists</div>
          <div style={{display:"flex",gap:5,marginBottom:8}}>
            <input value={newName} onChange={e=>setNewName(e.target.value)} placeholder="Name..."
              onKeyDown={e=>e.key==="Enter"&&create()}
              style={{flex:1,padding:"5px 8px",fontSize:10}}/>
            <button onClick={create} style={{padding:"5px 10px",background:"#ffc94d",color:"#000",fontWeight:700,border:"none",borderRadius:4,fontSize:10}}>+ New</button>
          </div>
          {Object.keys(watchlists).map(name=>(
            <div key={name} onClick={()=>setActive(name)}
              style={{padding:"7px 9px",borderRadius:4,cursor:"pointer",display:"flex",alignItems:"center",justifyContent:"space-between",marginBottom:3,
                background:active===name?"rgba(255,201,77,.08)":"none",border:active===name?"1px solid rgba(255,201,77,.2)":"1px solid transparent"}}>
              <span style={{fontFamily:"'JetBrains Mono',monospace",fontSize:10}}>{name} <span style={{color:"#4a5568"}}>({(watchlists[name]||[]).length})</span></span>
              <button onClick={e=>{e.stopPropagation();deleteWatchlist(name);if(active===name)setActive(null);fetch(`/api/watchlist/${name}`,{method:"DELETE"})}}
                style={{background:"none",border:"none",color:"#4a5568",fontSize:12,lineHeight:1}}>✕</button>
            </div>
          ))}
          {!Object.keys(watchlists).length&&<div style={{fontSize:9,color:"#4a5568",padding:6}}>No watchlists yet</div>}
        </div>
        <div style={{background:"#0f1624",border:"1px solid #162033",borderRadius:8,overflow:"hidden"}}>
          <div style={{padding:"10px 12px",borderBottom:"1px solid #162033",fontFamily:"'JetBrains Mono',monospace",fontSize:10,color:"#4a5568"}}>
            {active?`${active} — ${keys.length} instruments (right-click any stock to add)`:"Select a watchlist"}
          </div>
          <table style={{width:"100%",borderCollapse:"collapse",fontSize:10}}>
            <thead><tr>
              {["Symbol","LTP","Chg%","BOP","CEP","PEP","Zone",""].map(h=>(
                <th key={h} style={{padding:"6px 10px",textAlign:h===""||h==="Symbol"||h==="Zone"?"left":"right",fontFamily:"'JetBrains Mono',monospace",fontSize:8,textTransform:"uppercase",color:"#4a5568",background:"#1a2535",borderBottom:"1px solid #162033"}}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {!keys.length?<tr><td colSpan={8} style={{padding:20,textAlign:"center",color:"#4a5568",fontSize:10}}>
                {active?"Empty watchlist — right-click stocks to add":"Select a watchlist"}
              </td></tr>:keys.map(k=>{
                const d=marketData[k]||{};const ltpc=d.ltpc||{};const ltp=ltpc.ltp||0,cp=ltpc.cp||ltp
                const p=pct(ltp,cp);const dir=sign(p);const m=getMeta(k)
                const loc=locResults[m.s]||{}
                return(
                  <tr key={k} onClick={()=>onOpenChart(k)} style={{cursor:"pointer"}}
                    onMouseEnter={e=>e.currentTarget.style.background="rgba(255,255,255,.015)"}
                    onMouseLeave={e=>e.currentTarget.style.background=""}>
                    <td style={{padding:"7px 10px",fontFamily:"'JetBrains Mono',monospace",fontWeight:700,borderBottom:"1px solid rgba(22,32,51,.4)"}}>{m.ico} {m.n}</td>
                    <td style={{padding:"7px 10px",textAlign:"right",fontFamily:"'JetBrains Mono',monospace",borderBottom:"1px solid rgba(22,32,51,.4)"}}>{fmt(ltp)}</td>
                    <td style={{padding:"7px 10px",textAlign:"right",fontFamily:"'JetBrains Mono',monospace",borderBottom:"1px solid rgba(22,32,51,.4)",color:dir==="up"?"#00e676":"#ff3d5a"}}>{arr(p)}{absn(p)}%</td>
                    <td style={{padding:"7px 10px",textAlign:"right",fontFamily:"'JetBrains Mono',monospace",color:"#ffc94d",borderBottom:"1px solid rgba(22,32,51,.4)"}}>{fmt(loc.bop||0)}</td>
                    <td style={{padding:"7px 10px",textAlign:"right",fontFamily:"'JetBrains Mono',monospace",color:"#00e676",borderBottom:"1px solid rgba(22,32,51,.4)"}}>{fmt(loc.cep||0)}</td>
                    <td style={{padding:"7px 10px",textAlign:"right",fontFamily:"'JetBrains Mono',monospace",color:"#ff3d5a",borderBottom:"1px solid rgba(22,32,51,.4)"}}>{fmt(loc.pep||0)}</td>
                    <td style={{padding:"7px 10px",borderBottom:"1px solid rgba(22,32,51,.4)"}}>
                      {loc.zone&&<span style={{fontSize:9,fontFamily:"'JetBrains Mono',monospace",fontWeight:700,color:loc.zone==="CALL"?"#00e676":loc.zone==="PUT"?"#ff3d5a":"#ffc94d"}}>{loc.zone}</span>}
                    </td>
                    <td style={{padding:"7px 10px",borderBottom:"1px solid rgba(22,32,51,.4)"}}>
                      <button onClick={e=>{e.stopPropagation();removeFromWatchlist(active,k);fetch("/api/watchlist",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({name:active,keys:keys.filter(x=>x!==k)})})}}
                        style={{background:"none",border:"none",color:"#4a5568",fontSize:12}}>✕</button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
