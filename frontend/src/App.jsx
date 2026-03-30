import{useState}from'react'
import useStore from'./store/useStore'
import useWebSocket from'./hooks/useWebSocket'
import Login from'./components/Login'
import Nav from'./components/Nav'
import Statusbar from'./components/Statusbar'
import ChartModal from'./components/ChartModal'
import Dashboard from'./pages/Dashboard'
import Stocks from'./pages/Stocks'
import LOCTable from'./pages/LOCTable'
import Calculator from'./pages/Calculator'
import History from'./pages/History'
import Watchlist from'./pages/Watchlist'

export default function App(){
  const authed=useStore(s=>s.authed)
  const[page,setPage]=useState("dashboard")
  const[chartKey,setChartKey]=useState(null)
  const[pendingWL,setPendingWL]=useState(null)
  useWebSocket()

  if(!authed)return<Login/>

  function openChart(key){setChartKey(key)}
  function addToWL(key){setPendingWL(key);setPage("watchlist")}

  return(
    <div style={{paddingBottom:30}}>
      <Nav activePage={page} setActivePage={setPage}/>
      {/* Top segments bar */}
      <TopBar/>
      {/* Pages */}
      {page==="dashboard"&&<Dashboard onOpenChart={openChart}/>}
      {page==="stocks"&&<Stocks onOpenChart={openChart} onAddToWatchlist={addToWL}/>}
      {page==="loc"&&<LOCTable onOpenChart={openChart}/>}
      {page==="calculator"&&<Calculator/>}
      {page==="history"&&<History/>}
      {page==="watchlist"&&<Watchlist onOpenChart={openChart}/>}
      {/* Chart overlay */}
      {chartKey&&<ChartModal instrKey={chartKey} onClose={()=>setChartKey(null)}/>}
      <Statusbar/>
    </div>
  )
}

function TopBar(){
  const{marketStatus,frames,marketData}=useStore()
  const segs=Object.entries(marketStatus)
  return(
    <div style={{display:"flex",alignItems:"center",gap:12,padding:"5px 18px",
      background:"rgba(11,16,24,.95)",borderBottom:"1px solid #162033",flexWrap:"wrap"}}>
      <div style={{display:"flex",gap:5,flexWrap:"wrap"}}>
        {segs.map(([seg,status])=>(
          <span key={seg} style={{fontSize:8,fontFamily:"'JetBrains Mono',monospace",padding:"2px 6px",borderRadius:3,
            border:`1px solid ${status.includes("OPEN")?"rgba(0,230,118,.25)":"#162033"}`,
            color:status.includes("OPEN")?"#00e676":"#4a5568",
            background:status.includes("OPEN")?"rgba(0,230,118,.05)":"none"}}>
            {seg} · {status.replace("NORMAL_","")}
          </span>
        ))}
      </div>
      <span style={{fontSize:9,color:"#4a5568",marginLeft:"auto",fontFamily:"'JetBrains Mono',monospace"}}>
        Ticks:<span style={{color:"#dde4ef"}}>{frames}</span> Instr:<span style={{color:"#dde4ef"}}>{Object.keys(marketData).length}</span>
      </span>
    </div>
  )
}
