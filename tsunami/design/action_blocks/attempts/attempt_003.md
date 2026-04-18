# Action Blocks + Mechanics — v0 method (attempt 003)

> Loop-closing proof. One mechanic, `WaveSpawner`, traced stem to stern:
> prompt → emitted JSON → validator output → compiler-lowered TS →
> engine runtime → QA critique shape → JSON patch → re-run.
> If this trace is clean, the method is ready for implementation.

## Stage 0 — Prompt to Tsunami

```
make me a small arena shooter — one player, waves of enemies, health bar
```

The prompt is terse. Tsunami's current freehand-TS path would call
`project_init(name="arena-shooter")` and start writing App.tsx.
The new path routes through `emit_design`.

## Stage 1 — Tsunami emits a design script

Tsunami receives: (a) the schema TS types, (b) the mechanic catalog with
one-line descriptions, (c) 3 example design scripts for nearest-match
priming. It emits:

```json
{
  "meta": {
    "title": "Arena Shooter",
    "vibe": ["arcade", "fast-paced"],
    "target_session_sec": 180
  },
  "config": {
    "mode": "3d",
    "camera": "perspective",
    "gravity": [0, -20, 0],
    "arena": { "shape": "disk", "size": 25 }
  },
  "archetypes": {
    "player": {
      "mesh": "capsule",
      "controller": "topdown",
      "components": ["Health(100)", "Score"],
      "tags": ["player"]
    },
    "grunt": {
      "mesh": "box",
      "ai": "chase",
      "components": ["Health(20)"],
      "tags": ["enemy"]
    }
  },
  "mechanics": [
    { "id": "diff",  "type": "Difficulty",
      "params": { "drive": "wave_index",
                  "easy": { "spawnRateMul": 0.6, "enemyHealthMul": 0.8 },
                  "hard": { "spawnRateMul": 2.0, "enemyHealthMul": 1.5 },
                  "max_level": 10 } },
    { "id": "waves", "type": "WaveSpawner",
      "params": { "archetype": "grunt",
                  "difficulty_ref": "diff",
                  "base_count": 4, "rest_sec": 6,
                  "arena_radius": 20 } },
    { "id": "hud",   "type": "HUD",
      "params": { "fields": [
                    { "archetype": "player", "component": "Health" },
                    { "archetype": "player", "component": "Score" },
                    { "mechanic": "waves",  "field": "wave_index" } ] } },
    { "id": "lose",  "type": "LoseOnZero",
      "params": { "archetype": "player", "field": "Health",
                  "emit_condition": "player_dead" } }
  ],
  "flow": [
    { "scene": "title", "transition": "fade" },
    { "scene": "arena", "condition": "start_pressed" },
    { "scene": "gameover", "condition": "player_dead" }
  ]
}
```

Notes on what's in this shape:
- Every mechanic has an `id`; mechanics can reference each other
  (`difficulty_ref: "diff"`). No implicit singletons.
- `HUD` reads both archetype components and mechanic-published fields
  (`waves.wave_index`) — mechanics are allowed to expose read-only
  fields to other mechanics, documented in the catalog.
- `LoseOnZero` emits a `ConditionKey` consumed by the flow. That's the
  "dangling condition" detector's connection check.
- `archetypes` is a dict keyed by archetype id; mechanics refer to
  archetypes by key. No structural recursion, flat lookups.

## Stage 2 — Validator output

The compiler's first pass (`validate(script)`) runs five checks. For this
script they all pass, but here's what each would produce on a typo:

**(a) Unknown mechanic type** — swap `"WaveSpawner"` → `"WavSpawner"`:
```
SchemaError: unknown mechanic type 'WavSpawner' at mechanics[1].type
  did you mean: WaveSpawner
  catalog: https://[path]/design/catalog.ts
```

**(b) Unknown archetype reference** — `difficulty_ref: "doesnt_exist"`:
```
ReferenceError: mechanics[0].params.difficulty_ref references mechanic
  'doesnt_exist' which is not declared. Declared: diff, waves, hud, lose
```

**(c) Dangling flow condition** — remove the `LoseOnZero` mechanic but
keep the flow step:
```
DanglingConditionError: flow[2].condition 'player_dead' is never emitted.
  No mechanic with emit_condition='player_dead' found.
  Mechanics that could emit this: LoseOnZero, LoseOnCount, WinOnCount
```

**(d) Missing required tag** — remove the `grunt` archetype:
```
TagRequirementError: mechanics[1] (WaveSpawner) requires at least one
  archetype with tag 'enemy'. Archetypes tagged: player. Add a tag
  'enemy' to an archetype, or declare one.
```

**(e) Incompatible combo** — flip to `"mode": "2d"` with `"controller":
"fps"`:
```
CompatibilityError: archetype 'player' has controller='fps' which
  requires config.mode='3d'. Current mode: '2d'.
  Fix: change config.mode to '3d', or use controller='topdown'.
```

Every error is actionable (names the mechanic, names the allowed
alternatives, points at the catalog). These errors are the input to
Tsunami's error_fixer, which matches them against a small pattern table
and regenerates only the offending fragment — not the whole design.

## Stage 3 — Compiler lowering

The validated script is lowered into engine calls. The lowering for
`WaveSpawner` — the critical one — is:

```ts
// ark/scaffolds/engine/src/design/mechanics/wave_spawner.ts
import type { ValidatedDesign, WaveSpawnerParams } from '../schema'
import type { Game, SceneBuilder } from '../../game'
import { DifficultyManager } from '../../flow/difficulty'
import { Vec3 } from '../../math/vec'

export function lowerWaveSpawner(
  m: { id: string, params: WaveSpawnerParams },
  design: ValidatedDesign,
  game: Game,
  scene: SceneBuilder,
  ctx: LoweringContext,
): void {
  const archetype = design.archetypes[m.params.archetype]
  const diff = ctx.getMechanic<DifficultyManager>(m.params.difficulty_ref)

  // Mechanic-local state
  const state = {
    waveIndex: 0,
    alive: new Set<number>(),         // entity handles
    restingUntil: 0,
    elapsed: 0,
  }

  // Publish read-only field for other mechanics to consume (HUD)
  ctx.publishField(m.id, 'wave_index', () => state.waveIndex)

  scene.onUpdate(dt => {
    state.elapsed += dt

    // Advance difficulty on wave index
    diff.setLevel(Math.min(state.waveIndex / 10, 1))

    // Between waves
    if (state.alive.size === 0) {
      if (state.elapsed >= state.restingUntil) {
        state.waveIndex++
        const count = Math.floor(
          m.params.base_count * diff.get('spawnRateMul')
        )
        for (let i = 0; i < count; i++) {
          const pos = randomOnDisk(m.params.arena_radius)
          const handle = scene.spawnFromArchetype(m.params.archetype, {
            position: pos,
          })
          const health = ctx.getComponent(handle, 'Health')
          health.maxHealth *= diff.get('enemyHealthMul')
          health.health = health.maxHealth
          health.onDeath = () => state.alive.delete(handle)
          state.alive.add(handle)
        }
        state.restingUntil = state.elapsed + m.params.rest_sec
      }
    }
  })
}

function randomOnDisk(r: number): Vec3 {
  const a = Math.random() * Math.PI * 2
  const d = Math.sqrt(Math.random()) * r
  return [Math.cos(a) * d, 1, Math.sin(a) * d]
}
```

Four primitive calls land on the engine:
- `scene.onUpdate(dt => ...)` — existing `SceneBuilder.onUpdate`.
- `scene.spawnFromArchetype(name, overrides)` — **new thin wrapper**
  around `SceneBuilder.spawn()` that pulls mesh/controller/ai/tags/
  components from a validated archetype definition. This wrapper lives
  in the new `design/` directory, not in the engine's existing game/
  directory — keeps the existing fluent API untouched.
- `ctx.getComponent(handle, 'Health')` — the LoweringContext owns the
  component registry; it builds a `HealthSystem` from the
  `"Health(100)"` string spec when the archetype is first instantiated.
- `DifficultyManager` — existing class, instantiated once per
  `Difficulty` mechanic by its own lowering function
  (`lowerDifficulty`), and shared through `ctx.getMechanic()`.

The LoweringContext is the seam between mechanics — anything a mechanic
needs from another mechanic goes through it. That keeps mechanic files
independent and testable.

## Stage 4 — Engine runtime

The lowered game instantiates just like any hand-written game (via the
existing `Game.fromDefinition` + the new lowering layer injected between
validator and `GameDefinition`). Per-frame behavior:

- `game.frameLoop.onFixedUpdate` → `physics.step(dt)` — existing.
- `game.frameLoop.onUpdate` → `flow.update(dt)` + `input.update()` —
  existing. `flow.update` ticks the scene manager, which calls each
  scene's `update()`, which runs all `onUpdate` callbacks, which
  includes the `WaveSpawner` tick from Stage 3.
- When a grunt's `HealthSystem.onDeath` fires, `state.alive.delete(handle)`
  runs — eventually the set empties, the rest timer elapses, and the
  next wave spawns at a higher difficulty level.
- When the player's `HealthSystem.onDeath` fires, `LoseOnZero`'s
  lowering (`flow.setCondition('player_dead', true)`) triggers the flow
  to advance to `gameover`.

Zero new engine primitives required for this mechanic. The method is
additive — it changes what Tsunami authors, not what the engine runs.

## Stage 5 — Undertow build + QA critique

The built `deliverables/arena-shooter/dist/index.html` is handed to
undertow. For the Visual QA fun-detector (future work), the critique
shape is:

```json
{
  "verdict": "mid",
  "score_est": 0.42,
  "blocks_to_modify": [
    { "id": "waves",
      "issue": "wave_1_too_dense",
      "evidence": "player died at t=8s with 0 kills; 4 enemies spawned",
      "suggestion": { "base_count": 2 } },
    { "id": "diff",
      "issue": "ramp_too_steep_early",
      "evidence": "spawnRateMul jumped from 0.6 at w0 to 1.0 at w3",
      "suggestion": { "max_level": 15 } }
  ],
  "blocks_to_add": [
    { "type": "PickupLoop",
      "params_hint": { "archetype": "health_pack",
                       "reward_field": "Health",
                       "reward_amount": 25,
                       "respawn_sec": 12 },
      "reason": "no way to recover health; death is one-mistake" }
  ],
  "blocks_to_remove": [],
  "pacing_notes": "first 10s starts mid-wave — no ramp in. Consider
    WaveSpawner.intro_delay_sec."
}
```

Important: the critique is vocabularized in the same schema terms
Tsunami emits in. "blocks_to_modify[0].suggestion" is a JSON patch that
applies directly to `mechanics[i].params`. No NL-to-code translation
step.

## Stage 6 — Patch application

Tsunami reads the critique and applies three patches to the design:

1. `mechanics[1].params.base_count = 2` (was 4)
2. `mechanics[0].params.max_level = 15` (was 10)
3. Append new archetype `health_pack` + new mechanic `m_pickups`:
   ```json
   "archetypes": {
     ...,
     "health_pack": { "mesh": "sphere", "trigger": "pickup",
                      "tags": ["pickup"] }
   },
   "mechanics": [
     ...,
     { "id": "m_pickups", "type": "PickupLoop",
       "params": { "archetype": "health_pack",
                   "reward_field": "Health",
                   "reward_amount": 25,
                   "respawn_sec": 12 } }
   ]
   ```

The revised script re-runs through the validator (still valid), the
compiler (adds PickupLoop lowering + health_pack archetype), and the
build. QA re-runs and re-scores. The delta between scores is the fun-
signal over this patch step.

## Loop closure confirmed

Stages 0 → 6 form a closed loop that runs on the existing engine
without new runtime primitives, rejects malformed designs with
actionable errors, emits modification suggestions in the same
vocabulary Tsunami authors in, and applies patches as small JSON diffs
rather than TS rewrites.

The method is ready to implement.

## Implementation order (for whichever instance picks it up)

Three layers, each independently testable. Build in this order so each
stage has a working harness before the next:

1. **Schema + validator only.**
   - Land `ark/scaffolds/engine/src/design/schema.ts` (from attempt_002)
   - Land `validate.ts` — no lowering yet.
   - Land `catalog.ts` — the 15 mechanic metadata entries (name,
     description, required tags, exposed fields, compatibility matrix).
   - Tests: validate 5 known-good scripts pass; validate 5 adversarial
     malformed scripts each produce the expected error class.
   - This is the "skeleton of the method" — before any game runs.

2. **One mechanic end-to-end (`WaveSpawner` + `Difficulty` + `LoseOnZero`
   + `HUD`).**
   - Land `compiler.ts` + `mechanics/wave_spawner.ts` +
     `mechanics/difficulty.ts` + `mechanics/lose_on_zero.ts` +
     `mechanics/hud.ts`.
   - Tests: the Stage 1 script above compiles and runs in a vitest
     browser test, spawns enemies, fires the lose condition on player
     death.
   - Deliverable: a minimum-viable arena shooter built FROM a design
     script, end-to-end.

3. **Tsunami integration.**
   - Land `ark/tsunami/tools/emit_design.py` wrapping the compiler.
   - Replace `agent.py:2696-2716` prose with the schema-based context
     injection at `tsunami/context/design_script.md`.
   - Add error_fixer patterns for the 5 validator error classes.
   - Tests: given the Stage 0 prompt, the model emits a valid script ≥
     50% of the time on N=20 sample generations. (Baseline; no
     optimization yet — measure, don't tune.)

4. **Remaining 14 mechanics** — each is a `mechanics/<name>.ts` file
   + a catalog entry + ≥ 2 tests. Order by leverage: `PickupLoop`,
   `HUD`, `ScoreCombos`, `WinOnCount` first (small genre, big coverage);
   `TileRewriteMechanic`, `RhythmTrack`, `DayNightClock` last (novel
   subsystems, more engine surface to touch).

5. **QA critique shape** (schema on the Visual QA side). Out of scope
   for the current pair of instances; flagged for the QA instance when
   one exists.

## One uncomfortable detail

I keep finding that every new feature here is *recognizably* the same
object another engine has already shipped. `HUD` is a widget tree.
`WaveSpawner` is a script. `Difficulty` is a curve asset. Nothing here
is novel at the per-feature level.

The novelty is in the **authoring surface**: the catalog is LLM-
readable by construction, composition is JSON-first, errors round-trip
back to the author as structured suggestions. That's the design-level
bet. If the bet is wrong, the falsifier from attempt_002 catches it —
and we fall back to freehand TS, having learned that the schema was
overhead rather than scaffold.

Worth naming explicitly: the originality is in the LOOP, not the
blocks.
