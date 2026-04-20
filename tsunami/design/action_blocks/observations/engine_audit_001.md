# Engine audit 001 — end-to-end integration gaps

**Date:** 2026-04-18
**Auditor role:** game-dev auditor (external pass)
**Scope:** `ark/scaffolds/engine/` + connections into `ark/tsunami/agent.py` +
README-stated open problems.
**Method:** Sigma v9.1 Phase 4a (structural audit — grep + Read +
cross-reference scanning; no content-audit / WebSearch phase).

The "v1.0 ships / 4 ship gates green" framing in `scaffolds/engine/README.md`
holds for the **validator + compiler + unit-tested mechanics**. The
end-to-end "AI authors a playable game" pipeline drawn in README §4 does
**not** hold. Three load-bearing edges are missing between compile output
and runtime.

---

## 🔴 Critical integration breaks

### 1. `EmitDesignTool` is defined but never registered

- `tsunami/tools/emit_design.py:193` — class exists.
- `tsunami/tools/__init__.py:100-124` — `build_registry()` registers 13
  tools; `EmitDesignTool` not among them.
- `tsunami/agent.py:3122` injects a system-note telling the model to
  "use `emit_design(name, design)`" — the model has no tool-call handle
  for it.

**Consequence.** The model cannot invoke the compiler. Ship gate #14
works only because `tests/measure_ship_gate_14.py:35` imports
`emit_design` as a Python function and bypasses the agent loop. The
gate measures "Qwen emits valid JSON," not "the agent ships a game."

**Fix (one line).** Add `from .emit_design import EmitDesignTool` and
register it in `build_registry` alongside the other 13 tools.

### 2. `Game.fromDefinition` does not instantiate mechanics

- `src/game/game.ts:153-160` — only calls `SceneBuilder.deserialize(sceneDef)`.
- `mechanicRegistry.create(…)` call sites in the repo:
  - `tests/audio_mechanics.test.ts` (unit tests)
  - `src/design/mechanics/embedded_minigame.ts:78` (one internal case)
  - **Zero call sites in `src/scene`, `src/game`, or `src/systems`.**

The compiler produces scenes with `properties.mechanics: MechanicInstance[]`
per README §1 ("wires mechanic instances into scene property bags"), but
no production code walks that array and instantiates the registered
factories.

**Consequence.** The 35-mechanic registry is dormant in production.
README §4 arrow 3 ("mechanicRegistry.create per mechanic") and §1 claim
("scene activation walks the list and constructs a MechanicRuntime")
both describe code that does not exist.

**Fix.** Add a `Game.activateScene(name)` (or extend `fromDefinition`)
that iterates `scene.properties.mechanics` and calls
`mechanicRegistry.create(instance, this)` for each; hang the returned
runtimes on the scene so the frame loop ticks them.

### 3. Compiler strips `sprite_ref`

- `src/design/compiler.ts:252-274` (`archetypeToEntity`) forwards
  `mesh / controller / ai / trigger / components / tags` to
  `entity.properties` — silently drops `sprite_ref`.
- Schema declares `sprite_ref` at `src/design/schema.ts:97`; validator
  checks it at `src/design/validate.ts:159-167`; loader resolves it at
  `src/sprites/loader.ts:72`. **Everything except the compiler is ready.**

**Consequence.** README-stated blocker #1 ("renderer doesn't consume
sprite_ref") is worse than stated. Even if the renderer learned to
read `entity.properties.sprite_ref`, nothing puts it there.

**Fix (one line).** Add `sprite_ref: arch?.sprite_ref` to the
`properties` literal in `archetypeToEntity`.

### 4. Game scaffold defaults to React, not engine

- `scaffolds/game/src/main.ts:19-35` auto-mounts `App.tsx` via React;
  the "engine mode" branch (`catch`) never runs because the scaffold
  ships with a placeholder `App.tsx` ("Loading...").
- No `game_definition.json` fetch anywhere in `scaffolds/game/`.

**Consequence.** When Tsunami writes
`deliverables/<name>/game_definition.json`, nothing in the scaffold
consumes it. The agent would have to manually write engine-native
TS code — the exact workflow the design-script was designed to eliminate.

**Fix.** Replace `main.ts` with a loader that fetches
`game_definition.json`, calls `Game.fromDefinition`, activates the
first flow step's scene, and starts the frame loop. Drop React
dual-mode (design-script is the only v1 path).

---

## 🟠 Missing build plumbing

### 5. No `public/` directory; no build hooks

- `vite.config.ts:5` declares `publicDir: '../public'` — directory
  does not exist.
- `demos/text_demo.html` fetches `/fonts/regular.atlas.{bin,json}` → 404.
- `src/sprites/loader.ts:40` fetches `/sprites/manifest.json` → 404.
- Demos that land in the source tree **cannot run** without manual
  `font_bake.py` invocation + manual `public/` creation.

### 6. No `npm run build:sprites` / `build:fonts`

- `package.json` scripts: `test / dev / build / test:watch`.
- `tools/build_sprites.py` and `tools/font_bake.py` are manual CLIs.
- README §Gaps #2 calls this out — still unfixed.

**Fix.** `scripts/prebuild.mjs` or tiny Vite plugin that runs
`build_sprites.py` when `assets.manifest.json` exists, and invokes
`font_bake.py` against a default TTF when `public/fonts/` is absent.

---

## 🟡 Documentation drift

### 7. `src/ui/README.md` is stale

- Says `webgpu_compiler.ts` is **TODO**.
- `src/ui/webgpu_compiler.ts` exists at 513 LOC and is exported via
  `src/ui/index.ts:27-32`.
- `src/ui/index.ts` correctly marks it `✓ scaffold`.
- The two README files disagree.

### 8. Main README undercounts the engine

- TL;DR says "16,642 LOC across 16 subsystems."
- Actual: **19,251 TS LOC across 17 source dirs.**
- `src/ui` (~2,600 LOC, 9 files) is missing from §1's subsystem table
  entirely — the whole UI framework + Hermite text pipeline landed
  after the README snapshot.

### 9. Ship gate #13 "e2e" label is inflated

`tests/design_e2e.test.ts` only asserts JSON shape after
validate+compile. It never starts a Game, never ticks a frame, never
runs a mechanic. The label promises behavior the test doesn't
exercise. Combined with finding #2, this explains how
"v1.0 ships / 4/4 gates green" can be true while the runtime path is
inert — the gates don't cover the inert stretch.

---

## 🟡 README-stated blockers (confirmed real)

All four from `scaffolds/engine/README.md` §Gaps → Blocking:

| # | README claim | Verdict |
|---|---|---|
| 1 | `sprite_ref` not consumed by renderer | Real; **also** stripped by compiler (finding 3) |
| 2 | Scaffold-level build wiring missing | Real |
| 3 | No bundled sprites example | Real; `examples/` has no `sprites_demo.json` |
| 4 | `sprite_manifest` field not declared on `DesignScript` | Real; `validate.ts:134-140` does `(raw as unknown as {sprite_manifest?:…})` gymnastics |

---

## Priority order for fixing

1. Register `EmitDesignTool` in `build_registry`. *(one line; unblocks
   real agent-driven emission)*
2. Wire `mechanicRegistry.create` into `Game.fromDefinition` (or a
   new `Game.activateScene`). *(the dormant-registry fix)*
3. Forward `sprite_ref` in `compiler.ts:archetypeToEntity`. *(one
   line; makes sprite pipeline actually-visible-in-game)*
4. Rewrite `scaffolds/game/src/main.ts` to fetch
   `game_definition.json` + load-and-start. *(closes the deliverable
   → running game loop)*
5. Vite plugin for `build_sprites.py` + `font_bake.py`; create default
   `public/` layout. *(makes demos runnable out-of-the-box)*
6. Declare `sprite_manifest` on `DesignScript` type; sync
   `src/ui/README.md` to match `src/ui/index.ts`.

Items 1–3 are each one-line-to-small patches. Together with #4 they
convert the "green ship gates" claim into an actually-runnable
pipeline end-to-end.

---

## Method notes

**Sigma compliance.** This is a Phase 4a structural audit — no content
verification (no WebSearch, no live runtime testing). Findings 1–3
were triangulated across three sources: the README's architectural
claim, the source file at the claimed responsibility, and grep for
call sites. All three flagged the same disconnects; the convergence
is the signal (v9 Three-Source Triangulation).

**Would falsify.** A single production call site of
`mechanicRegistry.create` inside `src/scene/` or `src/game/`, or a
single `sprite_ref` reference in `src/renderer/`, would kill findings
2 and 3 respectively. Grepped and absent at time of audit.

**Not audited.** 4b content audit (actually compiling + running a
deliverable in a browser to confirm mechanics don't tick) — would
upgrade 🔴 findings from "structurally unwired per grep" to
"confirmed dead at runtime." Recommended next pass.
