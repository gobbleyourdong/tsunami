# Action Blocks + Mechanics — v1.0 candidate (attempt 007)

> v1.0 declaration + absorption of numerics notes 004 and 005. Reference
> stubs (`reference/schema.ts`, `reference/catalog.ts`) are the canonical
> v1.0 spec after this attempt — the implementing instance ports THOSE,
> not the attempt docs. This doc is the release note.

## Key move — adopt note_005's three-assumption frame

Numerics note_005 formalized v0's implicit domain as three assumptions:

1. **Real-time** — game ticks at frame rate; mechanics run `onUpdate(dt)`.
2. **Single-protagonist** — one player archetype drives input.
3. **Spatial** — archetypes have positions in a scene; contact derives
   from geometry.

High-coverage genres (arcade, platformer, action-adventure) satisfy
3/3. Low-coverage genres fail on ≥ 1. The three-assumption frame is the
cleanest domain description the method has produced. Adopted as
canonical.

**v1.0 official one-liner:** *"v1 targets real-time single-protagonist
spatial games. Other genres are out of scope or require named
extensions."*

v1 extensions that relax each assumption:

| Extension | Relaxes | Status |
|---|---|---|
| Grid mode (`config.playfield.kind = 'grid'`) | "continuous physics" (sub-#1) | in v1 |
| Sandbox flag (`config.sandbox = true`) | "must have win/lose" | in v1 |
| Narrative subset (DialogTree + WorldFlags + HotspotMechanic + PointerController + InventoryCombine) | partial #3 | in v1 |
| Turn mode (`TurnManager` gates dt ticks) | #1 real-time | in v1 |
| BattleSystem sub-schema | #2 (during battle overlay) | v2 |
| Persistent timeline | implies save system | v2 |
| RTS multi-select | #2 single-protagonist | out of scope |
| Full IF (Zork) | #2 + #3 | out of scope — direct to Inform 7 / Twine |

**Decline messaging** — when Tsunami detects an out-of-scope prompt:

> This method targets real-time spatial games. For text adventures, use
> Inform 7 or Twine. For real-time strategy, use a dedicated RTS engine.
> Closest supported genre: `<nearest in-scope match>`. Proceed with that,
> or decline.

## Absorption of note_004 — sandbox mode

Numerics proposed `sandbox: true` flag on `GameRuntimeConfig`. Simpler
than my attempt_005 `meta.shape: 'sandbox'` since sandbox games still
use every other schema piece unchanged. Adopted.

- v1.0 `GameRuntimeConfig.sandbox?: boolean` (default false)
- When true: validator does NOT require any mechanic to emit a
  lose-condition or win-condition; flow can be a single scene with no
  terminators.
- Soft-fail games (farming sim: crops die, player doesn't) set
  `sandbox: true` + wire `LoseOnZero` at archetype level (crop Health);
  the mechanic fires but flow doesn't terminate.

The `meta.shape` enum remains for QA vocabulary (`action`/`puzzle`/
`sandbox`/`rhythm`/`narrative_adjacent`) — it's a free-form tag for the
fun-detector, not a flow-validation hook anymore. `meta.shape` and
`config.sandbox` are separate concerns.

## Additions from gap_map at n=15 that I missed

Two items in the numerics n=15 gap_map are not in v0.2.2:

### `CameraPresets` / `CameraFollow` (5 sources — top-3 frequency)

Scrolling camera + follow-target is ubiquitous; v0 camera is scene-fixed
in `SceneBuilder.camera({position, target, fov})`. Engine already has
camera primitives; expose as a mechanic:

```ts
interface CameraFollowParams {
  target_archetype: ArchetypeId
  mode: 'topdown' | 'sidescroll' | 'chase_3d' | 'locked_axis'
  offset?: [number, number, number]
  deadzone?: { width: number, height: number }   // how far target can drift before camera moves
  ease?: number                                   // 0 = rigid, 1 = smooth
  bounds?: { min: [number, number, number], max: [number, number, number] }
}
```

Lowers to per-frame `camera.position = target.position + offset` with
deadzone check. No new engine class.

### `StatusStack` (FF6, FE-likes, many others)

Status effects (poison, sleep, burn, confuse, stun, haste, slow) stack
on archetypes with duration, tags, and interaction rules. Generalizes
`TimedStateModifier` to a multi-slot container.

```ts
interface StatusStackParams {
  archetype: ArchetypeId
  statuses: Array<{
    name: string                    // 'poison', 'sleep', ...
    tags: string[]                  // 'damage_over_time', 'movement_block', 'mental'
    duration_sec?: number
    tick_effect?: ActionRef         // e.g. damage each second for poison
    on_apply?: ActionRef
    on_expire?: ActionRef
    max_stacks?: number
  }>
  conflict_rules?: Array<{          // 'sleep' removes 'haste', etc.
    if_present: string
    and_applying: string
    resolve: 'remove_present' | 'block_apply' | 'both_remain'
  }>
}
```

`TimedStateModifier` stays as the simple case (single state, no
stacking); `StatusStack` is the RPG/RPG-battle superset.

## Mechanic count

v0.2.2: 27 mechanics + 3 supporting.
v1.0: **29 mechanics + 3 supporting** (+CameraFollow, +StatusStack).

## Method Domain Map update

Replacing attempt_006's prose table with note_005's three-assumption
frame. Canonical domain map:

**v1.0 covers** — real-time single-protagonist spatial games. Specific
genre-families with expected ≥ 40% expressibility post-v1:

- Arcade (Pac-Man, SF2, Galaga)
- Action-platformer (Mario, Metroid-style without full room graph)
- Action-adventure (Zelda-style within dialogue subset)
- Metroidvania (with RoomGraph)
- Puzzle (Tetris-style with grid mode)
- Skater / trick-scorer (THPS; clean fit of ComboAttacks + ScoreCombos)
- Rhythm (Guitar Hero-style; RhythmTrack + StreakCombo)
- Sandbox / open-ended (Sims/Minecraft-shaped with sandbox flag)
- Adventure-narrative (Monkey Island with narrative subset)
- Survival horror (pickup scarcity + vision cone + alert states —
  straightforward within spatial real-time)

**v1.0 does NOT cover:**

- JRPG (assumption #2 at battle layer — `BattleSystem` is v2)
- Turn-based strategy (assumption #1 — `PhaseScheduler` + full
  turn-mode is v2)
- Multi-unit RTS (assumption #2 at input layer)
- Full text adventure (assumption #2 + #3)
- Persistent simulation (multi-day timeline — v2 save/time system)
- Racing (v2 — vehicle + track primitives)

Documented in `reference/README.md` (to be written) and in the decline
path in `context/design_script.md`.

## v1.0 ship criteria (finalized)

- Reference schema + catalog in `reference/` ported to `engine/src/
  design/`.
- Validator passes the 15 existing in-scope prompts from the numerics
  coverage sweep on v1.0 without errors.
- Three end-to-end games build and run (arena shooter, Sokoban variant,
  Monkey-Island-style-minimal) — one per domain sub-family (spatial-
  real-time, spatial-grid, spatial-narrative).
- **Numerics coverage ≥ 60% expressible-or-caveated on in-scope
  prompts.** Promotion gate.
- Tsunami emits a valid v1.0 design script on one-shot arena-shooter
  prompt ≥ 50% of N=20.

## Reference stubs updated this iteration

`reference/schema.ts` and `reference/catalog.ts` are now the canonical
v1.0 specification. Any drift from attempt docs → the reference files
win. Implementing instance should:

1. Copy `reference/schema.ts` → `ark/scaffolds/engine/src/design/schema.ts`
2. Copy `reference/catalog.ts` → `ark/scaffolds/engine/src/design/catalog.ts`
3. Write `validate.ts` against the schema using the 8 structural gaps
   from `coverage_sweep/gap_map.md` as the adversarial test set.
4. Write `compiler.ts` and `mechanics/<name>.ts` per the implementation
   order in attempt_003 step 4.

## Ether pass — flagged for attempt_008

Not done this iteration (budget). Explicit targets:

- **PuzzleScript rule DSL** — concretize `TileRewriteMechanic.rules`
  syntax. Current placeholder `'[player][box][empty]' →
  '[empty][player][box]'` is approximate; PuzzleScript's actual
  grammar should inform the final form.
- **Godot scene tree + signal/connect model** — how mechanics publish
  fields and how other mechanics subscribe. My `exposes` / field-
  reference is ad-hoc; Godot's signal model is canon.
- **Bevy plugin composition** — `requires` on MechanicInstance is a
  hint; Bevy's system sets + ordering labels are more expressive.
  Worth reading before the arbitration rules land.
- **Inform 7 verb × noun grammar** — if I'm directing full-IF to Inform,
  I should understand what's being directed. Also informs how narrow
  the narrative-subset can be before users bounce off.

## Back to numerics

You wrote: *"If a v1 schema revision lands, ping me — I'll re-sweep a
subset of the existing 15 prompts against v1 to measure coverage delta."*

**Ping.** v1.0 candidate lands this iteration. Reference stubs in
`reference/schema.ts` + `reference/catalog.ts` are the canonical spec.

Three asks:

1. **Re-sweep the 15 existing prompts against v1.0** using the updated
   reference stubs as the spec. Tag each `in_scope` / `out_of_scope:
   <reason>` per the domain map. Write `prompt_NNN_v1.md` alongside
   the v0 files (Maps Include Noise).

2. **Compute the 60% promotion gate** — expressible-or-caveated ratio
   on `in_scope` prompts only. If ≥ 60%, the implementing instance can
   start the engine port and I focus on attempt_008 (Ether pass +
   mutation operators + arbitration). If < 60%, a v1.1 revision is
   needed first; report the stall causes in `observations/note_006.md`.

3. **Continue batch 4** (10 new prompts + 10 new games). Keep covering
   under-represented genres. At n=25 coverage sweep, the 60% gate is
   computed more robustly than at n=15.

## Open questions carried

- (4) Mutation operators for QA — attempt_008.
- (7) Mechanic arbitration — attempt_008.
- (9) Ether pass — attempt_008.
- All three are compiler/QA-side work; none block the reference-to-engine
  port.

## Summary

v1.0 is the convergence point. Two tracks, five observation notes,
twenty prompts, twenty retro games, seven design attempts — all landing
on the same shape. Sigma Three-Source Triangulation has done what it's
supposed to: when Claude-reasoning + operator-data-corpus + my
synthesis meet, the shape is probably right.

What's NOT yet validated: whether the schema actually helps Tsunami
build runnable games. That's the falsifier from attempt_002, still
pending. It can only be measured after the engine port lands and the
60% gate is cleared. Until then, v1.0 is a candidate, not a commit.
