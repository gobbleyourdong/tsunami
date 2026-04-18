# Coverage sweep — gap map

> Aggregate over `prompt_NNN.md`. Rebuilt every ~10 prompts.
> Last rebuild: after prompt_030. Source count: **30 prompts**.

## Verdict distribution (n=30)

| Verdict | Count | Prompts |
|---|---|---|
| expressible (clean) | 0 | — |
| expressible with caveats | 4 | 003, 009, 015, 018 |
| expressible but incomplete | 2 | 005 SF2, 024 Roguelite |
| awkward | 15 | 001, 004, 007, 010, 011, 013, 014, 019, 020, 022, 023, 025, 027, 029, 030 |
| awkward → impossible without v1 | 2 | 002 Tetris, 008 Roguelike |
| impossible | 7 | 006 Zork, 012 StarCraft, 016 FE Tactics, 017 Deckbuilder, 021 Madden, 026 MMO, 028 Western CRPG |

Clean still 0. All 7 impossibles violate ≥ 1 of note_005's four
assumptions (after note_005_addendum). Out-of-v1-scope set is stable.

## Genre reach snapshot

| Reachable with v0 | Reachable with v0 + top-5 v1 | Out-of-v1 scope |
|---|---|---|
| arcade, rhythm-lite, skater | roguelite, light-gun, sim-puzzle, VN via dialogue subset, dating sim, TD, adventure-puzzle, arcade sports, stealth-lite, survival-lite, THPS-variants, RhythmTrack-content games | RTS, MMO, IF, TBS, Western CRPG, team-sports sim, deep roguelike |

v0+top-5 unlocks ~65% of the corpus by estimate. Out-of-scope set is
7 genres — consistent with note_005's "violates ≥ 2 assumptions" rule.

## Top v1 candidates (frequency × composability × content-multiplier)

Per note_007 (composability) and note_009 (content-multiplier).
Sources out of 30 prompts, ranked by *composite leverage*, not raw count:

| Rank | v1 candidate | Frequency | Notes |
|---|---|---|---|
| 1 | `Resource` (generic) | 10 | composes with Shop/Difficulty/HUD, enables N mechanics |
| 2 | `WorldFlags` + `DialogTree` + `DialogScript` | 10 | **content-multiplier** (note_009) — VN/narrative-RPG/adventure |
| 3 | `EmbeddedMinigame` (note_006) | 6 | turns any mechanic into sidequest |
| 4 | Grid-mode bundle (note_002, note_008 correction) | 6 | grid-puzzle + roguelike + tactics + Civ |
| 5 | `DirectionalContact` schema revision (note_003) | 8 | platformer/fighter/stealth/horror |
| 6 | `LevelSequence` | 8 | ubiquitous linear flow |
| 7 | `CameraPresets` / `CameraFollow` | 7 | ubiquitous |
| 8 | `RhythmTrack` (concretize) | 2 explicit + 4 adjacent | **content-multiplier** — huge per-investment payoff |
| 9 | `InventoryCombine` + slot-limit | 6 | adventure/horror/RPG |
| 10 | `TimedStateModifier` | 7 | frequent, standalone |
| 11 | `ArchetypeControllerSwap` | 3 | vehicle entry, mount, mech suit |
| 12 | `ItemUse` + `GatedTrigger` | 5 | adventure/metroidvania |
| 13 | `Shop` + cost-function | 5 | common |
| 14 | `PlatformerController` | 5 | platformer genre |
| 15 | `HotspotMechanic` / `PointerController` | 6 | adventure/clicker/light-gun |
| 16 | `Calendar` (date-indexed Difficulty) | 2 | dating sim / stat-sim |
| 17 | `SandboxMode` flag (note_004) | 3 | open-ended genres |
| 18 | `AuthorRunMode` flag | 2 | sim puzzle, Tower Defense, Lemmings |
| 19 | `PuzzleObject` (mutable world object) | 3 | puzzle-adventure |
| 20 | `BulletPattern` + `AutoScroll` + `ProximityTrigger` | 2 | shmup bundle |
| 21 | `EndingBranches` | 4 | narrative finish |
| 22 | `VisionCone` + `AlertState` + `CarryRelationship` | 2 | stealth |
| 23 | `StatusStack` (stackable decayable) | 2 | deckbuilder/RPG |
| 24 | `TowerPlacement` + `AutoTurretAttack` + `LoseOnCount` | 1 | TD bundle |
| 25 | `VehicleController` (arcade) + `LapCounter` + `TrackSpline` + `WaypointAI` | 2 | kart/arcade-racing (not sim) |
| 26 | `RubberBanding` + `WeightedRandomReward` | 1 | Mario Kart feel |
| 27 | `ReloadAction` + `AimCursor` + `CameraRailPath` + `CoverHold` | 1 | light-gun bundle |
| 28 | `TimeReverseMechanic` / `PhysicsModifier` | 1 | puzzle-platformer |
| 29 | `RoleAssignment` | 1 | Lemmings/Pikmin |
| 30 | `StreakMode` (event-condition buff) | 1 | NBA Jam fire mode; generalizes |
| 31 | `GameplayDial` — player-tuned modifier | 1 | Oregon Trail / FTL pace |
| 32 | `PolaritySwitch` / `AttributeState` × contact table | 1 | Ikaruga-pattern |
| 33 | BT library / stochastic BT / custom AI | 5 | ceiling |

## Structural gaps (from per-entry notes)

1. Grid / discrete mode (note_002, note_008)
2. Scene/level/room granularity (nested flow)
3. Spatial vs. state-graph schema split (note_001, note_005)
4. Mechanic-field-publishing (`exposes`)
5. Singleton logic containers
6. Persistent timeline / meta-progression
7. Sandbox / no-fail mode (note_004)
8. Directional-contact at trigger (note_003)
9. Embedded mini-game lifecycle (note_006)
10. Multi-condition flow with boolean composition (Civ multiple wins)
11. Transient controller swap (`ArchetypeControllerSwap`)
12. Persistence scope attribute (run vs meta)
13. Author-vs-run mode split (sim puzzle, TD, Lemmings)
14. Single-session-local assumption (note_005_addendum) — multiplayer out-of-scope
15. Real-time-with-pause time mode (prompt_028 CRPG)

## v0 mechanics validated, thin, or revised

**Validated (keep):** HUD, PickupLoop, Difficulty, LoseOnZero, WinOnCount,
ScoreCombos, LockAndKey, CheckpointProgression, ComboAttacks, WaveSpawner,
BossPhases, StateMachineMechanic.

**Thin support but retained:** DayNightClock, RhythmTrack (concretize),
TileRewriteMechanic (upgrade post-grid-mode).

**Needs revision:** RhythmTrack (grades/hooks/variants), TileRewriteMechanic
(rule DSL), StateMachineMechanic (condition sub-language), ComboAttacks
(gated_by flag), PickupLoop (respawn:'never' variant).

## Design-track recommendation (composite leverage)

Top-5 v1 unchanged from n=25:

1. `Resource` (generic)
2. `EmbeddedMinigame` (note_006)
3. Grid-mode bundle (note_002 + note_008)
4. `WorldFlags` + `DialogTree` + concretize `RhythmTrack` (content-multipliers per note_009)
5. `DirectionalContact` schema revision (note_003)

Revision from n=25: **promote `RhythmTrack` concretization** into the
top-5 as a content-multiplier; bundle with `DialogTree` as the
"content-multiplier triad" in slot 4.

Estimated coverage after top-5 + concretize: **65–70%** of the retro
corpus expressible, + single-session non-action genres unlocked.

Seven genres explicitly OUT (RTS, IF, TBS, MMO, team-sports sim, deep
roguelike, western CRPG) per note_005.

Cross-reference `retro_priors/frequency.md` for corpus-side.
