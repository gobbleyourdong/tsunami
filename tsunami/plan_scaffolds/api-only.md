# Plan: {goal}

Headless REST / webhook service. No React, no DOM. The deliverable is
a Node (Fastify/Express) or Hono service that listens on `PORT` and
serves its own OpenAPI spec at `/openapi.json`. Vision gate doesn't
apply; delivery is gated by `tsunami.core.openapi_probe`.

## TOC
- [>] [Spec](#spec)
- [ ] [Handlers](#handlers)
- [ ] [Tests](#tests)
- [ ] [Build](#build)
- [ ] [Deliver](#deliver)

## Spec
Start from the OpenAPI doc, not the handlers. Write `src/openapi.ts`
exporting one `spec` object:

```
openapi: '3.1.0'
info: { title, version: '1.0.0' }
paths: {
  '/widgets': { get, post },
  '/widgets/{id}': { get, delete },
  ...
}
```

Every endpoint the service advertises MUST appear in the spec — the
probe walks `paths` and hits each one. A handler that exists but is
undocumented won't delivery-pass.

## Handlers
One file per resource: `src/routes/widgets.ts`. Each handler:
- Reads validated input (zod.safeParse → 400 on issues)
- Returns JSON with an explicit HTTP status
- Throws nothing — wrap errors, return 500 JSON bodies

Bind `PORT` from `process.env.PORT` in `src/index.ts`. The probe
injects an ephemeral port; hard-coded 3000 will make the gate fail.

Also wire `GET /openapi.json → res.json(spec)` and `GET /health
→ res.json({ ok: true })`.

## Tests
Write `tests/routes.test.ts` with vitest + supertest:
- Each endpoint: happy path + one edge (missing field → 400, bad id → 404)
- No auth? Test that the endpoint is reachable.
- Mock external IO (DB, outbound HTTP) — the probe runs against the real process but tests run in isolation.

## Build
shell_exec cd {project_path} && npm run build
(tsc + any bundler). Must produce a runnable `node dist/index.js`.

## Deliver
`message_result` with the one-line description. The wave's delivery
gate spawns the server, fetches `/openapi.json`, validates 3.x shape,
and liveness-probes every declared path. A 5xx on any endpoint blocks
delivery; 4xx is fine (we're probing shape, not correctness).
