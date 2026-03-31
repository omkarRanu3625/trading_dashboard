import{useState,useMemo}from'react'
import useStore from'../store/useStore'
import{fmt,absn,arr,getMeta,SYM_TO_KEY}from'../utils'
const TH=({label,k,sort,setSort,num})=>(
  <th onClick={()=>setSort(s=>({k,d:s.k===k?-s.d:1}))}
    style={{padding:"7px 10px",textAlign:num?"right":"left",fontFamily:"'JetBrains Mono',monospace",fontSize:8,
      textTransform:"uppercase",letterSpacing:".08em",color:sort.k===k?"#4fc3f7":"#4a5568",
      background:"#0f1624",borderBottom:"1px solid #162033",whiteSpace:"nowrap",cursor:"pointer",userSelect:"none"}}>
    {label}{sort.k===k?(sort.d>0?" ↑":" ↓"):""}
  </th>
)
export default function LOCTable({onOpenChart}){
  const{locResults,marketData,spotKeys}=useStore()
  const[filter,setFilter]=useState("all")
  const[sort,setSort]=useState({k:"symbol",d:1})
  const rows=useMemo(()=>{
    let arr2=Object.entries(locResults).map(([sym,loc])=>({sym,loc,meta:getMeta(sym)}))
    if(filter==="CALL"||filter==="PUT"||filter==="WAIT")arr2=arr2.filter(r=>r.loc.zone===filter)
    arr2.sort((a,b)=>{
      if(sort.k==="symbol")return sort.d*a.sym.localeCompare(b.sym)
      const av=a.loc[sort.k]||0,bv=b.loc[sort.k]||0
      return sort.d*(av-bv)
    })
    return arr2
  },[locResults,filter,sort])
  const FC=({id,label})=>(
    <button onClick={()=>setFilter(id)} style={{padding:"3px 9px",borderRadius:4,fontSize:10,
      border:`1px solid ${filter===id?"#4fc3f7":"#162033"}`,
      background:filter===id?"rgba(79,195,247,.1)":"none",color:filter===id?"#4fc3f7":"#4a5568"}}>
      {label}
    </button>
  )
  return(
    <div style={{padding:"14px 18px 60px"}}>
      <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",marginBottom:10,flexWrap:"wrap",gap:8}}>
        <div style={{fontFamily:"'JetBrains Mono',monospace",fontSize:9,color:"#4a5568",textTransform:"uppercase",letterSpacing:".1em"}}>LOC Analysis — All Symbols</div>
        <div style={{display:"flex",gap:5}}><FC id="all" label="All"/><FC id="CALL" label="CALL"/><FC id="PUT" label="PUT"/><FC id="WAIT" label="WAIT"/></div>
      </div>
      <div style={{overflowX:"auto",border:"1px solid #162033",borderRadius:8}}>
        <table style={{width:"100%",borderCollapse:"collapse",fontSize:10}}>
          <thead><tr>
            <TH label="Symbol" k="symbol" sort={sort} setSort={setSort}/>
            <TH label="LTP" k="ltp" sort={sort} setSort={setSort} num/>
            <TH label="Close" k="cp" sort={sort} setSort={setSort} num/>
            <TH label="Chg" k="change" sort={sort} setSort={setSort} num/>
            <TH label="CEP" k="cep" sort={sort} setSort={setSort} num/>
            <TH label="BOP" k="bop" sort={sort} setSort={setSort} num/>
            <TH label="PEP" k="pep" sort={sort} setSort={setSort} num/>
            <TH label="UL" k="ul" sort={sort} setSort={setSort} num/>
            <TH label="LL" k="ll" sort={sort} setSort={setSort} num/>
            <TH label="Dist" k="distance" sort={sort} setSort={setSort} num/>
            <TH label="Zone" k="zone" sort={sort} setSort={setSort}/>
            <TH label="Dir" k="direction" sort={sort} setSort={setSort}/>
          </tr></thead>
          <tbody>
            {rows.map(({sym,loc,meta})=>(
              <tr key={sym} onClick={()=>onOpenChart(spotKeys[sym]||SYM_TO_KEY[sym]||sym)} style={{cursor:"pointer"}}
                onMouseEnter={e=>e.currentTarget.style.background="rgba(255,255,255,.015)"}
                onMouseLeave={e=>e.currentTarget.style.background=""}>
                <td style={{padding:"7px 10px",fontFamily:"'JetBrains Mono',monospace",fontWeight:700,borderBottom:"1px solid rgba(22,32,51,.4)"}}>{sym}</td>
                <Td v={loc.ltp} color="#4fc3f7"/>
                <Td v={loc.cp} color="#4a5568"/>
                <Td v={loc.change} color={loc.change>=0?"#00e676":"#ff3d5a"} suffix={` (${absn(loc.pct)}%)`} arr/>
                <Td v={loc.cep} color="#00e676"/>
                <Td v={loc.bop} color="#ffc94d"/>
                <Td v={loc.pep} color="#ff3d5a"/>
                <Td v={loc.ul} color="#80deea"/>
                <Td v={loc.ll} color="#b39ddb"/>
                <Td v={loc.distance}/>
                <td style={{padding:"7px 10px",borderBottom:"1px solid rgba(22,32,51,.4)"}}>
                  <span style={{padding:"2px 6px",borderRadius:2,fontSize:9,fontFamily:"'JetBrains Mono',monospace",fontWeight:700,
                    background:loc.zone==="CALL"?"rgba(0,230,118,.12)":loc.zone==="PUT"?"rgba(255,61,90,.12)":"rgba(255,201,77,.1)",
                    color:loc.zone==="CALL"?"#00e676":loc.zone==="PUT"?"#ff3d5a":"#ffc94d"}}>{loc.zone}</span>
                </td>
                <td style={{padding:"7px 10px",borderBottom:"1px solid rgba(22,32,51,.4)",color:loc.direction==="UP"?"#00e676":"#ff3d5a",fontFamily:"'JetBrains Mono',monospace",fontSize:11}}>
                  {loc.direction==="UP"?"▲":"▼"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
function Td({v,color,suffix,arr:showArr}){
  return<td style={{padding:"7px 10px",textAlign:"right",borderBottom:"1px solid rgba(22,32,51,.4)",
    fontFamily:"'JetBrains Mono',monospace",color:color||"#dde4ef"}}>
    {showArr&&(v>=0?"▲":"▼")}{fmt(v)}{suffix||""}
  </td>
}
