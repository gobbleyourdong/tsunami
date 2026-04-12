import { useAuth } from "../hooks/useAuth"
import { Navigate } from "react-router-dom"

/**
 * ProtectedRoute — redirects to /login if not authenticated.
 * Usage: <ProtectedRoute><Dashboard /></ProtectedRoute>
 */
export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) return (
    <div style={{ display:"flex", alignItems:"center", justifyContent:"center", height:"100vh", color:"#888" }}>
      Loading…
    </div>
  )
  if (!user) return <Navigate to="/login" replace />
  return <>{children}</>
}
