# Scaffold Catalog Status

> **2026-04-26 update.** This file used to be a multi-instance rollout
> coordination doc — one sigma instance per scaffold, work-the-GAP.md,
> live-inference lock, contention rules. The local-LLM stack was
> retired (see `../tsunami/CHANGELOG.md`); tsunami is no longer invoked
> as a binary; there are no parallel sigma instances anymore. This file
> is now a simpler **catalog-status reference**: which scaffolds are in
> the catalog, what shipped with each, and which gate verifies them.

## Catalog (20 scaffolds, all closed)

All scaffolds below have shipped. Their `GAP.md` rollout files have been
deleted per the original convention ("when a gap closes, delete its
GAP.md"). The full per-scaffold deliverable list is preserved here for
reference.

### Vision-gated (web)

| Scaffold | What landed | Plan |
|---|---|---|
| react-app | 38/44 UI components widened to drone-natural prop vocab; `__fixtures__/{drone_natural,landing_dashboard_gallery}.tsx` locked into tsconfig include | `../tsunami/plan_scaffolds/react-build.md` |
| landing | Synced widened UI from react-app; `__fixtures__/{drone_natural,landing_patterns}.tsx`; routing | `../tsunami/plan_scaffolds/landing.md` |
| dashboard | Synced widened UI; `__fixtures__/{drone_natural,dashboard_patterns}.tsx`; recharts API hints in plan; routing | `../tsunami/plan_scaffolds/dashboard.md` |
| data-viz | Synced widened UI; `__fixtures__/{drone_natural,dataviz_patterns}.tsx`; chart-type catalog in plan; routing | `../tsunami/plan_scaffolds/data-viz.md` |
| form-app | Synced widened UI; `__fixtures__/{drone_natural,form_patterns}.tsx`; validation conventions in plan; routing | `../tsunami/plan_scaffolds/form-app.md` |
| fullstack | Synced widened UI; `__fixtures__/{drone_natural,fullstack_patterns}.tsx` exercising `useApi` CRUD; shared/types.ts pin in plan; routing | `../tsunami/plan_scaffolds/fullstack.md` |
| realtime | Synced widened UI; `__fixtures__/{drone_natural,realtime_patterns}.tsx` exercising `useWebSocket` + presence; tagged-union protocol + reconnect in plan; routing | `../tsunami/plan_scaffolds/realtime.md` |
| auth-app | `__fixtures__/auth_flow.tsx` locking `useAuth` contract (`{user,token,login,register,logout,authFetch}`) + ProtectedRoute; routing; renamed `useAuth.ts → .tsx` (pre-existing JSX-in-.ts tsc bug) | `../tsunami/plan_scaffolds/auth-app.md` |
| ai-app | `__fixtures__/chat_stream.tsx` locking `useChat` contract + standalone `parseSSE` helper; SSE wire format pinned in plan; routing | `../tsunami/plan_scaffolds/ai-app.md` |

All 9 verify via `../tsunami/vision_gate.py` (Playwright screenshot →
vision-VLM compare). The vision_gate is currently fail-closed pending
re-wiring to the Claude vision API — see `../tsunami/CLAUDE.md` and
`../tsunami/CHANGELOG.md` v3.6 for the deferred-state details.

### Bespoke-gate (no vision-gate applies)

| Scaffold | Bespoke probe | Plan |
|---|---|---|
| api-only | `../tsunami/core/openapi_probe.py` (OpenAPI handler-vs-spec) | `../tsunami/plan_scaffolds/api-only.md` |
| chrome-extension | `../tsunami/core/extension_probe.py` (load-unpacked headless playwright) | `../tsunami/plan_scaffolds/chrome-extension.md` |
| electron-app | `../tsunami/core/electron_probe.py` (build + artifact check, no GUI) | `../tsunami/plan_scaffolds/electron-app.md` |

All 3 probes exist in `core/` and are dispatched via
`../tsunami/core/dispatch.py`'s `_PROBES` dict (line ~49). Adding a
new bespoke-gate scaffold: see the META section in
`../tsunami/CLAUDE.md`.

### Games

| Scaffold | What it is | Probe |
|---|---|---|
| game | High-level game scaffold base | `../tsunami/core/gamedev_scaffold_probe.py` |
| engine | WebGPU game engine + design stack (`tests/{frame_loop,score_system,keyboard_input,ecs_scene}.test.ts` 51/51 green) | (same — exercises `@engine/*` drone surface) |
| gamedev | Data-driven gamedev scaffold parent. Holds 10 genre subdirs (`gamedev/{action_adventure, beat_em_up, cross, custom, fighting, fps, jrpg, platformer, racing, stealth}`). Builds emit `data/*.json` + edit `src/scenes/*.ts` per the genre_scaffolds plan. | `../tsunami/core/gamedev_scaffold_probe.py` |

`scaffolds/gamedev/{action_adventure, beat_em_up, cross, custom,
fighting, fps, jrpg, platformer, racing, stealth}/` are the 10 genre
sub-scaffolds. The 18 `genre_scaffolds/<name>.md` plans in
`tsunami/genre_scaffolds/` apply to every game build (use
`gamedev/custom/` for genres without a dedicated subdir — see
`../tsunami/CLAUDE.md` games table).

### Lighter scaffolds (no README, smaller surface)

`cli`, `mobile`, `infra`, `web`, `training` — minimal templates without
the full closed-status deliverables tracked above. Read the dir
contents directly. Probes for the routable ones live in
`../tsunami/core/{cli_probe, mobile_probe, infra_probe, training_probe}.py`.

## Shared infrastructure (post-purge state)

Originally this file documented contention rules around a shared
inference server. With the local-LLM stack retired, none of that
applies anymore:

- **No `tsunami.cli`** — the agent loop entry point was deleted.
  Agent harnesses (Claude Code or equivalent) run in their own
  process and call into tsunami's patterns directly.
- **No live-inference lock** — the `~/.tsunami/inference.lock`
  was for serializing live runs against the local Qwen3.6 server.
  No local server, no lock.
- **No shared :8090/:8092/:8095 endpoints** — all retired in
  the 2026-04-26 purge. See `../tsunami/CHANGELOG.md` v3+ entries.

## Adding a new scaffold

The META work is documented in `../tsunami/CLAUDE.md` ("Adding new
probes / styles / skills (META work)" section). For a new
scaffold + bespoke probe pair:

1. Create the scaffold dir under `scaffolds/<name>/`. Mirror the
   closest existing scaffold's structure (typically
   `__fixtures__/drone_natural.tsx` + `package.json` + `src/`).
2. Write `../tsunami/plan_scaffolds/<name>.md` with the build
   conventions for that scaffold target.
3. If vision-gate doesn't apply (API, browser extension, desktop
   binary), write a bespoke probe at `../tsunami/core/<name>_probe.py`
   and register in `../tsunami/core/dispatch.py`'s `_PROBES` dict.
4. Add a row to the choose-your-own-adventure table in
   `../tsunami/CLAUDE.md`.
5. Add the new scaffold to the catalog above.

## Shared-infra commits that already landed (historical reference)

Pre-existing structural work all scaffolds inherit:

- Wave/drone split with minimal `_ALWAYS_TOOLS` (4f463c0)
- Gamedev pipeline base (c50bb50)
- @engine FrameLoop / ScoreSystem prompt hints (a782331, afcae0b)
- ERNIE bucket-snap + sprite downscale + correct recipe (50046a2) —
  ERNIE itself retired 2026-04-26; structural lessons preserved
- Absolute save_path handling in generate.py (86b4db4, 1a7a259) —
  generate.py retired 2026-04-26; pattern lives in image-gen
  re-enablement target
- Drone-facing generate_image / assets toolbox (29f8d4d) — generate
  tool retired 2026-04-26
- file_edit full-file preview (c50bb50) — file_edit tool retired
  2026-04-26 (see `../tsunami/CLAUDE.md` legacy-API translation table:
  `file_edit` → Claude Code `Edit`)
- parameter_X / parameter / parameters JSON-key salvage (29f8d4d, 05b504f)
- framer-motion in react-app deps
