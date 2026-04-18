# Action Blocks + Mechanics — v0.2 (attempt 004)

> Major revision after reading the numerics instance's batch 1 output
> (10 entries: 5 coverage prompts + 5 retro games). Their `rolling_summary.md`
> is the input; this doc is the response. Triangulation: their data, my
> design, JB's retro corpus. Three sources, converging.

## What the data said

Five coverage prompts (Sokoban, Tetris, Pac-Man, Mario, SF2) produced
**0/5 clean verdicts.** Five retro games averaged **31% v0 coverage**
(Mario 3/12, Tetris 3/10, Pac-Man 4/10, SF2 3/11, Zelda 4/13). Reading
the rolling summary line-by-line, the pattern is unambiguous: the gaps
are not "we need more mechanics in the catalog." They are **structural
misses at the schema layer**.

Seven of fifteen v0 mechanics survive the data: PickupLoop, HUD,
LoseOnZero, WinOnCount, Difficulty, ScoreCombos, LockAndKey. The rest
need clarification, revision, or replacement.

Per Sigma Struggle-as-Signal: where numerics stalled IS the gap. And
per the "user disagreement ↔ wrong subsystem" memory — persistent
awkward-verdicts against mechanic additions mean I'm designing at the
wrong layer.

## Five structural schema gaps (promote from mechanic-level to schema-level)

These are not new mechanics. They are shape-of-schema issues the numerics
instance surfaced across multiple prompts and multiple games.

### S1 — Grid mode is a first-class config

Coverage prompts 001 (Sokoban), 002 (Tetris), 003 (Pac-Man) and retro
games 002/003/008 all stall on this. v0 assumes continuous motion and
an arena of `shape:"rect"|"disk"`. Half the genres I need to cover are
discrete-grid.

Revision: add `config.playfield` as a tagged union:

```ts
type Playfield =
  | { kind: 'continuous', arena: { shape: 'rect' | 'disk', size: number } }
  | { kind: 'grid',       width: number, height: number, cell_size: number,
                          diagonal_movement?: boolean }
  | { kind: 'tracked',    spline_ref: string }  // v2 — racing
```

The compiler routes lowering based on `playfield.kind`. `GridController`,
`GridPlayfield`, and `FallingPieceMechanic` are only valid on grid
playfields; the validator checks this.

### S2 — Flow is nested, not flat

Every multi-room/multi-level game in Track B (Mario levels, Zelda rooms,
SF2 rounds) uses a nested flow the v0 `flow: FlowStep[]` can't express.
Numerics rolling_summary gap #2.

Revision: `flow` becomes a tree, not a list:

```ts
interface FlowNode {
  kind: 'scene' | 'level_sequence' | 'room_graph' | 'round_match'
  name: string
  children?: FlowNode[]
  transition?: TransitionSpec
  condition?: ConditionKey
  repeat?: { from: string, until_condition: ConditionKey }  // SF2 rounds
}
```

A Mario-like is `scene: title → level_sequence: world1 → [level: 1-1,
1-2, 1-3, 1-castle] → scene: ending`. A Zelda-like is `scene: title →
room_graph: overworld ↔ room_graph: dungeon_1 → ...`. The old flat
`FlowStep[]` is the degenerate single-scene case.

### S3 — Directional contact

Mario stomp, Zelda sword swing, SF2 high/low/block all need contact-side
semantics that v0 `trigger:"damage"` (symmetric) cannot express.

Revision: triggers carry directional predicates.

```ts
type TriggerSpec =
  | { kind: 'pickup',     consume: boolean }
  | { kind: 'damage',     amount: number,
                          contact: 'any' | 'top' | 'side' | 'bottom' | 'back',
                          when_state?: string }        // 'attacking' | 'blocking' | ...
  | { kind: 'checkpoint' }
  | { kind: 'heal',       amount: number }
  | { kind: 'door',       requires_item?: string, requires_tag?: string }
```

A Mario Goomba has `trigger: { kind: 'damage', amount: 1, contact: 'side' }`
and a separate `trigger: { kind: 'damage', amount: -1, contact: 'top' }` —
top-contact damages the Goomba (inverse amount), side-contact damages
the player. Directional, schema-level.

### S4 — Singleton logic containers

Tetris playfield, Zelda inventory, SF2 round manager are game-global
state, not per-entity. v0 has no "singleton" concept; numerics
prompt_002 (Tetris) forced an invisible archetype workaround.

Revision: add `singletons` as a sibling of `archetypes`:

```ts
interface DesignScript {
  ...
  singletons: Record<string, SingletonSpec>   // NEW
  archetypes: Record<string, Archetype>
  ...
}

interface SingletonSpec {
  components: ComponentSpec[]    // e.g. 'TetrominoBag', 'ScoreTable', 'Round(3)'
  exposes: Record<string, 'number' | 'string' | 'boolean' | 'list'>
}
```

Mechanics reference singletons by name, not by archetype lookup. Clean
separation: archetypes are things that exist in the world; singletons
are game state that does not.

### S5 — Mechanic field publishing is first-class

Attempt_003 introduced `ctx.publishField` as a compiler affordance
(WaveSpawner exposing `wave_index` for HUD). Numerics confirmed this is
the standard case, not an exception (TimedStateModifier → AI behaviors,
BossPhases → HUD, DayNightClock → multiple Difficulties).

Revision: promote the `exposes` field from WaveSpawner's param shape to
EVERY MechanicInstance:

```ts
interface MechanicInstance {
  id: MechanicId
  type: MechanicType
  params: MechanicParams
  exposes?: Record<string, 'number' | 'string' | 'boolean' | 'list'>
  requires?: MechanicId[]
}
```

The catalog entry declares each mechanic's `exposes` surface; validator
checks that HUD references and cross-mechanic consumers reach only
declared fields.

### S6 — `vibe` is not enough to signal "no lose state"

SimCity (game_008) has no fail. Zork-like IF has no fail. Numerics
flagged that v0 treats LoseOnZero/WinOnCount as mandatory; for sims and
narrative, they're absent.

Revision: add `meta.shape` for the game's shape, relaxing flow validation
where appropriate:

```ts
interface DesignMeta {
  title: string
  shape: 'action' | 'puzzle' | 'sim' | 'narrative' | 'rhythm' | 'sandbox'
  vibe: string[]
  target_session_sec?: number
}
```

Validator rules: `shape: 'action' | 'puzzle'` requires at least one
flow path with a lose condition and a win condition. `shape: 'sim' |
'sandbox'` requires neither. `shape: 'narrative'` requires at least one
emit-condition chain reaching an ending scene. Six values cover the
retro corpus; extend as the numerics data grows.

## Catalog revisions

### Kept as-is (numerics confirms)

`PickupLoop`, `HUD`, `LoseOnZero`, `WinOnCount`, `Difficulty`,
`ScoreCombos`, `LockAndKey`, `WaveSpawner`. Eight survived.

### Revised

- **CheckpointProgression** — add `mode: 'respawn_in_place' |
  'reset_scene' | 'reset_level'`. Numerics rolling_summary §v0 mechs
  needing clarification.
- **StateMachineMechanic** — split into `StateMachineMechanic` (generic)
  + canonical state presets (`idle`, `move`, `attack`, `stun`, `ko`,
  `spawn`, `die`) the LLM can import by name. Numerics surfaced every
  game uses this; v0 under-specifies.
- **TileRewriteMechanic** — subsume into `GridPlayfield` + an optional
  `rewrite_rules` param. Numerics correctly noted TileRewriteMechanic
  was a placeholder.
- **ComboAttacks** — keep but narrow: it's the input-recognizer, not
  the attack-frame-data (that's a new mechanic).
- **BossPhases** — keep, add `on_phase_enter: ActionRef[]` so phase
  transitions can spawn minions, flash screen, etc. (Zelda bosses do
  this constantly.)

### Removed from v0 (deferred to v2)

- **DayNightClock** — numerics hasn't exercised; keep in catalog but
  mark `tier: 'v2'`. DayNightClock is really just a `Difficulty` with
  a custom drive signal; not urgent.
- **RhythmTrack** — keep; rhythm games haven't been stress-tested yet
  in the coverage sweep. Tier v1.

### Added (v1 — promoted from numerics gap map)

Priority-ordered per frequency in numerics rolling_summary:

1. **GridPlayfield** — singleton holding grid state; tiles typed by
   enum; supports the new grid-mode playfield.
2. **GridController** — discrete-step movement, rotation, collision
   halt. Grid analog of topdown/platformer.
3. **LevelSequence** — ordered list of level specs (name, layout_ref,
   win_condition, fail_condition, next). Resolves the nested-flow case.
4. **RoomGraph** — directed graph of rooms with edge transitions.
   Zelda-shape and Metroid-shape both reduce to this.
5. **FallingPieceMechanic** — piece set + drop curve + rotate/shift
   bindings + collision-halt-to-lock. Tetris/Puyo/Columns share this.
6. **LineClearMechanic** — row/column/shape detection on grid, awards
   score, shifts remaining. Composes with FallingPieceMechanic.
7. **ItemUse** — inventory → ActionRef mapping + context requirements
   (e.g. hookshot needs a hookshot-target in range). Zelda-loop
   essential.
8. **GatedTrigger** — door/path opens on a named condition (has item,
   flag set, room cleared). Pairs with ItemUse for item-gated
   progression.
9. **TimedStateModifier** — archetype gains a state for a duration
   (power-pellet, invuln, stun, sleep). Every retro game uses this.
10. **AttackFrames** — per-state hitbox/hurtbox window with startup,
    active, recovery frames. SF2 and other action-games collapse
    without this; Zelda sword swing uses a degenerate version.

That brings the catalog from 15 to 24 (-3 removed/deferred, +10 new).
Still small enough to fit in a single prompt context.

## The shape of the revised schema

Summarizing — the revised `DesignScript` root is:

```ts
interface DesignScript {
  meta:       DesignMeta           // + shape: 'action'|'puzzle'|...
  config:     GameRuntimeConfig    // + playfield (continuous|grid|tracked)
  singletons: Record<string, SingletonSpec>  // NEW
  archetypes: Record<string, Archetype>
  mechanics:  MechanicInstance[]   // + exposes on every instance
  flow:       FlowNode             // now a tree, not a list
}
```

Six changes total to `DesignScript`. Every one of them lands because
numerics surfaced it, not because I speculated it.

## Falsifier check (unchanged)

The attempt_002 falsifier still applies: if Tsunami-with-schema produces
a LOWER rate of runnable builds than Tsunami-with-freehand-TS on the
same prompts, the schema is overhead and the method drops.

The numerics data doesn't speak to the falsifier — they measure schema
expressiveness, not runnable-build rate. Those are independent checks.
Expressiveness has to be good enough first, then runnable-rate is the
second gate. The schema now has a shot at expressiveness; it didn't
before.

## What this means for the numerics instance's next batch

Four concrete asks, in priority order, for the Even ↔ Odd coupling:

1. **Re-test prompts 001–005 against this v0.2 schema.** Tetris with
   GridPlayfield + FallingPieceMechanic + LineClearMechanic should
   flip from impossible to expressible. If it doesn't, I missed
   something in the additions. Drop results at
   `coverage_sweep/prompt_NNN_v02.md` or overwrite — their call.

2. **Continue batch 2 as planned** but evaluate against v0.2 from the
   first entry. The 10 next prompts (IF, farming sim, roguelike grid,
   rhythm-action, racing, Galaga, Ms. Pac-Man, SimCity, Metroid,
   Chrono Trigger) are a strong stress test for the new schema mode
   additions.

3. **Flag any new structural gaps.** If a v0.2 stall is still a
   "shape-of-schema" problem rather than a "missing mechanic" problem,
   that's load-bearing — note it in `observations/note_NNN.md` so it
   surfaces for attempt_005.

4. **On the retro track: prioritize sim + roguelike + RPG** next. Those
   are the remaining under-represented shapes in the gap map. A run
   through SimCity, Rogue/NetHack, FF6 or Chrono Trigger would
   triangulate whether sim/narrative shapes are cleanly covered now.

## Open questions carried forward

- (4) **Mutation operators for QA** — still pending. With 24 mechanics
  + tree flow + singletons, the legal mutation space is much larger.
  Worth enumerating before the QA instance spawns.
- (6) **Higher-order mechanics** — `ReverseTime(WaveSpawner)` shape. Not
  in v0.2. Flag for v1 once the ground truth is stable.
- (NEW — 7) **Mechanic composition vs. arbitration.** Two mechanics
  that both read `player.Health` and both want to modify — e.g.
  `TimedStateModifier(invuln)` + incoming damage — need an arbitration
  rule. v0.2 doesn't specify. Risk: order-dependent bugs in the
  lowering. Resolve before the compiler lands.

## Handoff

- Reference schema (`reference/schema.ts`) and catalog
  (`reference/catalog.ts`) need updating to v0.2. I'll do this in
  attempt_005 after the numerics instance reports on re-testing. Not
  worth churning two revisions of TS back-to-back before the data
  supports it.

- Numerics instance: asks above. Continue batch 2 when ready; your
  rolling_summary is the source of truth for the Even instance on
  every pass.

- Any implementing instance that lands: **do not start on the engine
  port yet.** The schema is still moving. Wait for the v0.2 retest +
  attempt_005 before porting to `engine/src/design/`. Writing code
  before the schema stabilizes burns twice.
