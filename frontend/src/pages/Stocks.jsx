import{useState}from'react'
import useStore from'../store/useStore'
import{StockCard}from'../components/Cards'
import{getMeta,SPOT_META}from'../utils'
export default function Stocks({onOpenChart,onAddToWatchlist}){
  const{marketData,locResults}=useStore()
  const[filter,setFilter]=useState("all")
  const[search,setSearch]=useState("")
  const stocks=Object.entries(marketData).filter(([k])=>!SPOT_META[k])
  const filtered=stocks.filter(([k,d])=>{
    const m=getMeta(k,d);const nm=m.n.toLowerCase()
    const loc=locResults[m.s]
    const zf=filter==="all"||(loc?.zone===filter)
    return zf&&(!search||nm.includes(search.toLowerCase())||k.toLowerCase().includes(search.toLowerCase()))
  })
  const FBtn=({id,label})=>(
    <button onClick={()=>setFilter(id)} style={{padding:"3px 10px",borderRadius:4,fontSize:10,
      border:`1px solid ${filter===id?"#4fc3f7":"#162033"}`,
      background:filter===id?"rgba(79,195,247,.1)":"none",color:filter===id?"#4fc3f7":"#4a5568"}}>
      {label}
    </button>
  )
  return(
    <div style={{padding:"14px 18px 60px"}}>
      <div style={{display:"flex",gap:5,marginBottom:10,flexWrap:"wrap",alignItems:"center"}}>
        <FBtn id="all" label="All"/><FBtn id="CALL" label="📗 Call"/><FBtn id="PUT" label="📕 Put"/><FBtn id="WAIT" label="⏳ Wait"/>
        <input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search..."
          style={{flex:1,maxWidth:180,padding:"3px 9px",fontSize:10}}/>
        <span style={{fontSize:9,color:"#4a5568",marginLeft:"auto"}}>{filtered.length} stocks</span>
      </div>
      <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fill,minmax(148px,1fr))",gap:7}}>
        {filtered.map(([k,d])=>(
          <div key={k} onContextMenu={e=>{e.preventDefault();onAddToWatchlist(k)}}>
            <StockCard data={d} meta={getMeta(k,d)} loc={locResults[getMeta(k,d).s]||null}
              selected={false} onClick={()=>onOpenChart(k)}/>
          </div>
        ))}
      </div>
    </div>
  )
}
