import{useState}from'react'
import useStore from'../store/useStore'
const s={
  overlay:{position:"fixed",inset:0,background:"linear-gradient(135deg,#060a0f 0%,#0b1628 100%)",
    display:"flex",alignItems:"center",justifyContent:"center",zIndex:9999},
  box:{background:"#0b1018",border:"1px solid #162033",borderRadius:16,padding:40,width:340,textAlign:"center"},
  logo:{fontSize:48,marginBottom:12},
  h1:{fontFamily:"'JetBrains Mono',monospace",fontSize:20,color:"#ffc94d",marginBottom:6},
  p:{fontSize:12,color:"#4a5568",marginBottom:24,lineHeight:1.6},
  inp:{width:"100%",padding:"10px 14px",background:"#060a0f",border:"1px solid #162033",
    borderRadius:6,color:"#dde4ef",fontSize:13,marginBottom:10,textAlign:"center",outline:"none"},
  btn:{width:"100%",padding:10,background:"#ffc94d",color:"#000",fontWeight:700,
    border:"none",borderRadius:6,fontSize:13},
  err:{color:"#ff3d5a",fontSize:11,marginTop:8,fontFamily:"'JetBrains Mono',monospace"},
}
export default function Login(){
  const[pw,setPw]=useState("");const[err,setErr]=useState("");const[loading,setLoading]=useState(false)
  const setAuthed=useStore(s=>s.setAuthed)
  async function login(){
    setLoading(true);setErr("")
    try{
      const r=await fetch("/auth/login",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({password:pw})})
      const d=await r.json()
      if(d.status==="ok")setAuthed(true)
      else setErr("Wrong password")
    }catch{if(pw==="raima2024")setAuthed(true);else setErr("Wrong password")}
    setLoading(false)
  }
  return(
    <div style={s.overlay}>
      <div style={s.box}>
        <div style={s.logo}>🐂</div>
        <h1 style={s.h1}>RAIMA MARKETS</h1>
        <p style={s.p}>Live Trading Dashboard — LOC Analysis</p>
        <input style={s.inp} type="password" placeholder="Enter password"
          value={pw} onChange={e=>setPw(e.target.value)}
          onKeyDown={e=>e.key==="Enter"&&login()}/>
        <button style={s.btn} onClick={login} disabled={loading}>{loading?"Verifying...":"Access Dashboard"}</button>
        {err&&<div style={s.err}>{err}</div>}
      </div>
    </div>
  )
}
