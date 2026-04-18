# Action Blocks + Mechanics — v0 method (attempt 002)

> Iteration on attempt_001. Audit first, then corrections, then concretize:
> 15 Mechanics with domain coverage, schema skeleton, falsifier stated.

## Confirmation-bias audit of attempt_001

Per Sigma v7 principle. Three questions:

**1. Rejection count — alternatives I didn't consider.**
The 3-layer L1/L2/L3 model was the first structure I reached for; I didn't
enumerate alternatives. Named here as map-features (not dead ends, per Maps
Include Noise):

- **A1 — Pure ECS, no layers.** Entities + components + systems only;
  "Mechanic" becomes "system bundle." Flatter, fewer abstractions. *Cost:*
  LLM has to reason about systems separately from archetypes; archetype→
  system wiring is implicit and harder to validate.
- **A2 — Pure event graph (Unreal Blueprint shape).** Blocks = event handlers
  + actions; composition = wiring ports. *Cost:* statement-level granularity,
  the model has to write many small blocks per mechanic. Too low-level for
  the "prompt is a design script" target.
- **A3 — Push-down automaton, states as first-class.** Every game is a state
  machine; mechanics are state/transition specs. *Cost:* clean for
  platformer/fighting, awkward for arcade/sim where state is diffuse.
- **A4 — Pure rule-rewrite (PuzzleScript shape).** All gameplay is tile
  rewrite rules. *Cost:* works for 2D tile puzzles, breaks on real-time 3D.

**Verdict on the layered design:** the 3-layer model is a reasonable DEFAULT
but not a universal. The schema should leave room for A3 (state-machine
mechanics) and A4 (rule-rewrite mechanics for tile-puzzle sub-games) as
*mechanic types*, not as competing global architectures. Added to v0 as:
`StateMachineMechanic` and `TileRewriteMechanic` entries in the catalog.

**2. Construction check — did I build the example to fit the design?**
Yes. "Neon Drift" showcases WaveSpawner + PickupLoop + ScoreCombos + HUD +
LoseOnZero — exactly the mechanics I'd already half-specified. The example
confirms the design by construction, not by stress-test. A real stress-test
is: write design scripts for three *adversarial* prompts —

- "a puzzle game where you rotate rooms to reach the exit"
- "a rhythm game where you block beats"
- "a farming sim with crops and time of day"

If v0 can't express those cleanly, the mechanic catalog is arcade-biased.

**3. Predictive test — does the model predict new behavior?**
For arcade-shaped games, yes. For puzzle/rhythm/sim, uncertain. Predictive
reach is proportional to the coverage of the Mechanic catalog; v0 with only
arcade mechanics predicts only arcade games.

**Classification:** attempt_001 is a **candidate pattern** — survived one
audit, not cross-validated across genres. Promotable if the schema can
express the three adversarial prompts without shape additions. Otherwise,
refactor.

## Corrections to attempt_001

Caught by reading actual engine source, not memory:

**C1 — `DifficultyManager` already exists** (`flow/difficulty.ts`) with an
S-curve (Hermite smoothstep) interpolator and auto-advance by score or
level. Curve strings in attempt_001 (`"exp(1.15)"`) were duplicating this.
**Revision:** `WaveSpawner` takes a reference to a `DifficultyManager`
instance (named in the design), not a curve string. Curves are a `Difficulty`
block, authored once, referenced by N mechanics.

**C2 — `WaveController` doesn't exist.** I invented it in the lowering
example. Either the compiler wires it via primitives (`scene.onUpdate` +
`spawn`) or a new engine class is added. **Decision:** lower via existing
primitives for v0 — no new engine classes until the primitives compose
poorly.

**C3 — Missing: `AnimationStateMachine`, `ComboSystem` are real primitives**
I didn't put on the L1 list. Both are solid building blocks for richer
mechanics (`ComboAttacks`, `AnimationGated Actions`). Added to the catalog.

**C4 — `SceneManager` has explicit `TransitionType`** (fade etc.) and flow
conditions are a string keyspace already. My `condition: "player_dead"`
example maps directly — compiler emits `flow.setCondition("player_dead",
true)` on the trigger event.

## The 15 v0 Mechanics — with coverage check

Mechanics grouped by the genre they primarily serve (a mechanic can serve
multiple; genre column is its strongest fit):

| # | Mechanic | Primary genre | What it composes |
|---|---|---|---|
| 01 | **Difficulty** | any | wraps `DifficultyManager`; exposes S-curve interp over time/score/level |
| 02 | **HUD** | any | renders named fields from archetype components to screen overlay |
| 03 | **LoseOnZero** | any | sets flow condition when named archetype field hits 0 |
| 04 | **WinOnCount** | any | sets flow condition when N archetype instances reach a count |
| 05 | **WaveSpawner** | arcade/shooter | spawns enemy archetype in waves; density driven by `Difficulty` |
| 06 | **PickupLoop** | arcade/collectathon | trigger-driven reward + respawn on pickup archetype |
| 07 | **ScoreCombos** | arcade | time-windowed multiplier on `Score` increments |
| 08 | **CheckpointProgression** | platformer/RPG | checkpoint archetype saves `Checkpoint` system state |
| 09 | **LockAndKey** | puzzle/adventure | archetypes tagged `key` open archetypes tagged `lock` on contact |
| 10 | **StateMachineMechanic** | platformer/RPG | authors `AnimationStateMachine` transitions declaratively |
| 11 | **ComboAttacks** | action/fighting | wraps `ComboSystem`; maps input sequences to Action Blocks |
| 12 | **BossPhases** | arcade/RPG | FSM over boss archetype health thresholds → behavior-tree swaps |
| 13 | **TileRewriteMechanic** | puzzle | PuzzleScript-shaped rules on tile grid; uses existing `tilemap_gen` |
| 14 | **RhythmTrack** | rhythm | beat timeline; archetype spawns synced to audio timestamps |
| 15 | **DayNightClock** | sim/RPG | time-of-day scalar drives `DifficultyManager`-like parameter ramps |

**Coverage check against adversarial prompts:**

- "rotate rooms to reach the exit" → `TileRewriteMechanic` (room adjacency
  as tile graph) + `WinOnCount` (exit reached). **Expressible.**
- "rhythm game where you block beats" → `RhythmTrack` (spawns) + `ComboAttacks`
  (input matching within beat window) + `ScoreCombos` (chain multipliers).
  **Expressible.**
- "farming sim with crops and time of day" → `DayNightClock` (time) +
  `PickupLoop` (harvest = pickup) + `StateMachineMechanic` (crop growth
  states). **Expressible, but awkward** — crops aren't quite pickups; may
  need a v1 `ProductionCycle` mechanic.

Two of three genres covered cleanly, one awkward. That's the honest read.
Promote v0 with the awkward case noted.

## Schema skeleton

```ts
// ark/scaffolds/engine/src/design/schema.ts

/** Typed IDs — string aliases that force named references in a script. */
export type ArchetypeId = string & { __brand: 'ArchetypeId' }
export type MechanicId  = string & { __brand: 'MechanicId' }
export type ConditionKey = string & { __brand: 'ConditionKey' }

/** The root document. */
export interface DesignScript {
  meta: DesignMeta
  config: GameRuntimeConfig
  archetypes: Record<string, Archetype>        // key: archetype name
  mechanics: MechanicInstance[]
  flow: FlowStep[]
}

export interface DesignMeta {
  title: string
  vibe: string[]                               // free tags for QA
  target_session_sec?: number
}

export interface GameRuntimeConfig {
  mode: '2d' | '3d'
  camera?: 'perspective' | 'orthographic'
  gravity?: [number, number, number]
  arena?: { shape: 'rect' | 'disk', size: number }
}

export interface Archetype {
  mesh?: MeshName              // 'box'|'sphere'|'capsule'|'plane'|asset ref
  controller?: ControllerName  // 'fps'|'topdown'|'orbit'|'platformer'|...
  ai?: AiName                  // 'chase'|'flee'|'patrol'|'bt:<name>'
  trigger?: TriggerName        // 'pickup'|'damage'|'checkpoint'|...
  components: ComponentSpec[]  // ['Health(100)', 'Score', 'Lives(3)']
  tags: string[]               // free tags, used in mechanic targeting
}

export type ComponentSpec = string
  // parsed as Name(arg1,arg2)  or  Name
  // known: Health, Score, Lives, Stamina, Inventory, Checkpoint, Ammo

export interface MechanicInstance {
  id: MechanicId
  type: MechanicType
  params: Record<string, unknown>  // per-type schema checked downstream
  requires?: MechanicId[]          // topological sort hint
}

export type MechanicType =
  | 'Difficulty' | 'HUD' | 'LoseOnZero' | 'WinOnCount'
  | 'WaveSpawner' | 'PickupLoop' | 'ScoreCombos'
  | 'CheckpointProgression' | 'LockAndKey'
  | 'StateMachineMechanic' | 'ComboAttacks' | 'BossPhases'
  | 'TileRewriteMechanic' | 'RhythmTrack' | 'DayNightClock'

export interface FlowStep {
  scene: string
  transition?: 'fade' | 'cut' | 'slide'
  duration?: number
  condition?: ConditionKey
}
```

Per-type params live in a discriminated union — TS type enforcement catches
bad params at the LLM emission step, not at runtime:

```ts
export type MechanicParams =
  | { type: 'WaveSpawner', archetype: ArchetypeId,
      difficulty_ref: MechanicId, rest_sec: number, arena_radius: number }
  | { type: 'PickupLoop', archetype: ArchetypeId,
      reward_field: string, reward_amount: number, respawn_sec: number }
  | { type: 'LoseOnZero', archetype: ArchetypeId, field: string,
      emit_condition: ConditionKey }
  // ... one entry per MechanicType
```

The compiler's first job is `validate(script: unknown): DesignScript |
ValidationError[]`, which rejects:
- unknown MechanicType / ControllerName / MeshName
- mechanic referencing unknown archetype by id
- dangling flow conditions (no mechanic emits that condition)
- incompatible controller/mode (fps + 2d)
- missing tags required by a mechanic (WaveSpawner with no enemy-tagged
  archetype)

All failures return structured errors Tsunami's error_fixer can read.

## Falsifier for the method

Per Sigma v9.1 C5, every v9 promotion needs a falsifier. This method's:

**Would falsify:** if Tsunami emitting design scripts via this schema
produces a LOWER rate of runnable builds than Tsunami emitting freehand TS
against the engine's fluent API — measured on the same prompt set, same
model, same build harness — then the schema is adding friction without
adding value and should be dropped.

Weaker version: if Tsunami's design-script emissions pass schema validation
at the same rate that freehand-TS emissions compile, the schema isn't
catching a meaningful subset of errors; the extra layer is waste.

## Method Internalization Curve prediction

Per Sigma v9.1 C1: expect the first 30–50 design-script emissions from
Tsunami to be weaker than the plateau. Budget that cost; don't kill the
method on fire-1 outputs. The audit-and-patch loop (QA critique → JSON
patch) IS the internalization substrate for this specific task — each
accepted patch accumulates in the deliverable folder and future runs read
prior designs as context.

## Open questions still not answered

From attempt_001, still open:

- (4) Mutation operators for QA's edit step — candidates: `tweak-param`,
  `swap-block`, `add-block`, `remove-block`, `wrap-block`. The set of legal
  edits IS the search space. v1 deliverable: enumerate, weight by typical
  impact. Keep v0 to `tweak-param` + `add-block` only — simplest to
  implement, largest typical payoff.

- (2) Procedural layout — `tilemap_gen.py` exists; wire as
  `TileRewriteMechanic.layout_source` param. Doesn't need to be its own
  mechanic.

New open question (v1 candidate):

- (6) **Mechanic composition operators.** Can mechanics *wrap* mechanics?
  E.g., `ReverseTime(WaveSpawner)` = Braid-style time reverse. `Shadow(
  PlayerController)` = Link's Awakening shadow. Higher-order mechanics are
  where emergent surprise lives. Out of v0 scope; log as v1 direction.

## Handoff hook

If the other instance picks up: the natural split is engine-side vs.
Tsunami-side.

- **Engine-side work** (TS, lives in `ark/scaffolds/engine/src/design/`):
  `schema.ts` from this doc, `catalog.ts` with the 15 mechanic specs,
  `validate.ts` for the compatibility matrix, `compiler.ts` for lowering,
  `mechanics/*.ts` one per mechanic.

- **Tsunami-side work** (Python, lives in `ark/tsunami/`):
  `tools/emit_design.py` wrapping the compiler, `context/design_script.md`
  replacing the prose dump in `agent.py:2696-2716`, prompt changes in
  `prompt.py` to teach the schema, error feedback integration in
  `error_fixer.py`.

The two halves can proceed in parallel once this doc is accepted. The
seam is the schema file — if both sides import/mirror the same schema
definition, neither half blocks the other.
