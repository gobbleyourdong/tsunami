---
applies_to: [gamedev]
mood: exploratory, deliberate, progression-gated discovery
corpus_share: 12
default_mode: dark
anchors: legend_of_zelda, ocarina_of_time, ico, shadow_of_colossus
default_mechanics: [RoomGraph, LockAndKey, ItemUse, CameraFollow, HUD, ComboAttacks]
recommended_mechanics: [DialogTree, PuzzleObject, BossPhases, CheckpointProgression, GatedTrigger]
would_falsify: if an action-adventure delivery tagged with this genre ships without RoomGraph or equivalent scene-graph progression, or delivers as a single-screen arcade loop, the genre directive was ignored — measured via mechanic adoption probe (F-B1) and RoomGraph import presence
---

## Pitch

Single-screen-at-a-time top-down or third-person exploration through a
connected scene graph. The core verb is DISCOVER. Enemies gate rooms;
items unlock passages; bosses end chapters. Puzzle-solve and combat
alternate but neither dominates. Think Zelda 1986 overworld, OoT 1998,
ICO 2001.

## Mechanic set (anchor examples)

1. `RoomGraph` — scene-to-scene navigation with gated transitions.
2. `LockAndKey` — keys/items unlock specific rooms or progression.
3. `ItemUse` — player inventory with context-sensitive activation.
4. `ComboAttacks` — short-window chain inputs for combat variety.
5. `CameraFollow` — player-anchored camera, no free-look.
6. `HUD` — Hearts / Inventory / Map.
7. `DialogTree` — NPC conversation, quest-hint delivery.
8. `PuzzleObject` — environmental puzzle (block-push, switch-wire).
9. `BossPhases` — chapter-ending encounter with 2-4 phases.
10. `GatedTrigger` — progression flags (dungeon cleared, item acquired).

## Common shape

- **Scene count**: 6-20 rooms/zones. One overworld hub + 1-3 dungeons minimum.
- **Fail state**: on HP=0, respawn at last checkpoint or entry.
- **Progression curve**: each chapter unlocks 1-2 new mechanics (bomb,
  hookshot, swim suit). The final boss requires mastery of all.
- **Control**: d-pad / WASD movement, A = attack, B = item, select = map.

## Non-goals

- NOT a side-scrolling platformer (use `platformer` genre — discrete
  jump-physics).
- NOT an open-world sandbox (use `open_world` — too large for pre-2003
  action-adventure).
- NOT a stealth game (use `stealth` — VisionCone-driven AI dominates there).
- NOT a JRPG (use `jrpg` — turn-based combat, party composition).

## Anchor essences

`scaffolds/.claude/game_essence/1986_legend_of_zelda.md` —
**canonical reference, carries the Content Catalog** (Octorok, Moblin,
Aquamentus, etc.). For a "Zelda-like" prompt, F-I3 content injection
fires on top of this genre directive.

`scaffolds/.claude/game_essence/1998_ocarina_of_time.md` — 3D
extension; ZTargeting adds combat depth. Use when prompt says "3D
Zelda" or names OoT explicitly.

`scaffolds/.claude/game_essence/2001_ico.md` — minimalist
companion-NPC variant. DiegeticHUD, EscortFailState dominate.

## Pitfalls the directive is trying to prevent

- Wave defaults to a 2D platformer template when given "zelda-like" —
  action-adventure is TOP-DOWN by default in 2D, third-person in 3D,
  not side-scrolling.
- Wave re-invents inventory as React state when `ItemUse` +
  `InventoryCombine` from the engine catalog cover it.
- Wave ships one-screen arcade demo — action-adventure REQUIRES at
  least a 2-room RoomGraph to be recognizable.
