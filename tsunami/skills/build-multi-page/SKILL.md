# Build a multi-page app (dashboard / auth flow / routed UI)

Multi-page apps fail differently than single-page ones: rework cascades when you build pages before routing, or build protected pages before auth. Respect dependencies, test the critical path early, and never skip ahead to polish.

## When

Prefer this skill (over `build-react`) when the prompt contains any of:

- **Routing signals**: "dashboard", "multi-page", "tabs", "pages", "sidebar", "nav", "navigation", "routes", "router"
- **Auth signals**: "login", "signup", "auth", "authentication", "user", "account", "profile", "settings"
- **Shell signals**: "SaaS", "admin panel", "CMS", "CRM", "portal"
- **Explicit multi-view**: "with a home page and ...", "two pages", "three views", "a landing and a dashboard"

If the prompt is just "build a counter / dice roller / color picker / calculator" → use `build-react` instead. Single-file is enough there.

## Pipeline (dependency-driven, 7 phases)

Each phase MUST complete + compile cleanly before the next. Don't skip ahead.

### Phase 1 — Foundation
1. `project_init(name)` — pick a descriptive kebab-case name
2. (Mental step, no tool) — decide: route list, auth required?, data source

### Phase 2 — Layout & Navigation (ROUTING FIRST)
Write in this order — routing before pages:
1. `file_write` `src/App.tsx` with `<BrowserRouter>` + `<Routes>` + `<Route>` declarations for every page you plan. Use stub components (`const Home = () => <div>Home</div>`) — they'll be filled in later.
2. `file_write` `src/components/Layout.tsx` with sidebar/header + `{children}` slot
3. `file_write` `src/components/Navigation.tsx` with `<Link>` elements matching the routes from step 1
4. `shell_exec` `npm run build` — MUST compile before moving on

### Phase 3 — Public pages (Home, Login, Signup)
1. `file_write` `src/pages/Home.tsx` — hero + CTA, static content is fine
2. `file_write` `src/pages/Login.tsx` — form with email/password inputs
3. `file_write` `src/pages/Signup.tsx` — similar
4. `shell_exec` `npm run build`
5. `undertow` to verify — pages load without errors. Skip deep QA here; just a smoke test.

### Phase 4 — Auth system (CRITICAL PATH)
Auth is the most common failure point. Build + test it BEFORE protected pages:
1. `file_write` `src/auth/AuthContext.tsx` — provider + `useAuth` hook (simple localStorage or in-memory is fine; real backend comes later)
2. `file_write` `src/auth/ProtectedRoute.tsx` — wraps routes, redirects unauthenticated users to `/login`
3. `file_edit` `src/App.tsx` — wrap protected `<Route>`s in `<ProtectedRoute>`
4. `shell_exec` `npm run build`
5. `undertow` with expect describing the full login → redirect-to-protected-page flow

### Phase 5 — Protected pages (Dashboard, Profile, Settings)
Only AFTER auth works. Otherwise you'll rebuild when auth assumptions change.
1. `file_write` each protected page
2. `shell_exec` `npm run build`

### Phase 6 — Data layer (only if task needs fetched data)
1. `file_write` `src/api/client.ts` — fetch helpers
2. `file_write` `src/hooks/useData.ts` — loading/error/data state
3. `file_edit` pages to consume the hook
4. `shell_exec` `npm run build`

### Phase 7 — Deliver
1. Final `undertow` with full-flow expect
2. `message_result(text=..., attachments=[<dist/index.html>])`

## Gotchas

- **Routing before pages.** Pages built first = rework when you realize layout needs to wrap them. Write `App.tsx` with routes + stub components FIRST.
- **Auth before protected pages.** If auth is broken, every protected page has to be retested. Catch it once, at the auth layer.
- **One file_write per phase step.** Don't batch 10 files in one giant write — small steps let undertow catch compile errors early, before 10 files have the same bug.
- **No polish until Phase 7.** CSS fine-tuning, a11y, animations come last. If functionality is broken, polish is wasted work.
- **`npm run build` between phases.** Not `vite build` bare — the `tsc --noEmit` in `npm run build` catches missing imports and type errors that bare vite silently allows.
- **Skip Phase 6 for static apps.** If the prompt doesn't imply fetched data, don't invent it.
- **Protected route pattern:**
  ```tsx
  <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
  ```
  Don't invent alternative patterns; this one works.
- **Always import UI from the barrel `./components/ui`, never a direct subpath.** Subpaths like `./components/ui/Button` fail because the components only have `export default`, no named export — `import { Button } from "./components/ui/Button"` triggers TS2307. Use the relative path matching the file's location: from `src/App.tsx` → `"./components/ui"`; from `src/components/Layout.tsx` → `"./ui"`; from `src/pages/Home.tsx` → `"../components/ui"`. **Do NOT use the `@/` alias** — it's only configured in the react-app scaffold's vite.config.ts, not in dashboard/data-viz/form-app/landing/realtime/fullstack. hnresearch session `tsu_prog_hnresearch_1776258270` regressed 900s on `import { ... } from "@/components/ui"` in the dashboard scaffold which has no @ alias. Lunchvote session `tsu_prog_lunchvote_1776246326` regressed 20 iters on `import { Button } from "./components/ui/Button"` with no named export.
- **`Button` has NO `as` prop — use wrap pattern for Button-as-link.** `<Button as={Link} to="/foo">Label</Button>` fails TS2322 ("Type '{ as: ...; to: string; variant: string; children: string; }' is not assignable to type 'IntrinsicAttributes & ButtonHTMLAttributes<HTMLButtonElement>'"). Only `Heading` is polymorphic (`as="h1".."h6"`). For nav buttons in `Navigation.tsx` / sidebar / header, wrap the Button inside the Link instead: `<Link to="/foo"><Button variant="ghost">Label</Button></Link>`. Seen in lunchvote session `tsu_prog_lunchvote_1776351209` (multi-page voting app, Layout.tsx `<Button as={Link} to="/vote">` ×4 cross-class TS2322 cascade) and leads session `tsu_prog_leads_1776336039` (CRM Navigation.tsx same pattern). #71 PROMOTED n=3, first cross-skill occurrence.
