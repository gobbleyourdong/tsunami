# GAP — engine

## Purpose
WebGPU game engine, 20.6K LOC TypeScript, 16 subsystems (renderer,
physics, animation, audio, UI, ECS, AI, input, systems). Consumed by
`game` scaffold via symlink `deliverables/<proj>/engine → engine`.

## Wire state
- Not directly invoked by drones — always referenced through the
  `game` scaffold. Symlink in `tsunami/tools/project_init.py::
  Copied scaffold 'game'` hook.
- Referenced by `@engine/*` tsconfig paths and vite aliases in the
  game scaffold's tsconfig.json.

## Numeric gap
- Internal type errors counted at last `tsc --noEmit` run: **6+**
  (chipsynth.ts 2×, attack_frames.ts 1×, schema.ts, validate.ts, etc.)
- Target: **0**.
- Delta: engine's own source compiles dirty; we sidestep by making the
  `game` scaffold build script `vite build` only (not `tsc --noEmit
  && vite build`). Engine errors don't block deliveries but they're
  real bugs.

## Structural blockers (known)
- `src/audio/chipsynth.ts` — strict-optional boolean passed to a
  param typed as `boolean`, and `.wave` access on a Record keyed by
  channel number.
- `src/design/mechanics/attack_frames.ts` — `SceneManager.activeScene`
  doesn't exist (method name drift).
- See `tsc --noEmit` in engine dir for full list.

## Churn lever
1. Run `cd scaffolds/engine && ./node_modules/.bin/tsc --noEmit`.
2. Fix one error per commit. Re-run. Repeat until clean.
3. Once clean, flip `game`/package.json build back to `tsc --noEmit &&
   vite build` — restores strict compile gate for game deliveries.

## Out of scope
- New subsystems (16 is enough).
- Refactoring the design-script compiler.

## Test suite (inference-free — engine is pure TS/WebGPU, no LLM)
`cd scaffolds/engine && npm install && npm test` runs vitest on all
`tests/*.test.ts` — no network, no inference. Parallel-safe.

## Success signal
`tsc --noEmit` exits 0. `game` scaffold can re-enable strict tsc in
its build script. Next game delivery inherits type-level correctness.

## Symlink → file: dependency (side quest)
Current linkage: `tools/project_init.py` symlinks
`deliverables/engine → scaffolds/engine/` after copying `game/`.
Problems: `rm -rf` hangs on symlinked `node_modules`, breaks on
Windows, breaks inside sandboxed containers.
Cleaner: `game/package.json` declares
`"@tsunami/engine": "file:../engine"`. project_init skips the
symlink, runs one extra `npm install` (~5s). Deliverable becomes
self-contained and tarballable. File if you pick up this task —
ripgrep `engine_link.symlink_to` to find the site.
