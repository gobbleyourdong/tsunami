# GAP — auth-app

## Purpose
React client + Node server with auth flow (signup / login / session).
Has `src/` and `server/` — drones must coordinate across layers.

## Wire state
- **Not routed.** No plan_scaffold; `_pick_scaffold` has alias but
  no detection.
- Zero deliveries.

## Numeric gap
- Delivery count: **0**.
- Target: **≥2 vision-PASS deliveries** (fewer because cross-layer
  is harder — let's not overpromise).

## Structural blockers (known)
- Two-process build (server + vite). Auto-build only runs one at a
  time; the pipeline currently assumes single-process.
- JWT / session-cookie choice is load-bearing and drones pick
  inconsistently.
- Vision gate can't test auth interactively — login flow is
  behaviour, not visuals.

## Churn lever
1. Add `plan_scaffolds/auth-app.md` — sections: Server, Schema,
   Routes, Client, Flow, Build, Deliver.
2. Extend auto-build to cover both `src/` (vite) and `server/`
   (tsx / ts-node). Run them in parallel; both must pass.
3. Add a behavioural test: spin up server, POST /signup + /login,
   assert 200 and cookie set.
4. Ship: magic-link auth, password + 2FA, OAuth stub.

## Out of scope
- Real OAuth providers (stub the redirect).
- Database persistence (sqlite file or in-memory is enough).

## Test suite (inference-free)
Fixtures: in-memory server (`tsx fixture-server.ts &`), supertest
calls, assertion on response shape + cookies. `vitest` runs the
client-side reducer/state. Parallel-safe — each instance picks a
different port via env.

## Success signal
Signup → login → protected-page flow end-to-end green. Server logs
show no unhandled rejections.
