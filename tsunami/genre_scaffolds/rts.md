---
applies_to: [gamedev]
mood: cerebral, macro-to-micro, resource-anxious, APM-skill
corpus_share: 9
default_mode: dark
anchors: starcraft, command_and_conquer, age_of_empires_ii, warcraft_iii
default_mechanics: [WaveSpawner, HUD, UtilityAI, RoleAssignment, CameraFollow, Shop]
recommended_mechanics: [CrowdSimulation, StateMachineMechanic, RouteMap, GatedTrigger, ScoreCombos, LevelSequence]
would_falsify: if an RTS delivery tagged with this genre ships with single-unit-controls-at-a-time (no group selection / rally / queue commands) OR omits resource harvesting + base-building, the genre directive was ignored — measured via mechanic adoption probe on UtilityAI + RoleAssignment imports AND runtime check for unit-group selection handlers
---

## Pitch

Top-down god-view control of units + economy + base. The core verb is
COMMAND — macro (build order, economy) and micro (unit positioning,
target focus) alternate under time pressure. Dune II 1992 is the
ancestor; Command & Conquer 1995 defines the 2-faction asymmetry;
StarCraft 1998 perfects 3-faction balance; Age of Empires II 1999
adds historical civs; WarCraft III 2002 adds hero units + RPG layer.

## Mechanic set (anchor examples)

1. `UtilityAI` — unit AI picks targets/actions from weighted utility.
2. `RoleAssignment` — workers/soldiers/builders with role-specialized
   behaviors.
3. `CrowdSimulation` — N-unit pathfinding + formation movement.
4. `WaveSpawner` — enemy AI cadence (in missions) or player rallies.
5. `Shop` — unit/tech production from buildings (catalog applies —
   building = "shop" producing units as "stock").
6. `CameraFollow` — edge-pan + minimap click-to-focus; NOT entity-
   anchored.
7. `HUD` — resources, unit counter, minimap, command card.
8. `RouteMap` — minimap reveals scouted areas (fog of war).
9. `StateMachineMechanic` — per-unit state (idle/moving/attacking/
   mining/repairing).
10. `GatedTrigger` — tech-tree requirements (need supply depot for
    barracks, barracks for siege).

## Common shape

- **Unit count**: 50-200 simultaneous units is the genre baseline.
- **Economy loop**: harvester units → resource nodes → storage →
  production buildings → combat units.
- **Mission structure**: campaign scripted levels + skirmish vs. AI +
  multiplayer ladder (for modern RTS).
- **Fail state**: all-production-buildings-destroyed → defeat.
- **Progression curve**: per-mission tech tree gates upgrades; between-
  mission story.
- **Control**: LMB select, RMB action, hotkeys for build orders,
  double-click select-all-of-type, group-bind (Ctrl+1..9).

## Non-goals

- NOT a tactics RPG (use `tactics_rpg` — turn-based grid, small unit
  count).
- NOT a MOBA (use `moba` if it lands — single-unit control, lane-
  based).
- NOT a real-time tactics (use `rtt` — no base-building / economy).
- NOT a 4X (use `4x` — turn-based grand-strategy, not continuous time).
- NOT a city-builder (use `city_builder` — no combat, just growth).

## Anchor essences

`scaffolds/.claude/game_essence/1995_command_conquer.md` —
**modern RTS ancestor**. FMV cutscenes, 2-faction asymmetry, resource-
harvesting loop.

`scaffolds/.claude/game_essence/1998_starcraft.md` —
**canonical 3-faction RTS**. AsymmetricFactions reaches peak here;
OnlineLadder via Battle.net seeded the competitive-RTS era.

`scaffolds/.claude/game_essence/1999_age_of_empires_ii.md` —
historical-civ RTS. Adds civilization-specific tech trees, wonder
victory condition, MultipleVictoryConditions.

## Pitfalls the directive is trying to prevent

- Wave builds single-unit controls (click this unit, then click
  destination) — RTS REQUIRES group-select (box-drag + shift-click +
  ctrl+N bindings). `UtilityAI` + `RoleAssignment` on unit archetypes,
  not per-instance imperative commands.
- Wave omits fog of war — every RTS has `RouteMap` with scout-reveal
  behavior.
- Wave conflates resource-harvesting with pickups — RTS workers
  PATHFIND to a resource node, extract over time, return to storage.
  `CrowdSimulation` handles the pathfinding; `StateMachineMechanic`
  handles the mine/return cycle.
- Wave builds a "select a unit, attack" pattern — real RTS combat is
  UtilityAI-driven: you ORDER groups, unit AI resolves individual
  target selection and micro.
