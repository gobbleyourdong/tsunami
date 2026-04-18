# Action Blocks + Mechanics — v0.2.2 (attempt 006)

> Answers to numerics status.md (three non-blocking asks), adoption of
> three observation notes (IF / grid / directional contact), four new
> v1 mechanics from the corpus frequency data, and a structural
> acknowledgment of the sim/JRPG genre collapse.

## Triangulation state at n=15 + n=15

`retro_priors/frequency.md` aggregate after batch 2:

- **Mean v0 coverage: 27.6%** across 10 shipped retro games.
- **Genre-weighted variance is huge:** arcade 36%, platformer/action
  27%, puzzle 30%, action-adventure 31%, **sim/JRPG 8.5%**.
- **Triangulation top-5** (Track A + Track B converged, both tracks
  independent): `LevelSequence`, `GridPlayfield`, `DirectionalContact`,
  `RoomGraph`, `TimedStateModifier`. All five in my attempt_004 v0.2.

The method is **working for action/arcade, collapsing for sim/JRPG.**
That's a domain-map finding, not a bug to fix. See `§ Genre-coverage
boundary` below.

## Answering status.md asks

### Ask 1 — LevelSequence v0-vs-v1 placement + minimum viable schema

**Placement:** v0.2 promoted. Confirmed. 7/10 retro games and 5/10
Track A prompts name it — the most frequent v1 candidate.

**Minimum viable schema:**

```ts
interface LevelSequenceParams {
  levels: Array<{
    id: string
    // One of these must be present — defines level content:
    layout_source?: string               // reference to a tilemap_gen.py output
    archetype_overrides?: Record<string,  // per-level archetype tweaks
      Partial<Archetype>>
    spawn_list?: Array<{                 // explicit spawn placements
      archetype: ArchetypeId
      at: [number, number] | [number, number, number]
    }>
    // Win / lose conditions for THIS level (override global):
    win_condition?: ConditionKey
    fail_condition?: ConditionKey
    // Transition out of this level:
    on_win?: 'next' | string             // 'next' advances; string names a level
    on_fail?: 'retry' | 'previous' | string
  }>
  start_at: string                        // id of first level
  cycle_on_complete?: boolean             // loop back vs end flow
  exposes: { current_level: 'string', levels_completed: 'number' }
}
```

It's a mechanic, not a flow-node — lives in `mechanics[]`, not
`flow.children[]`. Reason: the flow tree handles *scene* granularity
(title/game/ending); LevelSequence handles the *level* granularity
within a game scene. Same pattern as Mario's `flow: title → game →
gameover` with a LevelSequence inside the `game` scene sequencing
through 1-1 → 1-2 → ... → 1-castle.

`RoomGraph` is the sibling mechanic for non-linear level progression
(Metroid/Zelda). The two are the two shapes of within-game progression:
ordered list vs. graph.

### Ask 2 — Grid mode: config flag vs. second schema root

**Confirmed: config flag.** Matches my v0.2 `config.playfield` tagged
union and note_002's recommendation. 70–80% of the schema (archetypes,
flow, HUD, LoseOnZero, WinOnCount, Difficulty) applies to both modes;
duplicating was the wrong move.

Compiler branches on `config.playfield.kind`. Grid-only mechanics
(`GridController`, `GridPlayfield`, `FallingPieceMechanic`,
`LineClearMechanic`, `TurnManager` when gated) get validated against
`playfield.kind === 'grid'`; continuous-only mechanics (`WaveSpawner`
arena-radius, `PlatformerController` when added) against `'continuous'`.

Closes the decision. Note_002 ships as-specified.

### Ask 3 — IF schema: separate doc or forbid?

**Adopting note_001 option (C):** accept the limit, add a narrow
adjacent subset, direct full IF elsewhere.

- Full IF (Zork, Anchorhead, Inform-class) — **out of scope.** The
  method targets real-time spatial games. Tsunami should decline
  Zork-class prompts with a message pointing at Inform 7 / Twine.
- Adjacent genre — dialogue-heavy action-adventure (Zelda talk,
  Chrono branching, Monkey Island hotspots) — **in scope** via four
  new mechanics (below).

Prompt 011 (Monkey Island) and prompt 006 (Zork) sit on opposite sides
of this line. Monkey Island is 70% spatial + 30% IF-shaped; playable
with the narrow subset. Zork is 10% spatial + 90% IF-shaped; decline.

Write the decline path into `tsunami/context/design_script.md` at the
top: "This method targets real-time spatial games. For text adventures,
use Inform 7 or Twine — the scaffold directs accordingly."

## Adopting observation notes

### Note_001 — IF

Adopted as above (option C + narrow adjacent subset). v0.2.2 adds:

- `DialogTree` — branching conversations with state-gated choices.
- `WorldFlags` — named boolean/enum global state, queryable in
  conditions. Companion to singletons.
- `HotspotMechanic` — named clickable regions with enter/examine/use
  actions. For point-and-click-adjacent.
- `InventoryCombine` — recipe table (item_a + item_b → item_c).
- `PointerController` — controller name for cursor-driven input.

These four mechanics + one controller form a coherent subset. Any
adventure/RPG-adjacent prompt should be expressible with them.

### Note_002 — Grid mode schema split

Adopted verbatim. v0.2 `config.playfield: {kind: 'grid', ...}` + the
five required mechanics (GridController, GridPlayfield, TurnManager,
FallingPieceMechanic, TileRewriteMechanic upgraded from placeholder).
`TileRewriteMechanic` is now specified against a concrete PuzzleScript-
style rule DSL — see `§ Open: rule syntax` below.

### Note_003 — Directional TriggerSpec

**Adopted verbatim with one tweak.** Their schema:

```ts
interface TriggerSpec {
  kind: 'pickup' | 'damage' | 'checkpoint' | 'heal' | 'stomp' | 'bump' | 'block' | string
  from_dir?: 'above' | 'below' | 'side' | 'front' | 'back' | 'any'
  on_contact?: ActionRef
  on_reverse?: ActionRef
  exclusive?: boolean
}
```

My only tweak: rename `from_dir` → `contact_side` for symmetry with
physics-engine norms ("contact side" is the Box2D/Bevy term) and add
`'bottom'` for "the entity's collision bottom was hit" — matters for
Mario stomp where `above` is ambiguous between "attacker from above" vs
"attacker's top contact".

Final:

```ts
interface TriggerSpec {
  kind: 'pickup' | 'damage' | 'checkpoint' | 'heal' |
        'stomp' | 'bump' | 'block' | 'hit' | string
  contact_side?: 'top' | 'bottom' | 'side' | 'front' | 'back' | 'any'
  on_contact?: ActionRef   // what happens to THIS entity
  on_reverse?: ActionRef   // what happens to the OTHER entity
  when_state?: string       // e.g. 'attacking' | 'blocking' | 'airborne'
  exclusive?: boolean       // destroy trigger after fire (pickup-style)
}
```

Backcompat: `trigger: "pickup"` is sugar for `trigger: {kind:
"pickup", exclusive: true}`. Validator expands on parse.

Goomba example from note_003:
```json
"goomba": {
  "mesh": "box", "ai": "patrol",
  "trigger": { "kind": "damage",
               "contact_side": "side",
               "on_contact": { "kind": "damage", "archetype": "player", "amount": 1 },
               "on_reverse": { "kind": "damage", "archetype": "goomba", "amount": 999 },
               "when_state": "alive" },
  "tags": ["enemy"]
}
```

Top-hit kills goomba; side-hit damages player. Schema-level. Done.

## v0.2.2 mechanic additions from frequency data

Beyond the four adventure-subset additions above, the corpus frequency
names three more ≥ 3-source candidates I hadn't promoted:

### `Shop` — 6 games
Inventory + currency-gated purchases. Universal in RPG/action-adventure.

```ts
interface ShopParams {
  vendor_archetype: ArchetypeId          // NPC who owns the shop
  currency_field: string                  // e.g. 'Resource(money)'
  stock: Array<{
    item: string                          // item name
    price: number
    unlock_condition?: ConditionKey
    stock_count?: number                  // infinity if omitted
  }>
  ui_layout?: 'list' | 'grid' | 'dialog_embedded'
}
```

Lowers to a `DialogTree` subtree with special buy/sell verbs. Pairs
with `InventoryCombine` and `ItemUse`.

### `UtilityAI` — distinct AI kind (from game_015 The Sims)
The Sims' autonomous sim behavior is utility-function AI. Distinct
from chase/flee/patrol/BT. Add as a new `AiName`:

```ts
// AiName extends:
| `utility:${string}`   // e.g. 'utility:sim_needs' referencing a UtilityAI mechanic
```

Plus the mechanic:

```ts
interface UtilityAIParams {
  archetype: ArchetypeId
  needs: Array<{                          // generalizes Resource
    name: string                          // 'hunger', 'comfort', 'social', ...
    decay_per_sec: number
    max: number
    initial?: number
  }>
  actions: Array<{                        // candidate actions the sim can take
    name: string
    need_deltas: Record<string, number>   // how this action changes needs
    precondition?: string                 // expression over world state
    effect: ActionRef
  }>
  selection: 'highest_need' | 'weighted_sample' | 'expected_utility'
}
```

Covers Sims autonomy + can be used for farm animals, RPG companions,
RTS unit idle behavior. Single mechanic, wide reach.

### State-gated `ComboAttacks` + `BankOnEvent ScoreCombos` (THPS deltas)

Two minor revisions rather than new mechanics:

- `ComboAttacks.patterns[i]` gains `gated_by?: string` — pattern only
  fires when named flag/state is active. THPS: `gated_by: 'airborne'`.
- `ScoreCombos` gains `commit: 'window' | 'event'` — event mode banks
  the combo on a named event rather than timing out. THPS: `commit:
  'event'` with event `'land'`.

Both are params, not new mechanics.

## Updated catalog count

v0.2.2 mechanics, grouped:

- **Kept from v0** (8): PickupLoop, HUD, LoseOnZero, WinOnCount,
  Difficulty, ScoreCombos, LockAndKey, WaveSpawner
- **Clarified** (5): CheckpointProgression (mode param),
  StateMachineMechanic (canonical states), TileRewriteMechanic (grid-
  mode only, rule DSL), ComboAttacks (+gated_by), BossPhases
  (+on_phase_enter ActionRef[])
- **Deferred v2** (2): DayNightClock (weak corpus support so far),
  RhythmTrack (not exercised yet; keep but don't block on)
- **v0.2 additions** (10): GridPlayfield, GridController, LevelSequence,
  RoomGraph, FallingPieceMechanic, LineClearMechanic, ItemUse,
  GatedTrigger, TimedStateModifier, AttackFrames
- **v0.2.1 additions** (2): Resource (generic component),
  TurnManager (mechanic)
- **v0.2.2 additions** (7): Shop, UtilityAI, DialogTree, WorldFlags
  (singleton kind), HotspotMechanic, InventoryCombine, PointerController
  (controller name, not a mechanic)

Net: **27 mechanics + 3 supporting concepts** (Resource component,
WorldFlags singleton, PointerController). Up from v0's 15.

## Genre-coverage boundary (Method Domain Map entry)

Per Sigma Method Domain Map discipline — name what the method does NOT
do, with evidence.

Frequency data shows:

| Genre-family | v0 coverage | Method fit |
|---|---|---|
| Arcade (Pac-Man, SF2, Galaga) | 36% | **Target** |
| Action-platformer (Mario) | 27% | **Target with v1 additions** |
| Action-adventure (Zelda) | 31% | **Target with v1 additions** |
| Metroidvania (Metroid) | 30% | **Target with v1 additions** |
| Puzzle (Tetris) | 30% | **Target with grid-mode** |
| JRPG (Chrono) | 8% | **Out of scope v0** — `BattleSystem` gap |
| Sim (SimCity, Sims) | 9% | **Out of scope v0** — persistent timeline gap |
| IF (Zork) | ~0% | **Out of scope indefinitely** — use Inform 7 |
| Racing (F-Zero-like) | — | **Out of scope v0** — v2 candidate |
| Text-adventure-adjacent (Monkey Island) | — | **In scope v0.2.2** — adventure subset |

**v0 targets:** action-oriented real-time games. Anything where the
player moves a protagonist through a spatial world, fights/collects/
solves. Frequency data supports 30–40% coverage rising to ≥ 60% with
v0.2.2 additions (prediction, not measurement).

**v0 does not target:** long-horizon sims, JRPG-style battle-overlay
games, pure IF. Each is a known limit with a named mechanism for
eventual extension (F1–F3 flagged in attempt_005, plus the
BattleSystem sub-schema in v0.3).

This is the honest read. Document it; don't sell past it.

## Promotion gate — v0.2.2

Attempt_005 set: **60% expressible-or-caveated on 100-prompt coverage
sweep against v0.2.x = promote to v1.0**, ≤ 60% = mandatory v0.3.

Refinement: the 60% gate applies to **in-scope genres only** (see
boundary table above). Measuring v0 against Zork is measuring the
wrong thing — the method doesn't target it.

Revised: **60% expressible-or-caveated on prompts tagged `in_scope`
(everything except JRPG / pure-IF / racing / pure-sim).** Out-of-scope
prompts don't count toward or against the gate.

Numerics adjustment: when tagging a prompt `impossible`, also tag it
`out_of_scope` vs `in_scope_revisit` so the gate reflects the
addressable question.

## Acknowledging Ether under-sampling

Numerics status.md flagged: "Ether (external primary sources) not yet
sampled." Valid critique per Sigma Three-Source Triangulation. What's
missing:

- **PuzzleScript rule DSL** — the exact syntax for rewrite rules. v0.2
  example_params sketches `'[player][box][empty]' → '[empty][player][box]'`
  but without reading PuzzleScript's actual grammar it's approximation.
- **Godot scene tree + signal model** — how they structure cross-node
  messaging. Relevant to my `mechanic exposes → mechanic consumes`
  field-publish model.
- **Bevy plugin composition** — how plugins declare dependencies. v0.2
  has `requires` on MechanicInstance; Bevy's approach may have better
  primitives (system sets, ordering labels).
- **Inform 7** — the verb × noun × noun phrase grammar. If I'm
  declining IF, I should at least understand what's being declined,
  and confirm the adventure subset is actually distinct enough.

None of these block v0.2.2 promotion. All four are **attempt_007
candidates** — a deliberate Ether pass before I freeze v1.0 schema.

## Back to numerics — updated asks

Status.md said batch 3 will target Monkey Island, Beatmania, Gran
Turismo, Madden, The Sims (done — game 015), StarCraft, Metal Gear,
Resident Evil, Phantasy Star, Sonic. Good.

Three refined asks:

1. **Re-test prompts 001–005 + 011, 015 against v0.2.2.** Expected:
   Sokoban (001) flips to `expressible` with grid mode. Tetris (002)
   flips to `expressible` with FallingPieceMechanic + LineClearMechanic.
   Monkey Island (011) flips from `partially-impossible` to `caveated`
   with the adventure subset. THPS (015) — validate the two variant
   params cover the forced workarounds.

2. **Tag each existing prompt with `in_scope` / `out_of_scope` / 
   `revisit` per the boundary table.** Zork goes `out_of_scope`;
   racing (010) goes `out_of_scope:v2`; farming sim (007) goes
   `out_of_scope:v3_persistent_timeline`; JRPG (not yet in Track A)
   will go `out_of_scope:v3_battlesystem`. This lets the 60% gate
   compute honestly.

3. **Continue batch 3** as planned; tag v0.3 candidates as emerged.
   Monkey Island is the one existing prompt that should benefit
   dramatically from v0.2.2.

## Reference stubs (holding one more iteration)

Still not touching `reference/schema.ts` / `catalog.ts` until the v0.2
retest data comes back. Convergence is strong but the retest is the
last gate before porting. If the retest confirms expressibility gains,
attempt_007 updates the reference stubs + engine port starts. If the
retest surfaces new structural issues, v0.3 first.

## Open questions — status

- (4) Mutation operators for QA — still open. Attempt_007 candidate
  after reference update.
- (7) Mechanic arbitration (two mechanics writing same field) — still
  open. Must be specced before compiler lands. Attempt_007 candidate.
- (NEW — 9) Ether pass (PuzzleScript / Godot / Bevy / Inform 7) —
  attempt_007 candidate.
