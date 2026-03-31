import{useEffect}from'react'
import useStore from'../store/useStore'
import{IndexCard,StockCard}from'../components/Cards'
import{getMeta,fmt,pct,sign,arr,absn,SPOT_META}from'../utils'

// Index keys — static (always these keys)
const INDEX_KEYS=[
  "NSE_INDEX|Nifty 50","NSE_INDEX|Nifty Bank","NSE_INDEX|Nifty Fin Service",
  "NSE_INDEX|NIFTY MID SELECT","BSE_INDEX|SENSEX","BSE_INDEX|BANKEX",
]

function SectionHdr({title,count,note}){
  return(
    <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",marginBottom:10}}>
      <div style={{display:"flex",alignItems:"center",gap:7,fontFamily:"'JetBrains Mono',monospace",
        fontSize:9,textTransform:"uppercase",letterSpacing:".1em",color:"#4a5568"}}>
        <div style={{width:3,height:11,background:"#ffc94d",borderRadius:2}}/>
        {title} {count!=null&&<span style={{fontSize:8,padding:"1px 5px",background:"#1a2535",borderRadius:2,color:"#4a5568"}}>{count}</span>}
      </div>
      {note&&<span style={{fontSize:9,color:"#4a5568"}}>{note}</span>}
    </div>
  )
}

function ComCard({instrKey,data,onClick}){
  const meta=getMeta(instrKey,data)
  const ltpc=data?.ltpc||{}
  const ef=data?.efeed||{}
  const ltp=ltpc.ltp||ef.ltp||0
  const cp=ltpc.cp||ef.cp||0
  const p=pct(ltp,cp); const dir=sign(p)
  return(
    <div style={{background:"#0f1624",border:"1px solid #162033",borderRadius:8,padding:11,cursor:"pointer",transition:".15s"}}
      onClick={onClick}
      onMouseEnter={e=>e.currentTarget.style.transform="translateY(-1px)"}
      onMouseLeave={e=>e.currentTarget.style.transform=""}>
      <div style={{fontSize:16,marginBottom:4}}>{meta.ico}</div>
      <div style={{fontSize:9,color:"#4a5568",fontFamily:"'JetBrains Mono',monospace",textTransform:"uppercase",marginBottom:4}}>{meta.n}</div>
      {ltp>0?(
        <>
          <div style={{fontFamily:"'JetBrains Mono',monospace",fontSize:14,fontWeight:700,
            color:dir==="up"?"#00e676":"#ff3d5a"}}>{fmt(ltp)}</div>
          <div style={{fontSize:9,fontFamily:"'JetBrains Mono',monospace",marginTop:2,
            color:dir==="up"?"#00e676":"#ff3d5a"}}>{arr(p)} {absn(p)}%</div>
        </>
      ):(
        <div style={{fontFamily:"'JetBrains Mono',monospace",fontSize:12,color:"#4a5568"}}>—</div>
      )}
    </div>
  )
}

export default function Dashboard({onOpenChart}){
  const{marketData,locResults,commodityKeys}=useStore()

  // Use dynamic commodity keys from server (updated at startup)
  // Fall back to detecting MCX keys from marketData
  const commKeys=(() => {
    if(commodityKeys && commodityKeys.length>0) return commodityKeys.slice(0,5)
    // Fallback: find MCX keys in marketData
    return Object.keys(marketData).filter(k=>k.startsWith("MCX_FO|")).slice(0,4)
  })()

  const stocks=Object.entries(marketData)
    .filter(([k,d])=>{
      if(SPOT_META[k]) return false          // exclude indices
      if(k.startsWith("MCX_FO|")) return false // exclude MCX
      const ltp=d?.ltpc?.ltp||d?.efeed?.ltp||0
      return ltp>0
    })
    .sort(([,a],[,b])=>(b?.ltpc?.ltp||0)-(a?.ltpc?.ltp||0))
    .slice(0,60)

  return(
    <div style={{padding:"14px 18px 60px"}}>
      {/* Indices */}
      <SectionHdr title="Indices" count={INDEX_KEYS.length}/>
      <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fill,minmax(170px,1fr))",gap:8,marginBottom:18}}>
        {INDEX_KEYS.map(k=>{
          const m=getMeta(k)
          return<IndexCard key={k} data={marketData[k]||{}} meta={m}
            loc={locResults[m.s]||null} selected={false} onClick={()=>onOpenChart(k)}/>
        })}
      </div>

      {/* Commodities — dynamic keys from server */}
      <SectionHdr title="Commodities" count={commKeys.length}/>
      <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fill,minmax(140px,1fr))",gap:7,marginBottom:18}}>
        {commKeys.length>0
          ? commKeys.map(k=><ComCard key={k} instrKey={k} data={marketData[k]||{}} onClick={()=>onOpenChart(k)}/>)
          : ["CRUDEOIL","NATURALGAS","GOLD","SILVER","COPPER"].map(n=>(
              <div key={n} style={{background:"#0f1624",border:"1px solid #162033",borderRadius:8,padding:11}}>
                <div style={{fontSize:9,color:"#4a5568",fontFamily:"'JetBrains Mono',monospace"}}>{n}</div>
                <div style={{fontFamily:"'JetBrains Mono',monospace",fontSize:12,color:"#4a5568",marginTop:4}}>Loading...</div>
              </div>
            ))
        }
      </div>

      {/* Top F&O Stocks */}
      <SectionHdr title="Top F&O Stocks" count={stocks.length} note="Click for chart · Right-click to add to watchlist"/>
      <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fill,minmax(148px,1fr))",gap:7}}>
        {stocks.map(([k,d])=>{
          const m=getMeta(k,d)
          return<StockCard key={k} data={d} meta={m}
            loc={locResults[m.s]||null} selected={false} onClick={()=>onOpenChart(k)}/>
        })}
      </div>
    </div>
  )
}
