import{useRef,useEffect}from'react'
import{fmt,pct,sign,arr,absn}from'../utils'

const cs={
  card:{background:"#0f1624",border:"1px solid #162033",borderRadius:8,padding:12,
    cursor:"pointer",transition:".15s",position:"relative",overflow:"hidden"},
  name:{fontSize:9,color:"#4a5568",fontFamily:"'JetBrains Mono',monospace",textTransform:"uppercase",marginBottom:5},
  price:{fontFamily:"'JetBrains Mono',monospace",fontSize:18,fontWeight:700,marginBottom:2,transition:"color .3s"},
  chg:{fontFamily:"'JetBrains Mono',monospace",fontSize:11},
  bar:{marginTop:7,height:2,background:"#1a2535",borderRadius:1,overflow:"hidden"},
  fill:{height:"100%",transition:"width .4s",borderRadius:1},
  loc:{display:"flex",gap:6,marginTop:5,fontFamily:"'JetBrains Mono',monospace",fontSize:9,alignItems:"center"},
  zone:{padding:"1px 5px",borderRadius:2,fontSize:8,fontWeight:700},
}

export function IndexCard({data,meta,loc,selected,onClick}){
  // Extract from both ltpc and efeed (WS feed uses ltpc, REST snapshot uses efeed)
  const ltpc=data?.ltpc||{}
  const ef=data?.efeed||{}
  const ltp=ltpc.ltp||ef.ltp||0
  const cp=ltpc.cp||ef.cp||0        // prev close — critical for change%
  const high=ef.high||ltp
  const low=(ef.low&&ef.low>0)?ef.low:ltp
  const p=pct(ltp,cp); const dir=sign(p)
  const fp=Math.min(100,Math.max(0,50+parseFloat(p)*8))
  const priceRef=useRef(null); const prevLtp=useRef(ltp)

  useEffect(()=>{
    if(priceRef.current&&prevLtp.current&&prevLtp.current!==ltp&&ltp>0){
      priceRef.current.style.animation="none"
      requestAnimationFrame(()=>{
        if(priceRef.current)
          priceRef.current.style.animation=`${ltp>prevLtp.current?"flash-up":"flash-dn"} .6s ease`
      })
    }
    prevLtp.current=ltp
  },[ltp])

  return(
    <div style={{...cs.card,borderColor:selected?"#ffc94d":"#162033",
      boxShadow:selected?"0 0 0 1px rgba(255,201,77,.3)":"none"}}
      onClick={onClick}
      onMouseEnter={e=>e.currentTarget.style.transform="translateY(-1px)"}
      onMouseLeave={e=>e.currentTarget.style.transform=""}>
      <div style={{position:"absolute",top:0,left:0,right:0,height:2,
        background:dir==="up"?"linear-gradient(90deg,transparent,#00e676,transparent)":"linear-gradient(90deg,transparent,#ff3d5a,transparent)"}}/>
      <div style={cs.name}>{meta.ico} {meta.n}</div>
      <div style={cs.price} ref={priceRef}>{ltp>0?fmt(ltp):"—"}</div>
      <div style={{...cs.chg,color:ltp>0&&cp>0?(dir==="up"?"#00e676":"#ff3d5a"):"#4a5568"}}>
        {ltp>0&&cp>0?`${arr(p)} ${absn(p)}%`:"▲ 0%"}
      </div>
      {ltp>0&&<div style={cs.bar}>
        <div style={{...cs.fill,width:fp+"%",background:dir==="up"?"#00e676":"#ff3d5a"}}/>
      </div>}
      {loc?.zone&&<div style={cs.loc}>
        <span style={{color:"#4a5568"}}>BOP:{fmt(loc.bop,0)}</span>
        <span style={{...cs.zone,
          background:loc.zone==="CALL"?"rgba(0,230,118,.15)":loc.zone==="PUT"?"rgba(255,61,90,.15)":"rgba(255,201,77,.1)",
          color:loc.zone==="CALL"?"#00e676":loc.zone==="PUT"?"#ff3d5a":"#ffc94d"}}>
          {loc.zone}
        </span>
      </div>}
    </div>
  )
}

export function StockCard({data,meta,loc,selected,onClick}){
  const ltpc=data?.ltpc||{}
  const ef=data?.efeed||{}
  const ltp=ltpc.ltp||ef.ltp||0
  const cp=ltpc.cp||ef.cp||0
  const p=pct(ltp,cp); const dir=sign(p)
  const zone=loc?.zone||""
  const zoneBg=zone==="CALL"?"rgba(0,230,118,.05)":zone==="PUT"?"rgba(255,61,90,.05)":"#0f1624"
  const priceRef=useRef(null); const prevLtp=useRef(ltp)

  useEffect(()=>{
    if(priceRef.current&&prevLtp.current&&prevLtp.current!==ltp&&ltp>0){
      priceRef.current.style.animation="none"
      requestAnimationFrame(()=>{
        if(priceRef.current)
          priceRef.current.style.animation=`${ltp>prevLtp.current?"flash-up":"flash-dn"} .5s ease`
      })
    }
    prevLtp.current=ltp
  },[ltp])

  return(
    <div style={{...cs.card,background:zoneBg,
      borderColor:selected?"#ffc94d":zone==="CALL"?"rgba(0,230,118,.15)":zone==="PUT"?"rgba(255,61,90,.15)":"#162033"}}
      onClick={onClick}
      onMouseEnter={e=>e.currentTarget.style.transform="translateY(-1px)"}
      onMouseLeave={e=>e.currentTarget.style.transform=""}>
      {zone&&<div style={{position:"absolute",top:5,right:5,fontSize:7,padding:"1px 4px",
        borderRadius:2,fontFamily:"'JetBrains Mono',monospace",
        background:zone==="CALL"?"rgba(0,230,118,.15)":"rgba(255,61,90,.15)",
        color:zone==="CALL"?"#00e676":"#ff3d5a"}}>{zone}</div>}
      <div style={{fontFamily:"'JetBrains Mono',monospace",fontSize:10,fontWeight:700,marginBottom:4,
        paddingRight:zone?28:0}}>{meta.n}</div>
      <div ref={priceRef} style={{fontFamily:"'JetBrains Mono',monospace",fontSize:13,fontWeight:700}}>
        {ltp>0?fmt(ltp):"—"}
      </div>
      <div style={{fontSize:9,fontFamily:"'JetBrains Mono',monospace",marginTop:1,
        color:ltp>0&&cp>0?(dir==="up"?"#00e676":"#ff3d5a"):"#4a5568"}}>
        {ltp>0&&cp>0?`${arr(p)} ${absn(p)}%`:"▲ 0%"}
      </div>
    </div>
  )
}
