# Engine handoff 001 — response to audit 001

**Date:** 2026-04-18
**Role:** responding instance
**Scope:** fix what's fixable from `engine_audit_001.md`; hand off the
rest with enough detail that the implementation instance can land
without rediscovery.

## Fixed directly (verified against source before patching)

| Audit # | Fix | File(s) |
|---|---|---|
| 1 | `EmitDesignTool` added to `build_registry`; import wired. Registry now 14 tools. | `ark/tsunami/tools/__init__.py` |
| 3 | `sprite_ref: arch?.sprite_ref` added to `archetypeToEntity`'s `properties` literal. Compiler now forwards sprite_ref. | `ark/scaffolds/engine/src/design/compiler.ts:265-273` |
| 7 | `src/ui/README.md` rewritten — matches current `index.ts` reality (full scaffold landed; text shipped; flex/input/icon atlas deferred). Table lists all 14 files + status. | `ark/scaffolds/engine/src/ui/README.md` |
| 8 | Main README TL;DR + subsystem table — LOC updated 16,642 → 20,586; added `ui` row (14 files, 3,942 LOC). | `ark/scaffolds/engine/README.md` |

**Verification notes.** Each patch was preceded by a direct file read
to confirm the audit's line citation. Audit 1's "one-line fix" claim
was accurate for items 1 and 3. Audit 2's "structurally unwired per
grep" claim for items 2 and 9 was not verified at runtime (Phase 4a
discipline stands — no content audit done here either).

## Handed off (need implementation-instance attention)

### 🔴 A. Wire `mechanicRegistry.create` into Game runtime (audit item 2)

**The dormant-registry problem.** 35 registered mechanic factories,
zero production call sites that instantiate them. Compiler emits
`scene.properties.mechanics: MechanicInstance[]`; nothing walks that
array.

**Suggested entry point.** Extend `Game.fromDefinition` at
`src/game/game.ts:153-160`, OR add a new `Game.activateScene(name)`
that:

1. Looks up `SceneDefinition` + `EntityDefinition[]` for the named scene.
2. Iterates `scene.properties.mechanics as MechanicInstance[]` (cast;
   `SceneDefinition` doesn't type `properties` — use `any` or declare
   it on the type).
3. For each `MechanicInstance`, calls
   `mechanicRegistry.create(instance, this)` to get a `MechanicRuntime`.
4. Hangs the array of runtimes off the scene (e.g. a `WeakMap<GameScene,
   MechanicRuntime[]>` maintained by Game, or add a field to
   `GameScene`).
5. On frame tick (`frameLoop.onUpdate`), iterate the live scene's
   runtimes and call their per-frame hooks.
6. On scene switch, call each runtime's teardown hook and clear.

**Reference shape.** The one existing production-ish call site —
`src/design/mechanics/embedded_minigame.ts:78` — shows the registry
API. That's the pattern to replicate in Game.

**Acceptance.** A design script with a ChipMusic mechanic, when
compiled + `Game.fromDefinition`'d + activated, should actually play
audio on frame ticks (the runtime's hook runs). Existing
`tests/audio_mechanics.test.ts` covers the registry-to-runtime path
at unit level; the new test asserts runtime ticks via frame loop.

**Scope.** ~60–120 LOC across `src/game/game.ts` +
`src/scene/scene_manager.ts` (probably) + a new
`tests/game_activation.test.ts`.

### 🔴 B. Replace `scaffolds/game/src/main.ts` (audit item 4)

**Current state.** Scaffold auto-mounts React `App.tsx`, never looks
for `game_definition.json`. Deliverables from Tsunami's
`EmitDesignTool` have no consumer.

**Target.** Rewrite `scaffolds/game/src/main.ts` to:

1. Initialize WebGPU (`initGPU(canvas)` from `@engine`).
2. `fetch('/game_definition.json')` — the file Tsunami deposits via
   `emit_design`. Produce an actionable error if 404 (parallels the
   text_demo's "atlas missing" error UI).
3. `Game.fromDefinition(def)` → `game.activateScene(def.flow[0].scene)`
   (once item A lands).
4. `game.start()`.
5. Keep a minimal error overlay for WebGPU init failures (same shape
   as `demos/phase1.html`).

Drop React. The scaffold is engine-only for v1. Web scaffolds stay
React; game scaffold doesn't need it.

**Acceptance.** Vite dev server → visit `/` → scaffold loads
`game_definition.json` from `public/` → game runs.

**Scope.** ~100 LOC. Likely touches `main.ts`, `index.html` to drop
React mount point, maybe delete `App.tsx`.

### 🟠 C. Build plumbing: `prebuild` hook + default `public/` (audit items 5, 6)

**Problem.** `publicDir: '../public'` is declared but the dir doesn't
exist. Demos fetch `/fonts/*`, `/sprites/manifest.json` → 404.
`font_bake.py` and `build_sprites.py` are manual CLIs with no
package.json hook.

**Proposed structure.**

```
scaffolds/engine/
├── scripts/
│   └── prebuild.mjs     NEW
├── public/              NEW (or one-time created by prebuild)
│   ├── fonts/           (populated by font_bake.py)
│   └── sprites/         (populated by build_sprites.py)
├── package.json         ADD: "prebuild": "node scripts/prebuild.mjs"
└── vite.config.ts       ALREADY REFS '../public'
```

`prebuild.mjs` does:

1. `mkdir -p public/fonts public/sprites` if missing.
2. If `assets.manifest.json` exists in the scaffold, spawn
   `python tools/build_sprites.py …`.
3. If `public/fonts/regular.atlas.bin` is missing AND a
   `DEFAULT_FONT_TTF` env or sibling path is set, spawn
   `python tools/font_bake.py $DEFAULT_FONT_TTF --out public/fonts/regular`.
4. Log warnings (non-fatal) if Python deps aren't installed, with
   the right `pip install fonttools numpy pillow` hint.

**Acceptance.** `npm run build` on a fresh checkout with a TTF env
var works end-to-end. Demos stop 404'ing.

**Scope.** ~80 LOC JS + `package.json` script additions + README
update documenting the env var.

### 🟠 D. Declare `sprite_manifest` on `DesignScript` type (audit
   README-stated blocker #4)

**Current hack.** `validate.ts:134-140` does `(raw as unknown as
{sprite_manifest?: …})` casting gymnastics because the type doesn't
declare the field.

**Fix.** Add to `src/design/schema.ts`'s `DesignScript` interface:

```ts
export interface DesignScript {
  // … existing fields …
  sprite_manifest?: string   // path relative to deliverable root
}
```

Remove the cast in `validate.ts`. Check any other cast sites for the
field (grep `sprite_manifest`).

**Scope.** ~5 LOC.

### 🟡 E. Ship gate #13 label honesty (audit item 9)

**Current.** `tests/design_e2e.test.ts` asserts compile-output shape;
label calls it "e2e." That's validator + compiler testing, not
end-to-end.

**Two paths:**

1. **Rename.** Change label to "design-roundtrip" or "compile-shape."
   Update `scaffolds/engine/README.md` ship-gates row to reflect.
2. **Upgrade.** Extend `design_e2e.test.ts` to actually run `Game.
   fromDefinition` + activate + tick N frames + assert mechanic
   side-effects (e.g. spawn count after N WaveSpawner ticks). This
   gates on item A landing first.

**Recommendation.** Rename now (30s fix); upgrade in a follow-up PR
once item A lands. The audit's criticism is that the label overpromises;
renaming ends that. The upgrade is strictly better but needs item A.

**Scope.** Rename only — 2 LOC across the test file + README.

## Priority order (copy from audit, with fixed items struck)

1. ~~Register `EmitDesignTool`.~~ ✓ done.
2. **A** — Wire mechanicRegistry into Game. *(highest leverage remaining)*
3. ~~Forward `sprite_ref` in compiler.~~ ✓ done.
4. **B** — Rewrite `scaffolds/game/src/main.ts`. *(closes agent→game
   loop; gates on A)*
5. **C** — Vite prebuild plugin + default `public/`.
6. **D** — `sprite_manifest` on `DesignScript` type.
7. **E** — Ship gate #13 rename.

Items A + B are the load-bearing integration work. C unblocks demos.
D is trivially mechanical. E is label correctness.

## Non-blockers for this handoff

The items below were NOT flagged by the audit but worth knowing:

- **UI framework scaffold** is landed but not wired to design
  mechanics yet. Seven of the 35 mechanics (HUD, Menu, DialogTree,
  Tutorial, Shop, InventoryPanel, hotspot-menu) produce
  ComponentDef subtrees that `webgpu_compiler.ts` can render — but
  nothing currently calls the compiler inside the Game's frame loop.
  This is the **next integration edge after items A + B land**. The
  mechanic runtime hook would call
  `compileToWebGPU(mechanic.renderUI(), ctx)` inside the frame's
  overlay pass.

- **Text renderer hardware validation** still pending (winding sign,
  Newton cusp convergence, AA tuning). Separate from this handoff;
  tracked in `src/ui/text.ts` status header.

## Audit-compliance self-check

**Sigma v9.1 Three-Source Triangulation.** The audit's findings were
triangulated across README + source + grep. My fixes triangulated the
same way: (a) read the audit's claimed file + line, (b) read the
source, (c) confirmed the disconnect before patching. Items 1 and 3
specifically verified by reading the `__init__.py` build_registry
body and the `archetypeToEntity` literal respectively.

**Would falsify this handoff.** If items 2 and 9 (the runtime-inert
pieces) actually do tick at runtime — via some wiring the grep missed
— then items A and E reduce to no-ops. A 4b content audit (run a
baked game + observe) would resolve that. Audit notes this as
"recommended next pass." Concur.
