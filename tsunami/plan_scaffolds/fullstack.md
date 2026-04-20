# Plan: {goal}

## TOC
- [>] [Architecture](#architecture)
- [ ] [Shared types](#shared-types)
- [ ] [Server](#server)
- [ ] [Client](#client)
- [ ] [Tests](#tests)
- [ ] [Build](#build)
- [ ] [Deliver](#deliver)

## Architecture
React (Vite) client + Express (Node) server + better-sqlite3 in a single
repo. Two processes, one deliverable. The drone-natural CRUD pattern:

  client (`src/App.tsx` + `src/components/useApi.ts`) ──fetch──▶ server (`server/index.js`)
                                       │                                    │
                                       └─── shared types from `shared/` ────┘
                                                                  │
                                                            SQLite (`server/data.db`)

Pin: ALL types live in `shared/types.ts`. The client imports from
`../../shared/types`; the server imports the same module. Drift is the
#1 fullstack failure mode — keep one source of truth.

## Shared types
Create `shared/types.ts` at the repo root with one type per resource:
```ts
// shared/types.ts
export interface Item {
  id: number
  name: string
  description?: string
  status: "active" | "archived"
  createdAt: string
  updatedAt: string
}
export type ItemDraft = Omit<Item, "id" | "createdAt" | "updatedAt">
```
Both `src/` and `server/` import from this file. NEVER duplicate the
shape — drift breaks API contracts at runtime, not compile time.

## Server
`server/index.js` is the existing scaffold stub: Express, CORS, a
generic `items` table, and CRUD routes. Customize the schema + routes:
- Schema: define each table via better-sqlite3's exec API at startup.
  Match the columns to `shared/types.ts` exactly — drift here is the
  #1 source of runtime 500s on fields the type promises but the table
  doesn't have.
- Routes follow REST: `GET /api/<resource>`, `GET /:id`, `POST /`,
  `PUT /:id`, `DELETE /:id`. Return JSON, set 4xx on validation errors.
- Validate body shape on POST/PUT — drones forget this and SQLite swallows
  garbage. One inline check per endpoint is enough.

## Client
Use the bundled `useApi` hook from `src/components/useApi.ts`:
```tsx
const { data, loading, error, create, update, remove, refresh } = useApi<Item>("items")
```
Compose UI from `./components/ui` primitives. Drone-natural prop
shapes are locked into `__fixtures__/{drone_natural,fullstack_patterns}.tsx` —
read those for canonical CRUD-list / form / dialog patterns.

Don't roll a second fetch wrapper. If you need optimistic updates,
add them inside `useApi` (or a sibling hook) — keep the API surface
consistent across the whole client.

## Tests
`src/App.test.tsx`. One behavioral test per CRUD action:
- `Empty list → renders empty-state Alert`
- `Create form submit → row appears, list refreshes`
- `Delete confirm → dialog opens, row removed on confirm`
- `Server 500 → error Alert renders, list still mounts`

Mock fetch via `vi.stubGlobal('fetch', ...)` returning the canonical
JSON shape; no real server needed for unit tests.

For end-to-end, the build script can spin up the server and probe via
fetch — leave that gate to the wave's harness.

## Build
shell_exec cd {project_path} && npm run build
(runs tsc --noEmit + vite build; tsc also checks `__fixtures__/`)

The dev workflow uses `npm run dev` which runs vite + `node --watch
server/index.js` concurrently. Don't ship a build that only succeeds
under one of those two — both must work.

## Deliver
message_result with one-line description.
