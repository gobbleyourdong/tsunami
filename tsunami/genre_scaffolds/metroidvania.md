---
applies_to: [gamedev]
mood: discovery-driven, labyrinthine, ability-gated, backtrack-rewarding
corpus_share: 8
default_mode: dark
anchors: super_metroid, castlevania_sotn, metroid_prime
default_mechanics: [RoomGraph, LockAndKey, ItemUse, CameraFollow, HUD, PhysicsModifier]
recommended_mechanics: [CheckpointProgression, BossPhases, StateMachineMechanic, PickupLoop, GatedTrigger, AttackFrames]
would_falsify: if a metroidvania delivery tagged with this genre ships with purely linear level progression (no backtracking through previously-visited rooms with new abilities) OR omits ability-gated room gating, the genre directive was ignored — measured via mechanic adoption probe on RoomGraph + GatedTrigger presence AND map-revisit telemetry in runtime logs
---

## Pitch

A single interconnected map navigated via abilities acquired through
exploration. The core verb is EXPLORE — and re-explore, once new
movement abilities unlock previously-inaccessible paths. Super Metroid
1994 defines the 2D template; Castlevania: Symphony of the Night 1997
adds RPG layering; Metroid Prime 2002 extends to first-person 3D.
Distinct from `action_adventure` in that the ENTIRE game is one
contiguous map, not discrete chapters.

## Mechanic set (anchor examples)

1. `RoomGraph` — a single large, interconnected map (not episodic).
2. `LockAndKey` — doors gated by abilities, not just keys.
3. `ItemUse` — morph ball, high jump, grappling beam, bombs.
4. `GatedTrigger` — permanent world-state flags per ability unlock.
5. `PhysicsModifier` — movement abilities (wall-jump, double-jump,
   space-jump) feel different; physics tuning per-state.
6. `CameraFollow` — scrolls through rooms seamlessly; side-scroll
   2D or free-look 3D depending on sub-family.
7. `CheckpointProgression` — save rooms restore HP, mark progress.
8. `BossPhases` — area bosses drop the KEY ability that gates the
   next region.
9. `AttackFrames` — weapon / beam systems with charge-window timing.
10. `PickupLoop` — missile expansion tanks, energy tanks, reserve
    tanks scattered as exploration rewards.

## Common shape

- **Map size**: 60-200 rooms in one contiguous world. Zones visually
  distinct (tourian, maridia, norfair) but all reachable from one graph.
- **Ability count**: 6-12 traversal abilities, acquired in rough order
  (e.g., morph ball → bombs → high jump → space jump → screw attack).
- **Fail state**: HP=0 → respawn at last save room; minimal progress loss.
- **Progression curve**: 100% completion encourages re-visiting every
  area with every new ability. The map itself IS the skill tree.

## Non-goals

- NOT a platformer (use `platformer` — linear level list, no backtracking).
- NOT an action-adventure (use `action_adventure` — episodic dungeons,
  scene-graph per chapter rather than single connected world).
- NOT a roguelike (use `roguelike` — procedural regen, death penalty).
- NOT an RPG (use `jrpg` — turn-based combat + party).

## Anchor essences

`scaffolds/.claude/game_essence/1994_super_metroid.md` —
**canonical 2D metroidvania**. The mechanic set coined here.

`scaffolds/.claude/game_essence/1997_castlevania_symphony_of_night.md`
— metroidvania + RPG hybrid. Adds `LevelUpProgression`, equipment,
spells. Use when prompt says "Castlevania-like" or "igavania."

`scaffolds/.claude/game_essence/2002_metroid_prime.md` — 3D
metroidvania in first-person. ScanLorebook, DiegeticVisorHUD,
TransformMode (morph ball in 3D).

## Pitfalls the directive is trying to prevent

- Wave treats the world as a linear list of levels — metroidvania's
  identity is the SINGLE connected graph. If the output has a level
  select screen, it's not a metroidvania.
- Wave implements door-locks but forgets that doors are gated by
  ABILITIES (player can't pass wall-jump door without wall-jump
  item), not generic keys. `GatedTrigger` with ability-id checks is
  the right pattern.
- Wave makes the whole map visible from start — metroidvania
  REQUIRES map-reveal-on-visit (`HUD` with fog-of-war-style minimap).
