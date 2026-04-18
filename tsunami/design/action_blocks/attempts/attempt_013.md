# Action Blocks — v1.0.4 rescope (attempt 013)

> Option C + operator scope correction landed. Action-blocks is ONE
> scaffold. Grid-mode, IF, RTS, card, deckbuilder all belong in
> separate hand-authored scaffolds. Removing grid-mode from action-
> blocks v1. This is the final cleanup before the implementer takes
> over.

## What changed in the operator's direction

Two operator inputs this session:

1. (note_012) Multiplayer — engine handles local multiplayer routing;
   schema is player-count-agnostic. Absorbed in attempt_012.
2. (note_013) **Scaffold library scoping** — each alternative game
   mode is its own scaffold, hand-authored. Action-blocks is the
   real-time-spatial scaffold, not a universal authoring layer.

## The correct action-blocks domain

Confirmed by reading `ark/scaffolds/`:

```
scaffolds/
├── ai-app/        auth-app/        chrome-extension/
├── dashboard/     data-viz/        electron-app/
├── engine/        form-app/        fullstack/
├── game/          landing/         react-app/
└── realtime/
```

Plus a scaffolds-meta dir. Each is a distinct expert-built template.
`game/` is the existing real-time-spatial scaffold (imports `@engine`).
Action-blocks fits inside `game/` (or a next-gen successor) — it's
the design-script method for *this one* scaffold.

Future mode-specific scaffolds (grid-puzzle, IF, RTS, card-game,
turn-based-tactics, racing-sim, persistent-simulation, JRPG-battle)
each get their own design methods, expertly tuned. Not our problem.

## Removed from action-blocks v1.0.4

Six mechanics drop from the catalog. They belong in a future
`grid-puzzle/` scaffold or equivalent:

- `GridPlayfield` (singleton kind — stays as a concept if future
  narrative-adventure needs a coarse grid, but the tile-rewrite
  semantics leave)
- `GridController`
- `TurnManager` (any turn-based scaffold owns this)
- `FallingPieceMechanic`
- `LineClearMechanic`
- `TileRewriteMechanic`

**Corresponding schema changes:**

- `config.playfield` collapses to continuous-only (the `grid` variant
  drops). Action-blocks is continuous-mode.
- The `'puzzle'` value in `meta.shape` stays — it covers real-time
  continuous puzzles (Lemmings, Braid, VVVVVV per note_008's third
  sub-genre). Those are within action-blocks scope.
- `sokoban` example script retires from `tsunami/context/examples/` —
  it belongs in the grid-puzzle scaffold's examples when that scaffold
  is built.

**v2 placeholders removed** (all were grid-mode-adjacent):
- `RoleAssignment` — continuous-puzzle, stays as action-blocks v2 candidate
  since Lemmings is real-time spatial. Keep.
- `CrowdSimulation` — same; keep.
- `TimeReverseMechanic` — Braid is real-time spatial; keep.
- `PhysicsModifier` — VVVVVV is real-time spatial; keep.

All 4 v2 placeholders STAY in action-blocks. They're continuous-puzzle
primitives per note_008 subclass. Good check.

**`MinigamePool` v2 (note_011)** — anthology pattern. WarioWare/Mario
Party/Rhythm Tengoku. WarioWare is real-time spatial within each mini-
game; Mario Party's BoardMovement might be a different scaffold but the
individual minigames fit. Keep as v2 placeholder.

## Revised action-blocks v1.0.4 catalog count

- v1.0.3: 36 mechanics + 4 v2 placeholders + MinigamePool v2 = 41 entries
- v1.0.4: **30 mechanics** + 4 v2 placeholders + MinigamePool = **35 entries**
- Removed: 6 grid-mode mechanics
- Added: none

## Revised top-5 v1 priorities (from numerics)

Per note_013:

1. **`Resource`** (generic) — mana/stamina/boost/currency/super-meter.
2. **`EmbeddedMinigame`** — composability multiplier (note_006).
3. **`WorldFlags` + `DialogTree` + `DialogScript`** — narrative
   layering for action-adventure and narrative-RPG in the real-time
   spatial shape. Content-multiplier per note_009.
4. **`DirectionalContact`** — schema revision (note_003). Already in
   v1.0 as `TriggerSpec.contact_side`.
5. **Concretize `RhythmTrack`** — content-multiplier for rhythm-
   action, which IS real-time spatial (DDR/Beatmania/Crypt of the
   NecroDancer).

Grid-mode bundle (was slot 3 earlier) is **gone** from action-blocks.

## Revised coverage estimate

- Of the 40 numerics prompts, **~29 are in action-blocks scope** (per
  note_013's out-of-action-blocks list).
- With v0 + top-5 v1 additions → estimated **~70–75% of the 29 in-
  scope prompts** expressible-or-caveated.
- Previous 60% gate was computed against all prompts; revised: 60%
  gate applies to **in-scope-for-action-blocks** prompts only.
- Honest coverage on total prompt set drops (because many prompts
  aren't our problem), but **per-scope coverage rises.**

## Updates to reference stubs

Applying these in follow-up edits:

**`schema.ts`:**
- Remove 6 mechanic types from `MechanicType` union
- Remove 6 Params interfaces
- `Playfield` tagged union → collapse to continuous-only variant
- Remove `controller: 'grid'` from `ControllerName`
- Keep the `MinigamePool` MechanicType / placeholder — it's v2
  but within action-blocks scope (WarioWare-class)

**`catalog.ts`:**
- Remove 6 grid-mode entries
- Update `OUT_OF_SCOPE_V1` — add grid-puzzle / tile-rewrite patterns
  with redirect "use grid-puzzle scaffold when built; not action-
  blocks' domain"
- Keep 4 v2 placeholders (RoleAssignment/CrowdSim/TimeReverse/
  PhysicsModifier) — all continuous-puzzle within action-blocks
- Keep `MinigamePool` v2 placeholder

**`tsunami/context/design_script.md`:**
- Remove "Grid-mode (grid-puzzle family)" section from catalog
- Update decline patterns to include grid-puzzle → grid-puzzle
  scaffold redirect
- Drop the sokoban example reference (the file itself moves out)

**`tsunami/context/examples/puzzle_sokoban.json`:**
- Move out of action-blocks examples directory. Options:
  - Delete (lossy; Maps Include Noise says no)
  - Move to `ark/tsunami/design/grid_puzzle/attempts/` as a seed for
    that scaffold's future design work
  - Keep as archived reference at `tsunami/context/examples/
    _retired_sokoban_pre_rescope.json` with a note

  Decision: move to `_retired_sokoban_grid_scaffold_seed.json` —
  flagged, kept, out of action-blocks-active-examples.

## Answering numerics' open question

> *"Is `ark/scaffolds/game/` the action-blocks scaffold, or is action-
> blocks a new scaffold parallel to it?"*

My read (unconfirmed; operator to confirm):

- `scaffolds/game/` is the current real-time-spatial scaffold.
  Today it uses the `@engine` freehand-TS authoring pattern.
- Action-blocks is the **new design-script method** for this same
  scaffold — it REPLACES the freehand-TS pattern within `game/`,
  not sits beside it.
- Other game modes get their own scaffolds when built:
  `scaffolds/grid-puzzle/`, `scaffolds/interactive-fiction/`,
  `scaffolds/rts/`, `scaffolds/card-game/`, etc.

So the engine port lands at:
- `scaffolds/engine/src/design/schema.ts` + `catalog.ts` + `compiler.ts`
  + `mechanics/*.ts` (shared infrastructure)
- `scaffolds/game/src/main.ts` is generated from a design script via
  the compiler
- `tsunami/tools/emit_design.py` dispatches on project type; for
  game projects, it emits a design script matching the engine's
  schema and the compiler does the rest

Implementer to confirm or correct.

## Final state

This is the last design iteration before implementer takes over per
Option C. Reference stubs after this edit round are v1.0.4:

- 30 mechanics + 5 v2 placeholders (MinigamePool + 4 continuous-
  puzzle) = 35 entries
- Continuous-only playfield
- Narrative subset intact (DialogTree, HotspotMechanic, Inventory­Combine,
  PointerController, WorldFlags singleton)
- Action core intact (WaveSpawner, Difficulty, HUD, etc.)
- Content-multiplier mechanics intact (ProceduralRoomChain, BulletPattern,
  RouteMap, RhythmTrack, PuzzleObject)

Scope: real-time single-protagonist spatial client-local games in the
`scaffolds/game/` scaffold. Everything else is someone else's scaffold.

## Option C stance

No more attempts_NNN after this one unless the implementer surfaces
a specific mechanic-spec need or a bug in the handoff. I'm in standby.

If the implementer spawns and asks me to:
- Flesh out a mechanic's lowering (`mechanics/<name>.ts` design)
- Spec validator rules for a specific error class
- Write a decline-message for a new genre prompt
- Cross-audit their compiler output

— I respond directly, no new attempt doc needed.

If numerics' retest fires post-port: I read their output and maybe
write attempt_014 if the 60% gate clears or if a structural gap
surfaces.

Else: silent standby.
