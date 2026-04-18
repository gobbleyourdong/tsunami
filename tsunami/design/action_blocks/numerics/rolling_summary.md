# Numerics — Rolling Summary

> Updated every ~10 entries. Distills the gap map so the design instance can
> read latest state without paging through every numbered attempt.
> Last update: after batch 1 (5 coverage prompts + 5 retro games).

## Entries so far

**Track A — coverage sweep** (genre tests against v0 catalog):
- 001 Sokoban, 002 Tetris, 003 Pac-Man, 004 Super Mario platformer, 005 Street Fighter II

**Track B — retro priors** (mechanics enumeration from shipped games):
- 001 Super Mario Bros, 002 Tetris, 003 Pac-Man, 004 Street Fighter II, 005 Zelda LTTP

## Verdict distribution (Track A, n=5)

| Verdict | Count |
|---|---|
| expressible (clean) | 0 |
| expressible with caveats | 1 (Pac-Man) |
| awkward | 3 (Sokoban, Mario, Tetris) |
| expressible but incomplete | 1 (SF2) |
| impossible without v1 | partial (Tetris mechanic-IS-game case) |

**Reading:** v0 catalog handles 0/5 cleanly. Every genre in this batch surfaces
≥ 2 structural gaps. This is the gap-map signal we wanted — not a calibration
failure, it's the measurement.

## Coverage-of-shipped-games (Track B, n=5)

Ratio of mechanics present in game that ARE covered by v0:

| Game | Covered / Total | % |
|---|---|---|
| Super Mario Bros | 3/12 | 25% |
| Tetris | 3/10 | 30% |
| Pac-Man | 4/10 | 40% |
| Street Fighter II | 3/11 | 27% |
| Zelda LTTP | 4/13 | 31% |

**Mean coverage:** ~31%. v0 covers roughly one-third of shipped-game mechanics.
Not a failure — v0 is 15 mechanics, these games have 10–13 each. But the
uncovered 69% is where the gap map lives.

## Gap map — v1 candidates by frequency

Rank by how many entries named each candidate (5 prompts + 5 games = 10 sources):

| Rank | v1 candidate | Sources | Notes |
|---|---|---|---|
| 1 | `LevelSequence` | 4 (Sokoban, Mario, Pac-Man, Zelda) | progression through authored levels; v0 `flow` is too coarse |
| 2 | `GridController` / `GridPlayfield` | 3 (Sokoban, Tetris, Pac-Man) | entire puzzle + arcade grid-genre depends on this |
| 3 | Directional triggers / hit-side | 3 (Mario stomp, Zelda sword, SF2 block-vs-hit) | contact semantics beyond symmetric |
| 4 | `TimedStateModifier` | 3 (Pac-Man power pellet, SF2 stun, Zelda invuln) | temporary state flips are everywhere |
| 5 | Custom BT library authoring | 2 (Pac-Man, Zelda) | `ai:"chase"` ceiling hit fast; need per-enemy BTs |
| 6 | `PlatformerController` | 2 (Mario, partial Zelda) | jump physics are their own genre |
| 7 | `CameraFollow` | 2 (Mario, Zelda) | scrolling camera; v0 is scene-fixed |
| 8 | Round/Room/Level graph | 3 (SF2 rounds, Zelda rooms, any multi-level game) | sub-scene sequencing |
| 9 | `FallingPieceMechanic` + `LineClearMechanic` | 1 (Tetris) but genre-defining | Tetris-clone impossible without |
| 10 | `AttackFrames` / frame data | 1 (SF2) but genre-defining | fighting game collapses without |
| 11 | `ItemUse` action blocks + `GatedTrigger` | 1 (Zelda) but core loop | item-gated progression |
| 12 | `Shop`, `DialogTree`, `MaxHealthIncrement`, `RoomGraph`, `ParallelWorldLayer`, `Resource` (generic), `Hitbox`/`Hurtbox`, `RandomBagGenerator` | 1 each | less frequent; v2 candidates |

## Structural gaps in v0 (not per-mechanic)

These are not additional mechanics, they're shape-of-schema issues:

1. **Grid/discrete motion is absent.** v0 assumes continuous motion. An entire
   genre family (puzzle, strategy, roguelike, sokoban, chess) needs grid-first
   thinking. Adding a `GridPlayfield` archetype kind + `GridController` is
   bigger than a single mechanic — it's a second schema mode.

2. **Scene vs. level vs. room granularity.** v0 `flow` is scene-level (title
   → game → gameover). Games mostly have three granularities: scene (menus),
   level (Mario 1-1 → 1-2), room (Zelda room-to-room). Need nested
   sequencing.

3. **Directional contact.** `trigger:"damage"` is symmetric. Mario stomp,
   Zelda sword swing, SF2 high/low/block — all need contact-side semantics.
   A real schema fix, not a mechanic addition.

4. **Mechanic publishes field, other mechanic consumes.** Attempt_003 introduced
   `ctx.publishField` for HUD → `waves.wave_index`. Every game in Track B
   uses this pattern more than v0 spec'd (e.g., TimedStateModifier needs to
   expose `active` flag to all AI behaviors). Promote to first-class.

5. **Singleton logic containers.** Tetris playfield, Zelda inventory, SF2
   round manager — not archetype-per-entity, they're game-global state. v0
   doesn't have a "singleton" archetype kind.

## v0 mechanics that validated (kept)

These showed up consistently across the corpus, no major revision needed:
- `PickupLoop`, `HUD`, `LoseOnZero`, `WinOnCount`, `Difficulty`, `ScoreCombos`, `LockAndKey`.

## v0 mechanics that need clarification or revision

- `CheckpointProgression` — semantics: respawn-in-place vs. reset-scene? Param needed.
- `StateMachineMechanic` — every game uses state machines; v0 under-specifies. Probably needs sub-catalog of canonical states (idle/move/attack/stun/ko/spawn/die).
- `TileRewriteMechanic` — placeholder. Either concretize the rule DSL or absorb into `GridController`.

## v0 mechanics not yet exercised

- `BossPhases`, `RhythmTrack`, `DayNightClock`, `ComboAttacks` (partially). Schedule for later prompts.

## What the data says for attempt_004 (handoff to design instance)

1. **Add a grid mode.** `GridPlayfield` + `GridController` + optional
   `FallingPieceMechanic`, `LineClearMechanic` is the single biggest coverage
   gain. Probably unlocks 25+% of retro-game coverage by itself.
2. **Promote `LevelSequence` into v1.** 4/5 games want it.
3. **Rework directional collision at the schema layer,** not as a mechanic.
4. **Custom BT authoring is needed by v1.** Generic `ai:"chase"` is
   insufficient for any game with >1 enemy type.
5. **Nested flow (scene/level/room).** v0 flow is one-level; real games
   have three.

## Pacing note

Batch 1 = 10 entries total (5+5). Target for batch 2: +10 more (Zork-like IF,
farming sim, roguelike grid, rhythm-action, racing sim + Galaga, Ms. Pac-Man,
SimCity, Metroid, Chrono Trigger). Planned 100-entry total for full coverage;
current rate is ~10 per fire.
