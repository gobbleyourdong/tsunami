// TODO: Replace with your app (routes go here)
// The AuthProvider and BrowserRouter are already set up in main.tsx.
// Use useAuth() to access: user, token, login, register, logout, authFetch
// Use <ProtectedRoute> to guard pages that require login.
import { Routes, Route, Navigate } from "react-router-dom"
import { useAuth } from "./hooks/useAuth"
import { LoginPage } from "./pages/LoginPage"
import { RegisterPage } from "./pages/RegisterPage"
import { ProtectedRoute } from "./components/ProtectedRoute"

function Dashboard() {
  const { user, logout } = useAuth()
  return (
    <div style={{ padding: 32 }}>
      <h1>Welcome, {user?.email}</h1>
      <button onClick={logout}>Log out</button>
    </div>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
