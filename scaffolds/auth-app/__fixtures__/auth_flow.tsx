/**
 * Auth-app contract fixture. The scaffold ships a `useAuth` hook + an
 * `AuthProvider` + a `<ProtectedRoute>` wrapper. This fixture pins the
 * shape of the contract drones MUST honor:
 *   - useAuth returns { user, token, loading, login, register, logout, authFetch }
 *   - login(email, password) → Promise<void>, throws on bad creds
 *   - authFetch(url, opts) → Promise<Response> with Authorization header
 *   - User shape: { id: number, email: string }
 *   - ProtectedRoute renders children when authed, <Navigate to="/login"> otherwise
 *
 * Compile-only: tsc validates the surface. No runtime — picked up by
 * tsconfig include `__fixtures__`.
 */
import { useAuth, AuthProvider, type User } from "../src/hooks/useAuth"
import { ProtectedRoute } from "../src/components/ProtectedRoute"
import { useState, useEffect, type ReactNode } from "react"

function LoginForm() {
  const { login, loading, user } = useAuth()
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  // The drone-natural pattern: try/catch around the promise; show error
  // banner on failure; the hook handles localStorage + setState.
  const handleSubmit = async () => {
    setBusy(true)
    setError(null)
    try {
      await login(email, password)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  if (loading) return <div>Loading…</div>
  if (user) return <div>Signed in as {user.email}</div>

  return (
    <form onSubmit={e => { e.preventDefault(); void handleSubmit() }}>
      {error && <div role="alert">{error}</div>}
      <input value={email} onChange={e => setEmail(e.target.value)} type="email" placeholder="Email" />
      <input value={password} onChange={e => setPassword(e.target.value)} type="password" placeholder="Password" />
      <button type="submit" disabled={busy || !email || !password}>Sign in</button>
    </form>
  )
}

function RegisterForm() {
  const { register } = useAuth()
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")

  return (
    <form onSubmit={e => {
      e.preventDefault()
      void register(email, password)
    }}>
      <input value={email} onChange={e => setEmail(e.target.value)} type="email" />
      <input value={password} onChange={e => setPassword(e.target.value)} type="password" />
      <button type="submit">Create account</button>
    </form>
  )
}

function ProfileBadge() {
  const { user, logout } = useAuth()
  if (!user) return null
  // User shape lock — id (number) + email (string). If either changes,
  // every drone-side profile component breaks here first.
  const _id: number = user.id
  const _email: string = user.email
  void _id; void _email

  return (
    <div>
      <span>{user.email}</span>
      <button onClick={logout}>Sign out</button>
    </div>
  )
}

function ProtectedDashboard({ children }: { children: ReactNode }) {
  // ProtectedRoute is a wrapper; drone hands it children, expects
  // it to render them when authed and redirect to /login otherwise.
  return <ProtectedRoute>{children}</ProtectedRoute>
}

function AuthedFetcher() {
  const { authFetch, token } = useAuth()
  const [items, setItems] = useState<unknown[]>([])

  useEffect(() => {
    if (!token) return
    let cancelled = false
    void (async () => {
      // authFetch is the canonical pattern — always sets the Bearer
      // header from localStorage. Drones who roll their own fetch + JWT
      // header lose the consistent error/refresh behavior.
      const res = await authFetch("/api/items")
      if (cancelled) return
      if (res.ok) setItems(await res.json())
    })()
    return () => { cancelled = true }
  }, [authFetch, token])

  return <div>{items.length} items</div>
}

// Type-only assertion — proves User is the shape we expect across the
// drone surface. If useAuth ever changes User shape, this fails first.
type UserMustHave = User & { id: number; email: string }
const _userTypeProbe: UserMustHave | null = null
void _userTypeProbe

export default function AuthFlowFixture() {
  return (
    <AuthProvider>
      <LoginForm />
      <RegisterForm />
      <ProfileBadge />
      <ProtectedDashboard>
        <AuthedFetcher />
      </ProtectedDashboard>
    </AuthProvider>
  )
}
