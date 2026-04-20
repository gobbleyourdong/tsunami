---
applies_to: [gamedev]
mood: sandbox-explorative, player-driven-agenda, systemic, dense-map
corpus_share: 8
default_mode: dark
anchors: grand_theft_auto_iii, grand_theft_auto_vice_city, morrowind, mafia
default_mechanics: [RoomGraph, UtilityAI, VisionCone, HUD, CameraFollow, ItemUse]
recommended_mechanics: [DialogTree, Shop, InventoryCombine, GatedTrigger, WaveSpawner, CrowdSimulation]
would_falsify: if an open-world delivery tagged with this genre ships with the world gated by linear mission-order (player cannot wander off-path from start) OR lacks diegetic world activity (NPCs standing still, no traffic, no day-night cycle), the genre directive was ignored — measured via runtime-check for player free-roam at mission 1 + presence of `DayNightCycle` / `CrowdSimulation` style mechanics
---

## Pitch

A large map the player can roam freely, with optional main-story
progression woven through. The core verb is EXPLORE — at your pace,
in your order. GTA III 2001 seeds the modern 3D open-world with
`OpenWorld3D` + `VehicleSystem` + `WantedLevel`; Morrowind 2002 does
it in fantasy with `ClassBuilder` and `FactionReputation` layered on;
Shenmue 1999 foreshadows the NPC-schedule-driven open-world;
Sid Meier's Pirates! 1987 is the primordial ancestor of the whole
sandbox lineage.

## Mechanic set (anchor examples)

1. `RoomGraph` — large interconnected map (city, continent, or country).
   Seamless streaming vs. loading zones is an implementation detail.
2. `UtilityAI` — per-NPC schedule + per-faction behavior. NPCs have
   agendas.
3. `CameraFollow` — third-person chase-cam or free-look first-person.
4. `VisionCone` — police / guard reaction to player crime (`WantedLevel`).
5. `HUD` — minimap, quest-marker, health, currency, time-of-day.
6. `ItemUse` — deep inventory: weapons, vehicles, clothing, spells
   (fantasy variant).
7. `DialogTree` — NPC-driven quests, faction relations.
8. `Shop` — weapons, food, equipment; specialized vendors per
   district.
9. `GatedTrigger` — mission-progression flags (story) interleaved
   with roam gates (ability, story-completion, reputation).
10. `WaveSpawner` — ambient enemy/NPC/traffic spawners that respond
    to player location + time.

## Common shape

- **Map size**: 1-10 km² (GTA III: 10 km; Morrowind: 25 km²). Big
  enough to warrant in-world traversal, not a loading-screen grid.
- **Mission count**: 40-150 missions spanning a main story + side quests
  + faction quests.
- **Day-night cycle**: present in most canonical open-worlds
  (`DayNightCycle`). NPCs have schedules tied to time.
- **Fail state**: HP=0 → respawn at hospital/temple/safehouse with
  money penalty. No hard game-over outside mission fail-states.
- **Progression curve**: story gates regions or abilities; player
  can ignore story and level through side-content.
- **Control**: WASD (PC) or dual-analog (console) movement; camera
  via mouse/right-stick; context-sensitive interact; vehicle-enter
  key; radial inventory menu.
- **Playtime**: 30-100 hours.

## Non-goals

- NOT a metroidvania (use `metroidvania` — smaller map, ability-gated
  re-exploration is the point; open-world's gates are mission/faction-
  driven, not ability-driven).
- NOT an action-adventure (use `action_adventure` — episodic scene-
  graph; open-world is one contiguous sandbox).
- NOT a CRPG / WRPG (use `wrpg` when it lands — party-based, turn-
  based combat, different loop).
- NOT a sim game (use `city_builder` / `life_sim` — open-world has
  player-character at center).

## Anchor essences

`scaffolds/.claude/game_essence/2001_grand_theft_auto_iii.md` —
**modern 3D open-world canonical**. `OpenWorld3D`, `VehicleSystem`,
`WantedLevel`, `MissionHub`, `DiegeticRadio`, `DayNightCycle`,
`CrowdSimulation`. The template most modern open-worlds follow.

`scaffolds/.claude/game_essence/2002_grand_theft_auto_vice_city.md` —
GTA III's direct extension. Adds `BusinessPropertyIncome`, deepens
the radio-as-atmosphere identity.

`scaffolds/.claude/game_essence/2002_elder_scrolls_iii_morrowind.md`
— fantasy open-world canonical. `QuestJournal`, `ClassBuilder`,
`FactionReputation`, `SpellCrafting`, `UseBasedProgression`,
`CraftingRecipes`, `ServiceBasedFastTravel`, `PlayerHousing`,
`MortalNPC`. Shows open-world-with-RPG-depth template.

`scaffolds/.claude/game_essence/2002_mafia.md` —
GTA III contemporaries with heavier narrative hand. `MissionHub`,
`WantedLevel`, `DiegeticRadio`, `NPCSchedule`.

`scaffolds/.claude/game_essence/1999_shenmue.md` —
proto-open-world with NPC schedules and QTE integration. Included
because `NPCSchedule` + `WeatherSystem` + `InWorldMessageSystem`
define the open-world-as-lived-in-space idiom.

`scaffolds/.claude/game_essence/1987_sid_meiers_pirates.md` —
**sandbox-open-world 15-years-pre-GTA-III**. Primordial ancestor.
Include as reference when prompt mentions "sailing sandbox" or
"age-of-sail open-world."

## Pitfalls the directive is trying to prevent

- Wave builds a corridor game with a big map texture — open-world
  REQUIRES genuine free-roam from mission 1. If the player is gated
  into story-order, it's linear with big environments, not open-world.
- Wave omits traffic / NPC schedules — open-world IDENTITY is
  "lived-in world continues without player." `UtilityAI` with
  ambient agendas + `CrowdSimulation` is the texture.
- Wave makes all NPCs immortal — `MortalNPC` in Morrowind is a real
  feature (warns the player they've broken the main quest) that
  distinguishes the genre from on-rails narrative games.
- Wave builds one scale of map — open-worlds benefit from
  MULTIPLE-SCALES (streets, neighborhoods, districts, city, continent).
  `RoomGraph` with nested zones.
- Wave treats the map as a menu of missions — open-world missions
  START at a location (pickup, meet NPC at bar). Travel IS part of
  the gameplay. `WantedLevel` pressure during travel is a GTA
  invention that makes travel meaningful.
- Wave bakes fantasy-only or crime-only assumptions — open-world
  spans genres (fantasy RPG, crime action, sci-fi, western, sailing
  sandbox). Genre-specific tropes come from CONTENT CATALOG, not from
  this directive.
