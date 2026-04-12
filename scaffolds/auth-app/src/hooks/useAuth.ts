import { useState, useEffect, createContext, useContext, useCallback } from "react"

export interface User { id: number; email: string }
interface AuthState { user: User | null; token: string | null; loading: boolean }
type AuthContextType = AuthState & {
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string) => Promise<void>
  logout: () => void
  authFetch: (url: string, opts?: RequestInit) => Promise<Response>
}

/**
 * useAuth — JWT auth hook.
 * Persists token + user in localStorage.
 * authFetch() wraps all API calls with Authorization header.
 */
function useAuthProvider(): AuthContextType {
  const [state, setState] = useState<AuthState>({ user: null, token: null, loading: true })

  useEffect(() => {
    const token = localStorage.getItem("auth_token")
    const userStr = localStorage.getItem("auth_user")
    if (token && userStr) {
      try {
        setState({ user: JSON.parse(userStr), token, loading: false })
      } catch {
        localStorage.removeItem("auth_token")
        localStorage.removeItem("auth_user")
        setState({ user: null, token: null, loading: false })
      }
    } else {
      setState(prev => ({ ...prev, loading: false }))
    }
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    })
    const data = await res.json()
    if (!res.ok) throw new Error(data.error || "Login failed")
    localStorage.setItem("auth_token", data.token)
    localStorage.setItem("auth_user", JSON.stringify(data.user))
    setState({ user: data.user, token: data.token, loading: false })
  }, [])

  const register = useCallback(async (email: string, password: string) => {
    const res = await fetch("/api/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    })
    const data = await res.json()
    if (!res.ok) throw new Error(data.error || "Registration failed")
    localStorage.setItem("auth_token", data.token)
    localStorage.setItem("auth_user", JSON.stringify(data.user))
    setState({ user: data.user, token: data.token, loading: false })
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem("auth_token")
    localStorage.removeItem("auth_user")
    setState({ user: null, token: null, loading: false })
  }, [])

  const authFetch = useCallback((url: string, opts: RequestInit = {}) => {
    const token = localStorage.getItem("auth_token")
    return fetch(url, {
      ...opts,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...opts.headers,
      },
    })
  }, [])

  return { ...state, login, register, logout, authFetch }
}

const AuthContext = createContext<AuthContextType>(null!)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  return <AuthContext.Provider value={useAuthProvider()}>{children}</AuthContext.Provider>
}

export function useAuth() { return useContext(AuthContext) }
