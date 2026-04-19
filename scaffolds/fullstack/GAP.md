# GAP — fullstack

## Purpose
Generic Node server + React client with shared TypeScript types in a
`shared/` dir. Target: CRUD app, todo-with-backend, chat app, any
site that needs persistence.

## Wire state
- **Not routed.** Scaffold exists; no plan, no keyword hit.
- Zero deliveries.

## Numeric gap
- Delivery count: **0**.
- Target: **≥2 vision-PASS deliveries**.

## Structural blockers (known)
- Same cross-layer issue as auth-app — two processes, one pipeline.
- Shared types location: drone writes types in `src/` AND `server/`,
  they drift. `shared/types.ts` convention must be prompt-enforced.

## Churn lever
1. Add `plan_scaffolds/fullstack.md` with required `shared/types.ts`
   section — ALL types live there.
2. Auto-build: run vite build + server tsc concurrently.
3. Runtime probe: `curl` the server health endpoint + render the
   client; vision gate sees the rendered client.
4. Ship: CRUD todo, realtime counter, simple chat.

## Out of scope
- auth-app overlaps — that's its own scaffold.
- GraphQL (stick with REST).

## Test suite (inference-free)
Fixtures wire a mock server + client. Vitest runs reducer/state
+ supertest hits the endpoints. Parallel-safe via port env.

## Success signal
Client lists data fetched from server, POST round-trips update the
list, no CORS errors, vision PASS.
