# Plan: {goal}

## TOC
- [>] [Architecture](#architecture)
- [ ] [Server](#server)
- [ ] [Client](#client)
- [ ] [Routes](#routes)
- [ ] [Tests](#tests)
- [ ] [Build](#build)
- [ ] [Deliver](#deliver)

## Architecture
React + react-router-dom client + Express + better-sqlite3 + bcryptjs +
jsonwebtoken server. Bundled scaffold provides the auth contract:
- `server/index.js` — `/api/auth/register`, `/api/auth/login`, JWT issuance,
  bcrypt hash, users table.
- `src/hooks/useAuth.tsx` — `AuthProvider`, `useAuth()` returning
  `{ user, token, loading, login, register, logout, authFetch }`.
- `src/components/ProtectedRoute.tsx` — route wrapper redirecting to
  `/login` when unauthed.
- `src/pages/LoginPage.tsx` + `RegisterPage.tsx` — starting forms.

Pin: JWT in localStorage, NOT cookies. The bundled hook is the
source of truth — DO NOT roll a second auth state. The contract is
locked in `__fixtures__/auth_flow.tsx`.

## Server
Customize `server/index.js`:
- Add tables to the `db.exec` block — match TS types in any shared
  module; the User shape MUST stay `{ id: number; email: string }`
  (more columns are fine; never drop those two).
- Protected endpoints check `req.headers.authorization` for
  `Bearer <token>`, verify with `jwt.verify(token, JWT_SECRET)`.
- Set `JWT_SECRET` via env in production. The bundled stub uses
  `dev-secret-change-in-production` — fine for local, NEVER ship.

## Client
Wrap the route tree in `<AuthProvider>` (already done in the bundled
`main.tsx`). Pull state via `useAuth()`. Pattern:
```tsx
const { user, login, logout, authFetch } = useAuth()
if (!user) return <LoginPage />
const data = await authFetch("/api/protected").then(r => r.json())
```
Always call `authFetch` for protected endpoints — it sets the
Authorization header automatically. Hand-rolling fetch + header
drifts on token refresh / clear-on-401 logic later.

## Routes
React-router structure:
```tsx
<Routes>
  <Route path="/login" element={<LoginPage />} />
  <Route path="/register" element={<RegisterPage />} />
  <Route path="/" element={<ProtectedRoute><Home /></ProtectedRoute>} />
  <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
</Routes>
```
ProtectedRoute redirects to `/login` when `useAuth().user === null`.
Loading state (token-from-localStorage hydration) shows a spinner
not a redirect — otherwise refresh always bounces to /login.

## Tests
- `Login form submit (valid) → useAuth().user populated, redirect to /`
- `Login form submit (invalid) → error message visible, stays on /login`
- `Register submit → user created, signed in immediately`
- `Logout → user nulled, redirect to /login`
- `ProtectedRoute (unauthed) → redirects to /login`
- `ProtectedRoute (authed) → renders children`
- `authFetch sends Authorization header` (assert via fetch mock)

Mock fetch via `vi.stubGlobal('fetch', ...)`. For routing tests, wrap
in `<MemoryRouter initialEntries={["/"]}>`.

## Build
shell_exec cd {project_path} && npm run build
(runs tsc --noEmit + vite build; tsc also checks `__fixtures__/`)

The dev workflow runs vite + `node --watch server/index.js`
concurrently. Both processes must succeed for the deliverable.

## Deliver
message_result with one-line description.
