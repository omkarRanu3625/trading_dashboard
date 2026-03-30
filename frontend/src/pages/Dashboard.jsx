import useStore from'../store/useStore'
import{IndexCard,StockCard}from'../components/Cards'
import{getMeta,fmt,pct,sign,arr,absn,SPOT_META}from'../utils'

const INDEX_KEYS=["NSE_INDEX|Nifty 50","NSE_INDEX|Nifty Bank","NSE_INDEX|Nifty Fin Service","NSE_INDEX|NIFTY MID SELECT","BSE_INDEX|SENSEX","BSE_INDEX|BANKEX"]
const COMM_KEYS=["MCX_FO|CRUDEOIL25APRFUT","MCX_FO|NATURALGAS25APRFUT","MCX_FO|GOLD25APRFUT","MCX_FO|SILVER25MAYFUT"]

function SectionHdr({title,count,note}){
  return(
    <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",marginBottom:10}}>
      <div style={{display:"flex",alignItems:"center",gap:7,fontFamily:"'JetBrains Mono',monospace",fontSize:9,textTransform:"uppercase",letterSpacing:".1em",color:"#4a5568"}}>
        <div style={{width:3,height:11,background:"#ffc94d",borderRadius:2}}/>
        {title} {count!=null&&<span style={{fontSize:8,padding:"1px 5px",background:"#1a2535",borderRadius:2,color:"#4a5568"}}>{count}</span>}
      </div>
      {note&&<span style={{fontSize:9,color:"#4a5568"}}>{note}</span>}
    </div>
  )
}

function ComCard({data,meta,onClick}){
  const ltpc=data?.ltpc||{};const ltp=ltpc.ltp||0,cp=ltpc.cp||ltp
  const p=((ltp-cp)/Math.max(cp,1)*100).toFixed(2);const dir=ltp>=cp?"up":"dn"
  return(
    <div style={{background:"#0f1624",border:"1px solid #162033",borderRadius:8,padding:11,cursor:"pointer",transition:".15s"}}
      onClick={onClick}
      onMouseEnter={e=>e.currentTarget.style.transform="translateY(-1px)"}
      onMouseLeave={e=>e.currentTarget.style.transform=""}>
      <div style={{fontSize:14,marginBottom:4}}>{meta.ico}</div>
      <div style={{fontSize:9,color:"#4a5568",fontFamily:"'JetBrains Mono',monospace",textTransform:"uppercase",marginBottom:4}}>{meta.n}</div>
      <div style={{fontFamily:"'JetBrains Mono',monospace",fontSize:14,fontWeight:700}}>{fmt(ltp)}</div>
      <div style={{fontSize:9,fontFamily:"'JetBrains Mono',monospace",marginTop:2,color:dir==="up"?"#00e676":"#ff3d5a"}}>{dir==="up"?"▲":"▼"} {Math.abs(parseFloat(p))}%</div>
    </div>
  )
}

export default function Dashboard({onOpenChart}){
  const{marketData,locResults}=useStore()
  const stocks=Object.entries(marketData).filter(([k])=>!SPOT_META[k]).slice(0,60)
  return(
    <div style={{padding:"14px 18px 60px"}}>
      <SectionHdr title="Indices" count={INDEX_KEYS.length}/>
      <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fill,minmax(170px,1fr))",gap:8,marginBottom:18}}>
        {INDEX_KEYS.map(k=>{const m=getMeta(k);return<IndexCard key={k} data={marketData[k]||{}} meta={m}
          loc={locResults[m.s]||null} selected={false} onClick={()=>onOpenChart(k)}/>})}
      </div>
      <SectionHdr title="Commodities"/>
      <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fill,minmax(140px,1fr))",gap:7,marginBottom:18}}>
        {COMM_KEYS.map(k=><ComCard key={k} data={marketData[k]||{}} meta={getMeta(k)} onClick={()=>onOpenChart(k)}/>)}
      </div>
      <SectionHdr title="Top F&O Stocks" count={stocks.length} note="Click for chart · Right-click to add to watchlist"/>
      <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fill,minmax(148px,1fr))",gap:7}}>
        {stocks.map(([k,d])=>{const m=getMeta(k);return<StockCard key={k} data={d} meta={m}
          loc={locResults[m.s]||null} selected={false} onClick={()=>onOpenChart(k)}/>})}
      </div>
    </div>
  )
}
