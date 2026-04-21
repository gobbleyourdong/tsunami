# Puzzle Platformer Roguelite — cross-genre scaffold

**Pitch:** Catherine's block-pushing × Celeste's movement × Into-the-Breach's
run structure. Pure composition from `@engine/mechanics`. Architecture canary
for the three-way genre combination.

## Heritage mix (14 mechanics across 4 buckets)

| Heritage    | Mechanics |
|-------------|-----------|
| puzzle      | `PuzzleObject` × per room, `LockAndKey` × per room, `GatedTrigger`, `TimeReverseMechanic` |
| platformer  | `PhysicsModifier` (ice/wind per room), `CameraFollow`, `PickupLoop`, `CheckpointProgression` |
| roguelite   | `ProceduralRoomChain`, `RoomGraph`, `RouteMap`, `Difficulty` (ramps with depth) |
| universal   | `HUD`, `LoseOnZero` |

Three clear heritages, all composed — no new primitives.

## Quick start

```bash
npm install
npm run dev        # localhost:5184
npm run check      # tsc typecheck
```

## Customize

- **Add a room blueprint** → append to `data/rooms.json::room_pool`.
  `ProceduralRoomChain` picks from the pool by `tags` + `difficulty`.
- **Add a relic** → `data/relics.json::relics`. The effect shape is a
  flat dict (`double_jump: true`, `gravity_mul: 0.85`) that the engine
  can dispatch into `PhysicsModifier` / `PickupLoop` / etc.
- **Change chain rule** → `rooms.json::chain.rule`. Options:
  `difficulty_ascending_with_one_shortcut` (default),
  `random_weighted`, `ascending_strict`. Implement in
  `ProceduralRoomChain` when the engine supports the rule; otherwise
  the default plays fine.

## Design notes

- One-hit death is a deliberate Celeste lineage call (`Health(1)` in
  `player.json`). Lives count is `3` — you die, respawn at room entry
  via `CheckpointProgression`; lose all 3 and the `Run` ends via
  `LoseOnZero(Lives)`.
- Puzzle state is NOT persisted across runs. Blocks reset on room entry.
  Relics ARE persisted within a run (roguelite lineage) but reset
  between runs. If you want meta-progression (e.g. unlock a new relic
  pool for future runs), add a second scaffold layer or wire a
  `WorldFlags` mechanic scene-above-the-run.

## Don't

- Don't overload one `PuzzleObject` kind with >2 responsibilities
  (e.g. a "laser_mirror_pressure_plate"). Split into separate objects
  linked by `GatedTrigger`. The engine's puzzle vocabulary stays
  clean when each kind does one thing.
- Don't add an `"endless" run mode` without building a fatigue/damage
  ramp first. `Difficulty` max_level is 4; past that the scene plays
  the same at a higher hazard scalar, which is unfun past 15 minutes.

## Anchors

`Catherine`, `Celeste`, `Inside`, `Braid`, `Meat Boy`, `Into the Breach`,
`Hades` (for the relic-granting-upgrades flow).

## Canary

`scaffolds/engine/tests/puzzle_platformer_roguelite_canary.test.ts` —
validates tree, data shape, scene imports from `@engine/mechanics`
only, every `tryMount()` is in the registry, ≥ 3 heritages represented.
