# Auth App Scaffold

React + Express + SQLite + JWT authentication scaffold.

## Architecture

```
src/main.tsx              — BrowserRouter + AuthProvider wrapping
src/hooks/useAuth.ts      — JWT auth hook: login, register, logout, authFetch
src/components/
  ProtectedRoute.tsx      — redirects to /login if not authenticated
src/pages/
  LoginPage.tsx           — email/password login form
  RegisterPage.tsx        — registration form
server/index.js           — JWT auth routes + per-user CRUD factory
```

## Quick start

1. Copy `.env.example` → `.env`, set a strong `JWT_SECRET`
2. `npm run dev` — starts React (Vite :5173) + Express (:3001)
3. Replace `src/App.tsx` routes with your app's protected pages

## useAuth API

```tsx
const { user, token, loading, login, register, logout, authFetch } = useAuth()

// login(email, password)  — throws on failure
// register(email, password)  — throws on failure
// logout()  — clears localStorage, redirects via ProtectedRoute
// authFetch(url, opts)  — fetch with Authorization header auto-added
```

## authCrud(table) — per-user CRUD

In `server/index.js`, call `authCrud("todos")` to get:
```
GET    /api/todos          — user's todos only
POST   /api/todos          — create (user_id auto-set)
PUT    /api/todos/:id      — update (user can only update own)
DELETE /api/todos/:id      — delete (user can only delete own)
```

Each user only sees their own data. No extra WHERE clause needed in the frontend.

## Adding a new table

1. `server/index.js`: Add `CREATE TABLE IF NOT EXISTS` + `authCrud("tablename")`
2. `src/App.tsx`: Add a route → `<ProtectedRoute><YourPage /></ProtectedRoute>`
3. Use `authFetch("/api/tablename", {...})` in your components
