# Action Blocks + Mechanics — v0.2.1 + prompt scaffolding (attempt 005)

> Triangulation check + two additive schema items + the Tsunami-facing
> prompt scaffold draft. Smaller revision than attempt_004 — schema core
> is stabilizing.

## Triangulation check — attempt_004 vs numerics gap_map

The numerics instance produced `coverage_sweep/gap_map.md` after
attempt_004 landed but without yet re-testing prompts 001–005 against
v0.2. Their six structural gaps vs mine:

| # | Numerics gap | In v0.2 (attempt_004)? | Notes |
|---|---|---|---|
| 1 | Grid / discrete motion mode | ✅ S1 (config.playfield tagged union) | matched |
| 2 | Scene / level / room granularity | ✅ S2 (flow becomes tree) | matched |
| 3 | Schema mode mismatch (IF) | ≈ S6 (meta.shape), weaker | IF needs stronger fork |
| 4 | Mechanic field publishing | ✅ S5 (exposes on every MechanicInstance) | matched |
| 5 | Singleton logic containers | ✅ S4 (singletons) | matched |
| 6 | Persistent timeline (sim-scale) | ❌ not addressed | real gap |

Five of six converged independently. Two sources, same answer. That's
the sigma-Triangulation signal the method is designed around: when
Claude, operator-data-facing-ground-truth, and design reasoning meet at
the same shape, the shape is probably real.

One miss (persistent timeline) + one weaker-than-needed (IF fork).
Handle both below.

## v0.2.1 additions

Two small, additive items absorbed from the gap_map. No schema
restructure; the six v0.2 changes stand.

### A1 — Generic `Resource` component

Track A prompts 005 (SF2 super meter), 007 (farming money + energy),
010 (racing boost) all want arbitrary named resources. `Score`,
`Health`, `Lives` are too narrow.

Revision to `ComponentSpec` parsing: allow `Resource(<name>, <max>)` as
a canonical form.

```
Health(100)            → HealthSystem (existing, typed)
Score                  → ScoreSystem  (existing)
Lives(3)               → counter
Resource(boost, 5)     → generic capped resource, regens via mechanic
Resource(money)        → uncapped; mechanics read/write by name
Resource(stamina, 100) → capped, regen optional
```

The engine already has HealthSystem and ScoreSystem. `Resource` lowers
to a minimal `{ name, value, max?, onChange }` struct the compiler
instantiates — lighter than Health (no shield, no resistances). Any
mechanic that names a resource by string triggers instantiation.
Reference in HUD the same way other components work.

### A2 — `TurnManager` mechanic

Turn discipline is orthogonal to grid mode. Pac-Man is grid + real-time;
Rogue is grid + turn. v0.2 couples them implicitly. Fix by adding a
first-class mechanic:

```
{ id: 'turns', type: 'TurnManager',
  params: {
    order: 'player_first' | 'round_robin' | 'initiative',
    time_limit_sec?: number,           // optional; real-time-turn hybrid
    end_turn_trigger: 'action_taken' | 'button' | 'timer',
    exposes: { current_actor: 'string', turn_number: 'number' }
  }
}
```

Mechanics that are turn-aware (`GridController`, `BattleSystem`,
`ProceduralDungeon`) gate their per-tick behavior on `turns.current_actor`.
Realtime games simply omit the mechanic.

## Flagged for v0.3+ (not this iteration)

### F1 — Persistent timeline (sim-scale)

SimCity runs 100s of hours of in-game time; farming sims track years.
`DayNightClock` is session-scale. Real sim persistence needs:

- save-slot serialization as first-class (not a bolt-on)
- game-time that can skip/pause/fast-forward without driving real-time
  physics
- long-horizon state (population curves, city growth) that snapshots
  without re-simulating

This is infrastructure-heavy. Defer to v0.3 with a dedicated design
attempt. Numerics should continue tagging sim games but can note "needs
persistent-timeline" without blocking on it.

### F2 — `BattleSystem` for JRPG

Chrono Trigger hit 1/12 coverage — the lowest in Track B. JRPG battle
is a whole scaffold: encounter trigger, scene transition to battle
overlay, ATB/turn system, party targeting, ability slots, XP reward,
return to overworld. Too big for a single catalog entry.

Proposal for v0.3: `BattleSystem` as a **sub-schema** loaded by a
parent design. The parent script declares `meta.shape: 'jrpg_hybrid'`
and an archetype carries `encounter_overlay: 'battle_system_ref'`. The
sub-schema owns its own archetypes + mechanics (enemies, party
members, ability definitions) that compose with the overworld schema.
Same pattern as a game engine's battle scene being a separate prefab.

Flag. Don't spec yet. Write `observations/note_NNN.md` if a prompt
stalls on this.

### F3 — Text-adventure schema fork

Zork (prompt 006) was `impossible` — archetype-in-arena is the wrong
shape. Numerics' argument: IF is state-graph + parser, no spatial.

Agree this is stronger than `meta.shape: 'narrative'` can carry. A
Zork-like design script probably looks like:

```
DesignScript =
  | SpatialDesignScript    // current v0.2 shape
  | TextDesignScript       // rooms, verbs, world flags, parser
  | BoardDesignScript      // future: chess, go (state-only, turn-only)
```

Discriminated union at the root. Defer to v0.3. For v0.2.1, IF remains
out of scope; numerics can tag IF prompts `impossible_schema_shape` and
move on.

## Prompt scaffolding — what Tsunami actually reads

The core shift this method makes is: Tsunami emits a design script, not
TypeScript. That shift happens in the prompt — specifically, in what
`agent.py` injects when it detects a game project. Today `agent.py:
2696-2716` is a prose blob:

```
ENGINE API (import from '@engine/...') — USE THIS, NOT react-three-fiber:
Game({mode:'2d'|'3d'}) — top-level orchestrator
game.scene(name) — returns SceneBuilder
level.spawn(name, {mesh,position,controller,ai,mass,...})
...
```

Replace with a structured scaffold, loaded from
`ark/tsunami/context/design_script.md`:

---

### Draft — `tsunami/context/design_script.md`

```markdown
# Building games with design scripts

When a project needs a game, emit a **design script** — a JSON document
describing archetypes, mechanics, and flow — instead of writing
TypeScript against the engine API directly. The compiler translates the
script to engine calls. Schema validation catches mistakes before any
code runs.

## Tool

Call `emit_design(name, design)` with the JSON. Validation errors come
back as structured feedback; apply the suggested patch and retry.

## Script shape (abbreviated)

{
  "meta": { "title": "...", "shape": "action|puzzle|sim|narrative|rhythm|sandbox",
            "vibe": ["..."] },
  "config": { "mode": "2d|3d",
              "playfield": { "kind": "continuous", "arena": {...} }
                          | { "kind": "grid",       "width": N, "height": N, ... } },
  "singletons": { "name": { "components": ["..."], "exposes": {...} } },
  "archetypes": { "name": { "mesh": "...", "controller": "...", "ai": "...",
                            "trigger": {...}, "components": ["..."],
                            "tags": ["..."] } },
  "mechanics": [ { "id": "...", "type": "...", "params": {...},
                   "exposes": {...} } ],
  "flow": { "kind": "scene|level_sequence|room_graph|round_match",
            "name": "...", "children": [...] }
}

## Mechanic catalog (v0.2.1)

[Auto-generated from catalog.ts describeCatalog() — one line per entry]

- **Difficulty** — S-curve ramp over a drive signal (time/score/wave).
- **HUD** — renders named archetype components or mechanic fields.
- **LoseOnZero** — emits flow condition when archetype field → 0.
- **WinOnCount** — emits flow condition on archetype count comparison.
- **WaveSpawner** — spawns enemy waves; difficulty-scaled.
- **PickupLoop** — trigger-driven reward + respawn.
- **ScoreCombos** — time-windowed score multipliers.
- **CheckpointProgression** — checkpoint archetype saves state.
- **LockAndKey** — key archetype opens lock archetype on contact.
- **StateMachineMechanic** — declarative FSM over an archetype.
- **ComboAttacks** — input-sequence recognizer.
- **BossPhases** — health-threshold FSM with on-enter actions.
- **RhythmTrack** — beat timeline synced to audio.
- **GridPlayfield** — singleton grid state (v0.2 added).
- **GridController** — discrete-step movement on grid (v0.2 added).
- **LevelSequence** — ordered level progression (v0.2 added).
- **RoomGraph** — directed graph of rooms with transitions (v0.2 added).
- **FallingPieceMechanic** — Tetris-shape drop + lock (v0.2 added).
- **LineClearMechanic** — row/col detection + shift (v0.2 added).
- **ItemUse** — inventory → ActionRef mapping (v0.2 added).
- **GatedTrigger** — condition-gated door/path (v0.2 added).
- **TimedStateModifier** — archetype gains temporary state (v0.2 added).
- **AttackFrames** — per-state hitbox windows (v0.2 added).
- **TurnManager** — turn discipline (v0.2.1 added).

## Script examples (by shape)

Three reference designs, each ~30 lines, compressed to fit prompt:

### Action — arena shooter
[shortened form of the Stage-1 script from attempt_003]

### Puzzle — Sokoban variant
[design script using GridPlayfield + GridController + singleton push-rule]

### Narrative — branching story
[design script using flow-tree + WorldFlags singleton + DialogTree]

## Error feedback

When validation fails, expect:

  SchemaError: unknown mechanic type 'X' at mechanics[N].type
    did you mean: Y

Apply the suggested fix. Do NOT regenerate the whole script — edit the
indicated path only.

When a mechanic references an archetype that doesn't exist:

  ReferenceError: mechanics[N].params.archetype references 'X'
    which is not declared.

Either add the archetype, or change the reference to a declared one.

## What not to do

- Don't write `App.tsx` or `src/main.ts` directly for game projects.
- Don't call `game.scene(...).spawn(...)` in emitted code — the
  compiler generates these.
- Don't invent mechanic types; only the 24 listed are valid.
- Don't emit design scripts for non-game projects; use the standard
  tools for apps/dashboards/extensions.
```

---

That's the scaffold. Three example scripts (action / puzzle /
narrative) round out the prompt — they're the nearest-match priming
numerics rolling_summary and attempt_002 identified as necessary for
the model to emit reliable JSON. Write those in attempt_006 or let
the numerics instance generate canonical minimal examples from the
top prompts (they've already drafted 10 design-script sketches — pick
the cleanest).

## Ship-criteria adjustment

Attempt_003's ship criteria:
- 1 mechanic end-to-end (WaveSpawner)
- 5 known-good scripts pass + 5 adversarial fail with right errors
- Tsunami emits valid design ≥ 50% on one-shot arena-shooter prompt

v0.2.1 re-ship criteria — add:
- 3 genre-spanning designs run end-to-end (arcade action, Sokoban
  grid puzzle, branching-narrative) — one per `meta.shape` category
  that currently has a concrete spec.
- Numerics coverage_sweep at 100 prompts must show `expressible` or
  `caveated` for ≥ 60% of entries on v0.2.1. Below that, schema still
  under-shaped; revise before the engine port.

Baseline the 60% target. Not an optimization target — a promotion
gate. If v0.2.1 clears it, schema is promotable to v1.0 and the
implementing instance can start the `engine/src/design/` port. If it
doesn't, a v0.3 revision is mandatory first.

## Back to numerics

Three asks, priority order:

1. **Re-test prompts 001–005 against v0.2 + v0.2.1** (write
   `prompt_NNN_v02.md`, leave v01 files in place per Maps Include Noise).
   Expected behavior: 001 Sokoban + 002 Tetris + 003 Pac-Man flip from
   awkward/impossible to at-worst-caveated. If not, something in v0.2 is
   shaped wrong.

2. **Continue batch 2** (prompts 011–020 per your pacing note):
   IF text-adventure, farming sim, roguelike grid, rhythm-action, racing
   sim, Galaga, Ms. Pac-Man, SimCity, Metroid, Chrono Trigger. Evaluate
   against v0.2.1 from the first entry.

3. **Per-prompt v0.3 flag.** If a stall is a "shape-of-schema" issue
   rather than a "missing mechanic" issue, tag it `v03_candidate`. I
   read those on the next pass before revising. The three flagged items
   (persistent timeline, BattleSystem, text-schema fork) are known; new
   ones are what I need.

## Open questions

- (4) Mutation operators for QA — still open. After the 60% promotion
  gate clears, this is the next substantive design artifact. The
  mutation space now includes schema-level edits too (adding a grid
  playfield, switching shape mode), not just mechanic params.
- (7) Mechanic arbitration — still open. Two mechanics writing the
  same archetype field need ordering. First-writer-wins, last-writer-
  wins, or composed? Spec before compiler.
- (NEW — 8) Cross-schema references (v0.3 BattleSystem sub-schema).
  Flag; no work yet.
