#!/usr/bin/env python3
"""build_auth_app_dpo_v1.py — DPO training data for the auth-app-v1 adapter.

18 pairs (3 per fault, 6 faults):
  AUF01 — template choice: template="auth-app" not "fullstack" or "react-app"
  AUF02 — server first: write server/index.js (auth routes) before App.tsx
  AUF03 — authFetch: use authFetch() from useAuth(), never raw fetch() for protected routes
  AUF04 — ProtectedRoute: wrap all authenticated pages in <ProtectedRoute>
  AUF05 — undertow before message_result
  AUF06 — file_edit on error, not file_read
"""
import json, sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

OUT = Path("workspace/training_data/auth_app_dpo_v1.jsonl")
TODAY = str(date.today())


def pair(source_bug, chosen, rejected, note):
    return {
        "prompt": f"[AUF probe: {source_bug}]",
        "chosen": chosen,
        "rejected": rejected,
        "source_bug": source_bug,
        "note": note,
        "images": [],
        "date": TODAY,
    }


# ── AUF01: template choice ─────────────────────────────────────────────────────
AUF01_PAIRS = [
    pair("AUF01a",
         chosen='project_init(name="notes-app", template="auth-app")',
         rejected='project_init(name="notes-app", template="fullstack")',
         note="Notes app with user accounts → template=auth-app, not fullstack (needs JWT + bcrypt)"),
    pair("AUF01b",
         chosen='project_init(name="expense-tracker", template="auth-app")',
         rejected='project_init(name="expense-tracker", template="react-app")',
         note="Expense tracker with login → auth-app template, not bare react-app (no server in react-app)"),
    pair("AUF01c",
         chosen='project_init(name="task-manager", template="auth-app") # JWT login + per-user tasks',
         rejected='project_init(name="task-manager", template="fullstack")  # fullstack has no auth layer',
         note="Task manager with user accounts → explicit template=auth-app, not fullstack (needs bcryptjs + JWT)"),
]

# ── AUF02: server first ────────────────────────────────────────────────────────
AUF02_PAIRS = [
    pair("AUF02a",
         chosen="1. project_init(template='auth-app')\n2. file_write server/index.js  ← auth routes first\n3. file_write src/App.tsx",
         rejected="1. project_init(template='auth-app')\n2. file_write src/App.tsx  ← UI first\n3. file_write server/index.js",
         note="Write server/index.js before App.tsx — login/register forms call /api/auth which must exist"),
    pair("AUF02b",
         chosen="project_init → file_write server/index.js (POST /api/auth/register + /api/auth/login + requireAuth) → file_write src/App.tsx with useAuth",
         rejected="project_init → file_write src/App.tsx → file_write server/index.js",
         note="Auth server is the foundation — useAuth() calls /api/auth; must exist before testing the frontend"),
    pair("AUF02c",
         chosen="After project_init: write server/index.js with bcrypt hash+compare, JWT sign, requireAuth middleware, then write App.tsx",
         rejected="After project_init: write App.tsx with login form first, then add server/index.js later",
         note="Auth routes define the API contract; write the server before writing forms that call it"),
]

# ── AUF03: authFetch ──────────────────────────────────────────────────────────
AUF03_PAIRS = [
    pair("AUF03a",
         chosen="const { authFetch } = useAuth()\nconst res = await authFetch('/api/notes', { method: 'POST', body: JSON.stringify({title, body}) })",
         rejected="const token = localStorage.getItem('auth_token')\nconst res = await fetch('/api/notes', { method:'POST', headers:{'Authorization':`Bearer ${token}`}, body: ... })",
         note="Use authFetch() from useAuth() — it auto-adds the Authorization header; never manually get the token"),
    pair("AUF03b",
         chosen="authFetch('/api/todos', { method: 'DELETE', ... })  // auto Authorization: Bearer",
         rejected="fetch('/api/todos', { method: 'DELETE', headers: { 'Authorization': 'Bearer ' + token } })",
         note="Raw fetch() with manual token is error-prone; authFetch() centralizes auth header injection"),
    pair("AUF03c",
         chosen="All protected API calls use authFetch(url, opts) from useAuth(). Raw fetch() only for /api/auth/login and /api/auth/register (unauthenticated).",
         rejected="All API calls use fetch() with manual headers: { Authorization: `Bearer ${localStorage.getItem('auth_token')}` }",
         note="authFetch() is the contract: only use raw fetch() for unauthenticated login/register endpoints"),
]

# ── AUF04: ProtectedRoute ─────────────────────────────────────────────────────
AUF04_PAIRS = [
    pair("AUF04a",
         chosen="<Route path='/dashboard' element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />",
         rejected="<Route path='/dashboard' element={<Dashboard />} />  // no protection — anyone can navigate",
         note="All authenticated pages must be wrapped in <ProtectedRoute>; bare <Route> is accessible to everyone"),
    pair("AUF04b",
         chosen="<ProtectedRoute><NotesPage /></ProtectedRoute>  // redirects to /login if not authenticated",
         rejected="{ user ? <NotesPage /> : <Navigate to='/login' /> }  // manual guard duplicated at every route",
         note="Use <ProtectedRoute> consistently; manual ternary guards scattered across routes are brittle"),
    pair("AUF04c",
         chosen="App.tsx routes: /login → <LoginPage>, /register → <RegisterPage>, /app/* → <ProtectedRoute><AppShell /></ProtectedRoute>",
         rejected="App.tsx routes: /login → <LoginPage>, /register → <RegisterPage>, /app/* → <AppShell /> (no guard)",
         note="Every non-auth route must use <ProtectedRoute>; forgetting it means logged-out users see protected data"),
]

# ── AUF05: undertow before message_result ─────────────────────────────────────
AUF05_PAIRS = [
    pair("AUF05a",
         chosen="npm run build ✓ → undertow() → [screenshot: login form renders, notes load after login] → message_result(done=True)",
         rejected="npm run build ✓ → message_result('Auth app is ready', done=True)  # no visual verification",
         note="Always undertow() after build for auth apps — verify login form renders and protected routes redirect correctly"),
    pair("AUF05b",
         chosen="shell_exec('npm run build') → undertow → message_result → done",
         rejected="shell_exec('npm run build') → message_result → done  # visual QA skipped",
         note="Skip undertow = deliver without QA; auth redirect bugs (ProtectedRoute loop, blank screen) won't show in build output"),
    pair("AUF05c",
         chosen="Build success → undertow() confirms login page renders and /dashboard redirects to /login → message_result",
         rejected="Build success → immediately message_result without checking UI",
         note="Auth flows need visual check — blank screen or infinite redirect won't appear in tsc/vite build logs"),
]

# ── AUF06: file_edit on error ──────────────────────────────────────────────────
AUF06_PAIRS = [
    pair("AUF06a",
         chosen="Build fails: 'Cannot find module jsonwebtoken' → file_edit(package.json, add jsonwebtoken dep) → npm install → npm run build",
         rejected="Build fails: 'Cannot find module jsonwebtoken' → file_read(server/index.js) → file_read(package.json) → ...",
         note="Missing module with clear cause → file_edit directly, no re-reading files first"),
    pair("AUF06b",
         chosen="TypeError: bcrypt.hash is not a function (server/index.js:23) → file_edit(server/index.js, replace bcrypt with bcryptjs)",
         rejected="TypeError: bcrypt.hash is not a function → file_read(server/index.js) to 'investigate'",
         note="Runtime error with line number → file_edit the specific line, don't file_read first"),
    pair("AUF06c",
         chosen="SyntaxError: Cannot use import statement in server/index.js → file_edit to add 'type':'commonjs' to server package.json or switch to require()",
         rejected="SyntaxError in server/index.js → file_read to understand the problem before editing",
         note="ESM/CJS syntax error is self-explanatory — edit immediately without reading first"),
]


def main():
    all_pairs = AUF01_PAIRS + AUF02_PAIRS + AUF03_PAIRS + AUF04_PAIRS + AUF05_PAIRS + AUF06_PAIRS
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w") as f:
        for p in all_pairs:
            f.write(json.dumps(p) + "\n")
    print(f"Wrote {len(all_pairs)} pairs to {OUT}")
    for p in all_pairs:
        print(f"  {p['source_bug']}: {p['note'][:65]}")


if __name__ == "__main__":
    main()
