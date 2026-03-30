import useStore from'../store/useStore'
import{fmt,pct,sign,arr,absn,getMeta,SPOT_META}from'../utils'
export default function Statusbar(){
  const{marketData,wsState,frames,tickCount}=useStore()
  const entries=Object.entries(marketData).slice(0,20)
  return(
    <div style={{position:"fixed",bottom:0,left:0,right:0,background:"#0b1018",borderTop:"1px solid #162033",
      padding:"4px 16px",display:"flex",alignItems:"center",justifyContent:"space-between",zIndex:100,gap:12,height:30}}>
      <div style={{display:"flex",gap:14,flexShrink:0}}>
        <span style={{fontSize:9,color:"#4a5568",fontFamily:"'JetBrains Mono',monospace"}}>WS:<span style={{color:"#dde4ef"}}>{wsState}</span></span>
        <span style={{fontSize:9,color:"#4a5568",fontFamily:"'JetBrains Mono',monospace"}}>Ticks:<span style={{color:"#dde4ef"}}>{tickCount}</span></span>
        <span style={{fontSize:9,color:"#4a5568",fontFamily:"'JetBrains Mono',monospace"}}>Instr:<span style={{color:"#dde4ef"}}>{Object.keys(marketData).length}</span></span>
      </div>
      <div style={{overflow:"hidden",flex:1,position:"relative"}}>
        <div style={{position:"absolute",top:0,bottom:0,left:0,width:20,background:"linear-gradient(90deg,#0b1018,transparent)",zIndex:1}}/>
        <div style={{position:"absolute",top:0,bottom:0,right:0,width:20,background:"linear-gradient(-90deg,#0b1018,transparent)",zIndex:1}}/>
        <div style={{display:"flex",gap:18,animation:"scroll 50s linear infinite",width:"max-content"}}>
          {[...entries,...entries].map(([k,d],i)=>{
            const m=getMeta(k);const ltpc=d?.ltpc||{};const ltp=ltpc.ltp||0,cp=ltpc.cp||ltp
            const p=pct(ltp,cp);const dir=sign(p)
            return<span key={i} style={{display:"flex",gap:4,fontSize:9,fontFamily:"'JetBrains Mono',monospace",whiteSpace:"nowrap"}}>
              <span style={{color:"#4a5568"}}>{m.n}</span>
              <span style={{color:"#dde4ef"}}>{fmt(ltp)}</span>
              <span style={{color:dir==="up"?"#00e676":"#ff3d5a"}}>{arr(p)}{absn(p)}%</span>
            </span>
          })}
        </div>
      </div>
      <style>{`@keyframes scroll{from{transform:translateX(0)}to{transform:translateX(-50%)}}`}</style>
    </div>
  )
}
