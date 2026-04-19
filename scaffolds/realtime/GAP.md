# GAP — realtime

## Purpose
WebSocket-based collaborative / live scaffold. Server + client +
event protocol. Target: live cursors, live comments, presence indicators,
multiplayer toys.

## Wire state
- **Not routed.** No plan, no keyword hit.
- Zero deliveries.

## Numeric gap
- Delivery count: **0**.
- Target: **≥2 deliveries**.

## Structural blockers (known)
- Two-client testing: vision gate only opens one browser. Real
  realtime QA needs two pages in sync.
- Reconnect logic: drones omit it; first disconnect = broken demo.
- State-sync patterns (CRDT vs last-write-wins vs event log) — drones
  pick inconsistently.

## Churn lever
1. Add `plan_scaffolds/realtime.md` — sections: Protocol, Server,
   Client, Presence, Reconnect.
2. Pin pattern: last-write-wins for most toys; note CRDT as an escape
   hatch for text editors.
3. Delivery gate: playwright opens 2 pages, types in one, asserts the
   text appears in the other within 1s.
4. Ship: live cursors, shared whiteboard, presence list.

## Out of scope
- Persistent storage (sessions die on server restart is fine).
- auth (open WS is fine for the toys).

## Test suite (inference-free)
ws mock in vitest. Spin a real server, two ws clients, assert
broadcast propagation. Parallel-safe via port env.

## Success signal
Two browser tabs synchronize state within 1s of an event. Reconnect
after 5s server kill re-syncs state.
