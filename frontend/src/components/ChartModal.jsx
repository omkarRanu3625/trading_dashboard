import{useState,useEffect,useRef}from'react'
import{createChart,CrosshairMode}from'lightweight-charts'
import useStore from'../store/useStore'
import{fmt,pct,sign,arr,absn,getMeta}from'../utils'

const LOC_ROWS=[
  ["ul","UL","#80deea"],["cep","CEP","#00e676"],["bop","BOP","#ffc94d"],
  ["pep","PEP","#ff3d5a"],["ll","LL","#b39ddb"],["ltp","LTP","#4fc3f7"],
]

export default function ChartModal({instrKey,onClose}){
  const{marketData,locResults}=useStore()
  const[tf,setTf]=useState("1m")
  const[candles,setCandles]=useState([])
  const[loading,setLoading]=useState(false)
  const chartRef=useRef(null);const ctRef=useRef(null)
  const meta=getMeta(instrKey,marketData[instrKey])
  const sym=meta.s||""
  const data=marketData[instrKey]||{}
  const ltpc=data.ltpc||{}
  const ltp=ltpc.ltp||0,cp=ltpc.cp||0
  const p=pct(ltp,cp);const dir=sign(p)
  const loc=locResults[sym]||null

  const TF_MAP={"1m":"minutes/1","5m":"minutes/5","15m":"minutes/15","1h":"hours/1","1d":"days/1"}

  useEffect(()=>{loadCandles()},[instrKey,tf])

  async function loadCandles(){
    setLoading(true)
    try{
      // Use live intraday API for today's candles
      const unit_interval = TF_MAP[tf] || "minutes/1"
      const r=await fetch(`/api/ohlc-live/${encodeURIComponent(instrKey)}?tf=${unit_interval}`)
      const d=await r.json()
      const c=d.candles||[]
      if(c.length>0){
        setCandles(c); setLoading(false); return
      }
    }catch(e){}
    // Fallback to server-tracked candles
    try{
      const r=await fetch(`/api/ohlc/${encodeURIComponent(instrKey)}`)
      const d=await r.json()
      setCandles(d.candles||[])
    }catch(e){}
    setLoading(false)
  }

  useEffect(()=>{
    if(!chartRef.current||candles.length===0)return
    ctRef.current?.remove();ctRef.current=null
    const chart=createChart(chartRef.current,{
      layout:{background:{color:"#0f1624"},textColor:"#4a5568"},
      grid:{vertLines:{color:"#162033"},horzLines:{color:"#162033"}},
      crosshair:{mode:CrosshairMode.Normal},
      rightPriceScale:{borderColor:"#162033"},
      timeScale:{borderColor:"#162033",timeVisible:true,secondsVisible:false},
      width:chartRef.current.clientWidth,height:260,
    })
    ctRef.current=chart

    // Main price series
    const series=chart.addCandlestickSeries({
      upColor:"#00e676",downColor:"#ff3d5a",
      wickUpColor:"#00e676",wickDownColor:"#ff3d5a",
      borderVisible:false,
    })
    const chartData=candles
      .filter(c=>c.t&&c.o&&c.h&&c.l&&c.c)
      .map(c=>({time:Math.floor(c.t/1000),open:c.o,high:c.h,low:c.l,close:c.c}))
      .sort((a,b)=>a.time-b.time)
    if(chartData.length>0)series.setData(chartData)

    // LOC horizontal lines
    if(loc&&chartData.length>0){
      const lines=[
        {v:loc.ul,  c:"#80deea",s:2,t:"UL"},
        {v:loc.cep, c:"#00e676",s:2,t:"CEP"},
        {v:loc.bop, c:"#ffc94d",s:2,t:"BOP"},
        {v:loc.pep, c:"#ff3d5a",s:2,t:"PEP"},
        {v:loc.ll,  c:"#b39ddb",s:2,t:"LL"},
      ]
      lines.forEach(({v,c,s,t})=>{
        if(!v)return
        const ls=chart.addLineSeries({color:c,lineWidth:s,lineStyle:2,
          priceLineVisible:false,lastValueVisible:true,
          title:t,crosshairMarkerVisible:false})
        ls.setData(chartData.map(d=>({time:d.time,value:v})))
      })

      // Yellow zone between UL and LL
      if(loc.ul&&loc.ll){
        const zone=chart.addLineSeries({color:"rgba(255,245,157,.08)",lineWidth:0,
          priceLineVisible:false,lastValueVisible:false,crosshairMarkerVisible:false})
        zone.setData(chartData.map(d=>({time:d.time,value:loc.ul})))
      }
    }

    const ro=new ResizeObserver(()=>{if(chartRef.current)chart.applyOptions({width:chartRef.current.clientWidth})})
    if(chartRef.current)ro.observe(chartRef.current)
    return()=>{ro.disconnect();chart.remove();ctRef.current=null}
  },[candles,loc])

  return(
    <div style={{position:"fixed",inset:0,background:"rgba(0,0,0,.75)",zIndex:300,
      display:"flex",alignItems:"center",justifyContent:"center"}}
      onClick={e=>{if(e.target===e.currentTarget)onClose()}}>
      <div style={{background:"#0b1018",border:"1px solid #162033",borderRadius:12,
        width:"92vw",maxWidth:1050,maxHeight:"88vh",overflow:"hidden",
        display:"flex",flexDirection:"column"}}>
        {/* Header */}
        <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",
          padding:"12px 16px",borderBottom:"1px solid #162033",flexWrap:"wrap",gap:10}}>
          <div style={{display:"flex",alignItems:"center",gap:14,flexWrap:"wrap"}}>
            <div>
              <div style={{fontFamily:"'JetBrains Mono',monospace",fontSize:15,fontWeight:700,color:"#ffc94d"}}>{meta.n}</div>
              <div style={{fontSize:9,color:"#4a5568",fontFamily:"'JetBrains Mono',monospace"}}>{instrKey}</div>
            </div>
            <div>
              <div style={{fontFamily:"'JetBrains Mono',monospace",fontSize:20,fontWeight:700,
                color:dir==="up"?"#00e676":"#ff3d5a"}}>{fmt(ltp)}</div>
              <div style={{fontSize:11,fontFamily:"'JetBrains Mono',monospace",
                color:dir==="up"?"#00e676":"#ff3d5a"}}>{arr(p)} {absn(p)}% ({fmt(ltp-cp)})</div>
            </div>
            {loc?.zone&&<div style={{padding:"4px 12px",borderRadius:4,
              fontFamily:"'JetBrains Mono',monospace",fontSize:11,fontWeight:700,
              background:loc.zone==="CALL"?"rgba(0,230,118,.1)":loc.zone==="PUT"?"rgba(255,61,90,.1)":"rgba(255,201,77,.1)",
              color:loc.zone==="CALL"?"#00e676":loc.zone==="PUT"?"#ff3d5a":"#ffc94d",
              border:`1px solid ${loc.zone==="CALL"?"rgba(0,230,118,.3)":loc.zone==="PUT"?"rgba(255,61,90,.3)":"rgba(255,201,77,.2)"}`}}>
              {loc.zone}
            </div>}
          </div>
          <button onClick={onClose} style={{background:"none",border:"none",color:"#4a5568",fontSize:22,lineHeight:1,cursor:"pointer"}}>✕</button>
        </div>
        {/* Body */}
        <div style={{flex:1,padding:14,overflowY:"auto",display:"grid",gridTemplateColumns:"1fr 240px",gap:14}}>
          <div>
            {/* TF buttons */}
            <div style={{display:"flex",gap:5,marginBottom:8,alignItems:"center"}}>
              {["1m","5m","15m","1h","1d"].map(t=>(
                <button key={t} onClick={()=>setTf(t)} style={{padding:"3px 10px",borderRadius:3,cursor:"pointer",
                  border:`1px solid ${tf===t?"rgba(255,201,77,.4)":"#162033"}`,
                  background:tf===t?"rgba(255,201,77,.1)":"none",
                  color:tf===t?"#ffc94d":"#4a5568",fontSize:10}}>
                  {t}
                </button>
              ))}
              {loading&&<span style={{fontSize:9,color:"#4a5568",fontFamily:"'JetBrains Mono',monospace"}}>loading...</span>}
              <span style={{fontSize:9,color:"#4a5568",fontFamily:"'JetBrains Mono',monospace",marginLeft:"auto"}}>
                {candles.length} candles
              </span>
            </div>
            {/* Chart */}
            <div style={{background:"#0f1624",border:"1px solid #162033",borderRadius:6,padding:8}}>
              <div ref={chartRef} style={{height:260,width:"100%"}}/>
            </div>
            {/* CE/PE info for index/sym */}
            {sym&&loc?.ce_strike&&<div style={{marginTop:8,background:"#0f1624",border:"1px solid #162033",borderRadius:6,padding:10}}>
              <div style={{fontFamily:"'JetBrains Mono',monospace",fontSize:9,color:"#4a5568",textTransform:"uppercase",marginBottom:8}}>ITM-2 Options — Live</div>
              <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:8}}>
                <div style={{background:"rgba(0,230,118,.05)",border:"1px solid rgba(0,230,118,.15)",borderRadius:5,padding:8}}>
                  <div style={{fontSize:9,color:"#00e676",fontFamily:"'JetBrains Mono',monospace",marginBottom:4}}>CE STRIKE {fmt(loc.ce_strike,0)}</div>
                  <div style={{fontFamily:"'JetBrains Mono',monospace",fontSize:13,fontWeight:700,color:"#00e676"}}>{fmt(loc.ce_ltp||0)}</div>
                  <div style={{fontSize:9,color:"#4a5568",fontFamily:"'JetBrains Mono',monospace"}}>IV: {fmt(loc.ce_iv||0,1)}%</div>
                </div>
                <div style={{background:"rgba(255,61,90,.05)",border:"1px solid rgba(255,61,90,.15)",borderRadius:5,padding:8}}>
                  <div style={{fontSize:9,color:"#ff3d5a",fontFamily:"'JetBrains Mono',monospace",marginBottom:4}}>PE STRIKE {fmt(loc.pe_strike,0)}</div>
                  <div style={{fontFamily:"'JetBrains Mono',monospace",fontSize:13,fontWeight:700,color:"#ff3d5a"}}>{fmt(loc.pe_ltp||0)}</div>
                  <div style={{fontSize:9,color:"#4a5568",fontFamily:"'JetBrains Mono',monospace"}}>IV: {fmt(loc.pe_iv||0,1)}%</div>
                </div>
              </div>
            </div>}
          </div>
          {/* LOC Panel */}
          <div style={{background:"#0f1624",border:"1px solid #162033",borderRadius:6,padding:12}}>
            <div style={{fontFamily:"'JetBrains Mono',monospace",fontSize:9,color:"#4a5568",
              textTransform:"uppercase",letterSpacing:".08em",marginBottom:8,
              borderBottom:"1px solid #162033",paddingBottom:6}}>LOC Analysis</div>
            {loc?(
              <>
                <div style={{padding:"6px 12px",borderRadius:4,fontFamily:"'JetBrains Mono',monospace",
                  fontSize:12,fontWeight:700,textAlign:"center",margin:"6px 0",
                  background:loc.zone==="CALL"?"rgba(0,230,118,.1)":loc.zone==="PUT"?"rgba(255,61,90,.1)":"rgba(255,201,77,.1)",
                  color:loc.zone==="CALL"?"#00e676":loc.zone==="PUT"?"#ff3d5a":"#ffc94d",
                  border:`1px solid ${loc.zone==="CALL"?"rgba(0,230,118,.25)":loc.zone==="PUT"?"rgba(255,61,90,.25)":"rgba(255,201,77,.2)"}`}}>
                  {loc.zone} ZONE
                </div>
                <div style={{background:"#060a0f",borderRadius:4,padding:8,marginTop:6}}>
                  {LOC_ROWS.map(([k,label,color])=>(
                    <div key={k} style={{display:"flex",justifyContent:"space-between",
                      padding:"3px 0",fontFamily:"'JetBrains Mono',monospace",fontSize:10,
                      borderBottom:"1px solid rgba(22,32,51,.4)"}}>
                      <span style={{color:"#4a5568"}}>{label}</span>
                      <span style={{fontWeight:600,color}}>{fmt(loc[k])}</span>
                    </div>
                  ))}
                </div>
                <div style={{marginTop:8}}>
                  {[["DSL",loc.dsl,4],["DSP",loc.dsp,2],["FUL",loc.ful,2],["FLL",loc.fll,2],
                    ["FUL Diff",loc.ful_diff,2],["FLL Diff",loc.fll_diff,2],
                    ["Distance",loc.distance,2],["Change",loc.change,2],
                    ["CE IV",loc.ce_iv,1],["PE IV",loc.pe_iv,1]].map(([k,v,d])=>(
                    <div key={k} style={{display:"flex",justifyContent:"space-between",
                      padding:"3px 0",fontFamily:"'JetBrains Mono',monospace",fontSize:10,
                      borderBottom:"1px solid rgba(22,32,51,.3)"}}>
                      <span style={{color:"#4a5568"}}>{k}</span>
                      <span style={{color:v>=0?"#dde4ef":"#ff3d5a"}}>{fmt(v,d)}</span>
                    </div>
                  ))}
                </div>
              </>
            ):<div style={{color:"#4a5568",fontSize:10,textAlign:"center",padding:20,lineHeight:1.8}}>
              No LOC data yet<br/>
              <span style={{fontSize:9}}>Waiting for option chain data...</span>
            </div>}
          </div>
        </div>
      </div>
    </div>
  )
}
