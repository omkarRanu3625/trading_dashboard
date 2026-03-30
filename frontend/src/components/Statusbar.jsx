import useStore from'../store/useStore'
import{fmt,pct,sign,arr,absn,getMeta}from'../utils'

export default function Statusbar(){
  const{marketData,wsState,tickCount,instrCount}=useStore()

  // Only show stocks with real ltp for ticker
  const entries=Object.entries(marketData)
    .filter(([,d])=>{
      const ltp=d?.ltpc?.ltp||d?.efeed?.ltp||0
      return ltp>0
    })
    .slice(0,30)

  return(
    <div style={{position:"fixed",bottom:0,left:0,right:0,background:"#0b1018",
      borderTop:"1px solid #162033",padding:"4px 16px",
      display:"flex",alignItems:"center",justifyContent:"space-between",
      zIndex:100,gap:12,height:30}}>
      <div style={{display:"flex",gap:14,flexShrink:0}}>
        <span style={{fontSize:9,color:"#4a5568",fontFamily:"'JetBrains Mono',monospace"}}>
          WS:<span style={{color:wsState==="OPEN"?"#00e676":wsState==="RECONNECTING"?"#ffc94d":"#ff3d5a"}}> {wsState}</span>
        </span>
        <span style={{fontSize:9,color:"#4a5568",fontFamily:"'JetBrains Mono',monospace"}}>
          Ticks:<span style={{color:"#dde4ef"}}> {tickCount}</span>
        </span>
        <span style={{fontSize:9,color:"#4a5568",fontFamily:"'JetBrains Mono',monospace"}}>
          Instr:<span style={{color:"#dde4ef"}}> {instrCount||Object.keys(marketData).length}</span>
        </span>
      </div>

      {/* Scrolling ticker */}
      {entries.length>0&&(
        <div style={{overflow:"hidden",flex:1,position:"relative"}}>
          <div style={{position:"absolute",top:0,bottom:0,left:0,width:20,
            background:"linear-gradient(90deg,#0b1018,transparent)",zIndex:1}}/>
          <div style={{position:"absolute",top:0,bottom:0,right:0,width:20,
            background:"linear-gradient(-90deg,#0b1018,transparent)",zIndex:1}}/>
          <div style={{display:"flex",gap:18,
            animation:`scroll ${Math.max(20,entries.length*2)}s linear infinite`,
            width:"max-content"}}>
            {[...entries,...entries].map(([k,d],i)=>{
              const m=getMeta(k,d)
              const ltpc=d?.ltpc||{}; const ef=d?.efeed||{}
              const ltp=ltpc.ltp||ef.ltp||0
              const cp=ltpc.cp||ef.cp||0
              const p=pct(ltp,cp); const dir=sign(p)
              return(
                <span key={i} style={{display:"flex",gap:4,fontSize:9,
                  fontFamily:"'JetBrains Mono',monospace",whiteSpace:"nowrap"}}>
                  <span style={{color:"#4a5568"}}>{m.n}</span>
                  <span style={{color:"#dde4ef"}}>{fmt(ltp)}</span>
                  {cp>0&&<span style={{color:dir==="up"?"#00e676":"#ff3d5a"}}>{arr(p)}{absn(p)}%</span>}
                </span>
              )
            })}
          </div>
        </div>
      )}
      <style>{`@keyframes scroll{from{transform:translateX(0)}to{transform:translateX(-50%)}}`}</style>
    </div>
  )
}
