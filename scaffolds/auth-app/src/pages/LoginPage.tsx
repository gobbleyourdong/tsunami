import { useState } from "react"
import { useAuth } from "../hooks/useAuth"
import { useNavigate, Link } from "react-router-dom"

export function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError("")
    setLoading(true)
    try {
      await login(email, password)
      navigate("/")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ display:"flex", alignItems:"center", justifyContent:"center", minHeight:"100vh", background:"#f9fafb" }}>
      <div style={{ background:"white", borderRadius:12, padding:40, width:"100%", maxWidth:380, boxShadow:"0 4px 16px rgba(0,0,0,0.08)" }}>
        <h1 style={{ fontSize:22, fontWeight:700, marginBottom:6 }}>Sign in</h1>
        <p style={{ color:"#6b7280", fontSize:14, marginBottom:28 }}>Welcome back</p>
        <form onSubmit={handleSubmit} style={{ display:"flex", flexDirection:"column", gap:14 }}>
          <input type="email" placeholder="Email" value={email} onChange={e => setEmail(e.target.value)} required
            style={{ padding:"10px 14px", border:"1px solid #d1d5db", borderRadius:8, fontSize:15 }} />
          <input type="password" placeholder="Password" value={password} onChange={e => setPassword(e.target.value)} required
            style={{ padding:"10px 14px", border:"1px solid #d1d5db", borderRadius:8, fontSize:15 }} />
          {error && <p style={{ color:"#dc2626", fontSize:13, margin:0 }}>{error}</p>}
          <button type="submit" disabled={loading}
            style={{ padding:"11px 0", background:"#2563eb", color:"white", border:"none", borderRadius:8, fontSize:15, fontWeight:600, cursor:"pointer" }}>
            {loading ? "Signing in…" : "Sign in"}
          </button>
        </form>
        <p style={{ textAlign:"center", marginTop:20, fontSize:14, color:"#6b7280" }}>
          No account? <Link to="/register" style={{ color:"#2563eb" }}>Register</Link>
        </p>
      </div>
    </div>
  )
}
