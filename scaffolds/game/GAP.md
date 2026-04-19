# GAP — game (+ engine)

## Purpose
WebGPU game scaffold. Engine-only (no React). Drone writes a single
`src/main.ts` using `@engine/*` primitives (KeyboardInput, FrameLoop,
ScoreSystem). For declarative games, drone calls `emit_design` and
the engine loads `public/game_definition.json`.

## Wire state
- Plan scaffold: `tsunami/plan_scaffolds/gamedev.md`
- Routing: `planfile.py::_DOMAIN_SIGNALS` on `frogger / snake / pong /
  asteroids / platformer / shooter / rhythm game / tower defense /
  playable game / arcade game / video game`.
- Proven: frogger v23 (2 iters), space invaders combo (3 iters),
  chiptune demo (2 iters).

## Numeric gap
- Runtime-correctness iter-1 rate: **~30%** (drone logic bugs, null
  derefs in their own update/render fns).
- Target: **70%**.
- Delta: drone emits code that compiles but crashes at render time
  because of one bad reference (`score.value` vs `.score`, FrameLoop
  ctor arg, undefined entity lookup).

## Structural blockers (known)
- a782331 / afcae0b / 50046a2 closed API-signature hallucinations
  (FrameLoop.onUpdate, ScoreSystem.score, ERNIE dim buckets, sprite
  downscale).
- Remaining: drone's own game logic — spawning, collision, respawn
  reset. These are the drone's code, not the engine's.

## Churn lever
1. Spin up a handful of small games (pong, snake, breakout, dodger).
2. When runtime-error surfaces, trace it to either (a) an
   `@engine/*` API the drone misremembered — add an exact-signature
   hint to `tsunami/prompt.py` gamedev branch, or (b) drone logic
   — log the pattern but do NOT patch the prompt further.
3. Target: 4 of 5 next games ship runtime-clean.

## Out of scope
- Writing drone game logic for them (pattern: keep the gap).
- React/DOM-based games (use `react-app` for those).
- Multi-file games (one main.ts is the scope — forces tight scope).

## Test suite (inference-free)
Fixtures at `scaffolds/game/__fixtures__/<name>/main.ts` —
hand-written mini-games that use every `@engine/*` primitive.
`cd scaffolds/game && npm install && npm run build` validates the
engine surface didn't regress. vitest `tests/engine_integration.test.ts`
should boot each fixture, tick FrameLoop for 60 frames, assert canvas
pixels changed. Parallel instances safe — no inference.

Parallelism: N instances on fixture churn, serialize live-inference
runs via `~/.tsunami/inference.lock`.

## Success signal
4/5 novel game specs ship canvas-rendering + vision-PASS in ≤4
iterations, zero pageerror events on load.
