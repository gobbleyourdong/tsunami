# GAP — api-only

## Purpose
Backend-only scaffold. Node + Express/Fastify, no UI. Target:
webhooks, tiny APIs, microservice stubs.

## Wire state
- **Not routed.** Scaffold exists; no plan, no keyword hit.
- Zero deliveries.

## Numeric gap
- Delivery count: **0**.
- Target: **≥2 vision-PASS-equivalent deliveries** (see gate below —
  vision gate doesn't apply).

## Structural blockers (known)
- **No vision gate** — api-only has no UI to screenshot. Need an
  alternate delivery gate.
- OpenAPI spec validation would be the right shape: drone writes
  handlers + spec, gate validates handler matches spec + probes each
  endpoint returns the declared shape.

## Churn lever
1. Add `plan_scaffolds/api-only.md` — sections: Spec, Handlers,
   Tests, Deliver.
2. Build a delivery gate: `openapi_probe.py` or similar that reads
   the spec, hits each endpoint with fixtures, asserts response shape
   matches. Replaces vision_gate.py for api-only.
3. Route on `REST API / backend only / webhooks / microservice /
   API server`.
4. Ship: webhook receiver, URL shortener, feature-flag service.

## Out of scope
- GraphQL (separate scaffold if anyone wants it).
- gRPC (same).

## Test suite (inference-free)
Supertest + vitest. `npm test` runs the whole surface. 100% parallel-
safe — each instance gets its own port via env.

## Success signal
All declared endpoints respond with shape matching the spec.
