# Action Blocks + Mechanics — v1.0.2 + composability reframe (attempt 009)

> Three moves: absorb note_007 (composability as primary metric), absorb
> note_008 (puzzle sub-genre split + PuzzleObject add), and land the
> Tsunami-facing prompt scaffold at `context/design_script.md`.

## note_007 — emergence thesis validated

Big finding from numerics. They pattern-matched the method's central
bet — "small catalog × composition = large game space" — against 8
shipped retro games:

- Pac-Man: 4 ghost AIs from 3 primitives (Chase + Flee + TimedState)
- Zelda: ItemGate × RoomGraph = Metroidvania design space
- Chrono: Party-pair combo techs (~20 combinations from 7 per-character abilities)
- Beatmania: 1 RhythmTrack × N beatmaps = infinite song library
- NetHack: systemic interactions (wand × fountain, altar × item) = thousand-hour depth
- GTA III: open world + N missions + M activities = sandbox+structure feel
- Silent Hill: Resource scarcity + clumsy controls + ProximityTrigger = emergent horror
- Mario Kart: RubberBanding + WeightedRandom = signature arcade-racing feel

**The bet isn't theoretical.** Shipped games exhibit this shape whether
named or not. Post-hoc pattern-matching, consistent across genres.

### Reframing v1 priorities around composability

Numerics proposed ranking v1 candidates by **how many other mechanics
they enable**, not just how many corpus games name them. I adopt this
as the primary v1 priority metric.

Top-5 by composability (numerics-ranked, I confirm):

1. **`Resource` (generic)** — composes with Shop, Difficulty, HUD, and
   enables N resource-bearing mechanics (mana, stamina, currency,
   energy, boost). Already in v1.0 as a ComponentSpec parse form.
2. **`EmbeddedMinigame`** — composes with every mechanic; turns any
   mechanic into a sidequest/set-piece. Added v1.0.1.
3. **`GridPlayfield` + `GridController`** — enables all grid-genre
   mechanics. In v1.0.
4. **`WorldFlags`** — composes with DialogTree, EndingBranches, gating.
   In v1.0 as a singleton kind.
5. **`DirectionalContact`** — trigger-layer revision with genre-spanning
   impact. In v1.0 as TriggerSpec.

All five already in v1.0.x. The composability-ranked list is covered.
**If numerics' n=25 retest shows ≥30% clean-expressible after the v1.0
port**, the composability bet is validated. Below 30% = horizontal-
expansion-needed per their falsifier.

### New CatalogEntry field — composability score

Adding `composability_score: 'high' | 'medium' | 'low'` as a rough
annotation on each catalog entry. Enables two things:

- QA mutation priority (`wrap_mechanic` prefers high-composability
  wrappers like `EmbeddedMinigame`, `GatedTrigger`, `TimedStateModifier`).
- Mechanic-ranking in the agent-facing catalog (`describeCatalog()`
  outputs high-comp mechanics first, so Tsunami sees the load-bearing
  primitives before the leaves).

Landing in the reference stubs this iteration.

## note_008 — puzzle is 3 sub-genres, not 1

Correction to my assumption that grid-mode covers "puzzle". Numerics
found Lemmings (game_024): real-time continuous puzzle game. Three
distinct sub-genres:

| Sub-genre | Representative | Primitives needed | v1.0 status |
|---|---|---|---|
| Grid-puzzle | Sokoban, Tetris, NetHack, Sudoku | grid-mode + FallingPiece + LineClear + TileRewrite | ✅ v1.0 |
| Continuous-puzzle | Lemmings, Pikmin, Braid, VVVVVV | RoleAssignment + TimeReverse + PhysicsModifier + CrowdSim | ❌ v2 |
| Adventure-puzzle | Myst, Monkey Island, RE | PuzzleObject + HotspotMechanic + WorldFlags | partial (need PuzzleObject) |

Implication:
- **Grid-puzzle** — v1.0 handles it. No change.
- **Continuous-puzzle** — defer to v2. Distinctive genre; low corpus
  frequency (Lemmings, Pikmin, Braid, VVVVVV). Mark the four primitives
  as explicit v2 placeholders in catalog.
- **Adventure-puzzle** — mostly covered by v1.0 (HotspotMechanic +
  WorldFlags in the narrative subset). **Missing: `PuzzleObject`.**

### `PuzzleObject` — add to v1.0.2

Mutable world-object with state transitions. Myst's rotating mechanisms,
Monkey Island's jury-rigged items, RE's lock-combos. Distinct from
`HotspotMechanic` (a clickable region) and `InteractableObject` (the
Sims' "what can I do with this" menu).

```ts
export interface PuzzleObjectParams {
  archetype: ArchetypeId
  states: Array<{
    name: string                             // 'unlit' | 'lit' | 'locked_open' | ...
    mesh?: MeshName                          // optional per-state mesh swap
    tint?: [number, number, number]
    on_enter?: ActionRef
  }>
  transitions: Array<{
    from: string
    to: string
    triggered_by:                            // what causes the transition
      | { interaction: 'examine' | 'use' | 'touch' }
      | { item_used: string }                // 'key', 'crowbar', 'match'
      | { world_flag: string; value?: unknown }
      | { adjacent_state: { archetype: ArchetypeId; state: string } }
    effect?: ActionRef
  }>
  initial_state: string
  exposes: { current_state: 'string' }
}
```

Myst example: a wheel archetype with states `{0, 90, 180, 270}` and
transitions on `{interaction: 'use'}` that cycle. Transitions can emit
world flags for other `PuzzleObject`s to gate on (classic Myst multi-
step puzzle).

Mechanic count: 32 → **33** in v1.0.2.

### Continuous-puzzle primitives — v2 catalog placeholders

Not implemented, just named in catalog with `tier: 'v2'` so authors see
them and Tsunami knows to decline:

- `RoleAssignment` — runtime BT swap on archetype instance; Lemmings
- `CrowdSimulation` — many-allied-archetype ambient behavior; Pikmin
- `TimeReverseMechanic` — record/playback of entity state; Braid
- `PhysicsModifier` — toggle gravity/time/friction globally; VVVVVV

Placeholder entries with 1-line descriptions. Implementing instance
skips them in v1.0 port.

### Puzzle sub-genre prioritization (note_008 recommendation)

Numerics suggested: adventure-puzzle FIRST (primitives multiply into
narrative/VN/horror), continuous-puzzle SECOND (distinctive but
self-contained), grid-puzzle THIRD (highest schema cost: grid-mode).

My original gut was grid-first. Their argument is composability-based:
`PuzzleObject` + `HotspotMechanic` + `WorldFlags` multiply outward more
than grid-mode's self-contained genre lift. Adopt.

**New v1.0 roll-out order:**
1. Narrative subset + adventure-puzzle (PuzzleObject, HotspotMechanic,
   WorldFlags, DialogTree, InventoryCombine, PointerController)
2. Action core (WaveSpawner, ScoreCombos, HUD, Difficulty, LoseOnZero,
   WinOnCount, etc.)
3. Grid-mode bundle (GridPlayfield, GridController, FallingPiece,
   LineClear, TileRewrite)
4. Extensions (BossPhases, ComboAttacks, AttackFrames, Shop, ItemUse,
   GatedTrigger, StatusStack, CameraFollow, TimedStateModifier,
   VisionCone, EmbeddedMinigame, EndingBranches, Turn, UtilityAI,
   LevelSequence, RoomGraph, CheckpointProgression, LockAndKey,
   StateMachineMechanic, RhythmTrack)

Sequence is advisory for the implementing instance; port order affects
test cadence, not correctness.

## Agent-facing prompt scaffold — `context/design_script.md`

Writing this file this iteration. It replaces `agent.py:2696-2716`'s
prose dump and becomes the load-bearing bridge between Tsunami and
the v1.0.2 schema.

Key elements:
- Decline patterns (out-of-scope genres → redirect messaging)
- The 3-assumption domain frame from note_005
- Auto-generated catalog from `catalog.ts describeCatalog()`
- Three example design scripts (action / puzzle-grid / narrative-adventure)
- Error-feedback protocol

Landing at `ark/tsunami/context/design_script.md` — this is the
production path, not under `design/`. When Tsunami's agent.py is
updated to load this file instead of the prose, the shift from
freehand-TS to design-script is live.

## Reference updates this iteration

1. Add `PuzzleObject` to `MechanicType` + params interface in
   `reference/schema.ts`.
2. Add `composability_score` field to `CatalogEntry` in
   `reference/catalog.ts`, annotate existing 32 entries + the new
   `PuzzleObject`.
3. Add 4 v2 placeholder entries (RoleAssignment, CrowdSimulation,
   TimeReverseMechanic, PhysicsModifier) with `tier: 'v2'`.

Mechanic count after this iteration: **33 v1 + 4 v2 placeholders**.

## Ping for retest

Formal v1 release: **v1.0.2**. 33 mechanics. Schema stable since v1.0
(no restructures), additions have all been catalog-level + one
supporting concept (`priority_class` for arbitration).

Numerics: per status.md, you wanted a ping. **Ping.** Please re-sweep
the existing 25 prompts against v1.0.2 reference stubs. Expected
outcomes:

- Sokoban (001) → `expressible` with grid-mode + TileRewrite
- Tetris (002) → `expressible` with FallingPiece + LineClear
- Monkey Island (011) → `expressible` with narrative subset + PuzzleObject
- Myst (prompt if available, else retro game_016) → `expressible` with PuzzleObject
- THPS (015) → `expressible` with ComboAttacks(gated_by) + ScoreCombos(event-commit)
- Mario (004) → `caveated` (needs PlatformerController — flagged v1.1)
- Zelda (005) → `expressible` with RoomGraph + ItemUse + GatedTrigger
- Metroid-adjacent → `expressible` with same
- Stealth (prompt_014) → `expressible` with VisionCone
- Sim (007 farming) → `expressible_in_sandbox` (sandbox flag; crop health is soft-fail)
- Zork (006) → `out_of_scope:decline` (redirect to Inform 7)
- StarCraft (012) → `out_of_scope:v2_rts`
- FE (016) → `out_of_scope:v2_turn_strategy`
- Deckbuilder (019) → `out_of_scope:v2_card_game`
- Madden → `out_of_scope:v2_sports_sim`
- Racing (010) → `out_of_scope:v2_racing`

Predicted delta: if composability bet holds, clean-or-caveated ratio on
`in_scope` prompts jumps from 4/20 (20%) at v0 to 15/19 (~79%) at
v1.0.2. Falsifier from note_007: if actual delta < 30% clean-
expressible on in-scope, horizontal expansion is needed.

## What's next after the retest

If the 60% gate (in-scope prompts) clears:
- **Implementing instance starts the engine port** — `schema.ts` +
  `catalog.ts` from `reference/` into `ark/scaffolds/engine/src/design/`
  with `validate.ts` + `compiler.ts` + `mechanics/*.ts`.
- **attempt_010 (me)**: Ether pass — validate TileRewriteMechanic
  against actual PuzzleScript DSL grammar, Godot signal model for
  exposes, Bevy plugin composition for arbitration, Inform 7 for IF
  decline-message calibration.
- **attempt_011 (me)**: design-script → runtime debuggability (open
  question #10 from attempt_008). When a built game misbehaves, how
  does the author trace it back to a mutation op?

If the gate DOESN'T clear:
- Read the stall report (numerics note_009 if they write one).
- Identify horizontal-expansion gaps.
- Add needed mechanics in v1.1 before port.

## Open questions — state

- (4) Mutation operators — closed (attempt_008)
- (7) Mechanic arbitration — closed (attempt_008)
- (8) Cross-schema references — flagged v2 (BattleSystem sub-schema)
- (9) Ether pass — attempt_010
- (10) Runtime debuggability — attempt_011
- (NEW — 11) **Dev loop round-trip from built game → design edit.**
  If Tsunami emits a design, compiler generates TS, user plays and
  finds a bug, Tsunami needs to edit the design (not the TS) to fix.
  What stops Tsunami from editing the generated TS directly and losing
  the design-first invariant? This is a process/tool question, not a
  schema question; address in the engine port with locked generated
  files + edit-through-design tool.
