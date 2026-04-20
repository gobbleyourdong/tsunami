---
applies_to: [gamedev]
mood: playful, rubber-band, item-chaos, pick-up-and-play
corpus_share: 5
default_mode: dark
anchors: super_mario_kart, f_zero, gran_turismo, diddy_kong_racing
default_mechanics: [CameraFollow, WaveSpawner, ItemUse, HUD, ScoreCombos]
recommended_mechanics: [WinOnCount, CheckpointProgression, PickupLoop, RouteMap, UtilityAI, StateMachineMechanic]
would_falsify: if a kart-racer delivery tagged with this genre ships without item-based interaction between racers (items pickable from the track that affect other karts) OR lacks lap-based race structure with checkpoint progression, the genre directive was ignored — measured via mechanic adoption probe for ItemUse + CheckpointProgression AND runtime-check for multi-kart field (≥4 AI opponents)
---

## Pitch

Arcade racing with item-driven player interaction. The core verb is
OVERTAKE — steer, grab items, throw them, drift around rivals. Not
about perfect lap time; about causing chaos on the final straight.
Super Mario Kart 1992 defines the 2D template with Mode 7
backdrops; F-Zero 1990 the higher-speed anti-gravity variant; Gran
Turismo 1997 the sim-vs-arcade boundary case (more arcade flavor —
see `kart_racer` even for GT-like builds when items/AI-rubberbanding
are present); Diddy Kong Racing 1997 the adventure-mode variant.

## Mechanic set (anchor examples)

1. `CameraFollow` — behind-kart or chase-cam, always anchored to the
   player kart.
2. `WaveSpawner` — AI racer fleet spawned at race start; 4-8 AI opponents.
3. `ItemUse` — track-pickup items: shell, banana, mushroom, lightning.
4. `HUD` — position indicator, lap counter, item slot, minimap.
5. `ScoreCombos` — drift-boost mechanic (short boost per drift arc).
6. `PickupLoop` — item boxes on the track, respawning after use.
7. `RouteMap` — minimap with live-kart-positions. `KartRacingCamera`
   variant per essence.
8. `CheckpointProgression` — lap-progress gates, prevent cutting.
9. `WinOnCount` — best-in-class (1st place) or cup structure
   (`TournamentStructure`).
10. `UtilityAI` — per-AI-kart decision: target nearest player with
    item, rubber-band to keep race close (`RubberBandAI`).

## Common shape

- **Track count**: 8-32 tracks organized into cups (`TournamentStructure`).
- **Lap count**: 3 laps per track (`CheckpointProgression` with 3
  repeats).
- **Racer count**: 4-8 per race (player + 3-7 AI).
- **Item count**: 6-12 item types; probability skewed by race position
  (trailing kart gets better items — `RubberBandItems`).
- **Fail state**: finish last; or time-out in time-trial variants.
- **Progression curve**: unlock cups, characters, tracks. No permanent
  character growth (except tracks/karts). Ghost replay (`GhostReplay`)
  for time-trial.
- **Control**: accelerate (A/X), brake (B/Square), drift+hop (R/L),
  use item (L/R or trigger).

## Non-goals

- NOT a sim racer (use `sim_racing` if it lands — physics-accurate,
  no items, tuning over chaos).
- NOT a combat racer (use `combat_racing` like Twisted Metal — kart-
  racer items are incidental projectiles; combat-racer items are
  primary weapons).
- NOT a kart-racer-style sports game — racing primitive, not score-
  based like arcade sports.
- F-Zero is an edge case (no items in original) — included here
  because `TournamentStructure`, `RubberBandAI`, and lap structure
  dominate; close to kart-racer per audit of anchor essences.

## Anchor essences

`scaffolds/.claude/game_essence/1992_super_mario_kart.md` —
**kart-racer canonical**. `RubberBandItems`, `RubberBandAI`,
`GhostReplay`, `SplitScreenCoop` (local versus). Mode 7 rendering.

`scaffolds/.claude/game_essence/1990_f_zero.md` —
higher-speed variant without items. `KartRacingCamera`, `RubberBandAI`.
Sets the anti-grav racer template GT, Wipeout, Mario Kart Wii riff on.

`scaffolds/.claude/game_essence/1997_gran_turismo.md` —
sim-racer BUT carries `LicensedAssetCatalog`, `VehicleTuning`,
`SkillGatedProgression`. Include when prompt says "licensed cars" or
"tuning" — those features cross over.

## Pitfalls the directive is trying to prevent

- Wave builds "racing game with no items" — kart-racers are DEFINED by
  item-based interaction. No items → sim racer or arcade racer, not
  kart racer.
- Wave omits `RubberBandAI` — without it, trailing AI gives up and
  the race is boring after lap 1. Rubber-banding is a FEATURE, not a
  bug; `UtilityAI` with rubber-band utility term.
- Wave models items as damage (shell reduces HP) — items are TIME
  penalties (spin-out 1s, speed down 0.5s). Kart-racers have no HP.
- Wave makes all AI karts identical — each AI should have a personality
  (aggressive, cautious, perfect-racer). Different `UtilityAI`
  weights per AI archetype.
- Wave uses a single-lap time-trial as the primary mode — kart-racer
  identity is MULTI-KART RACE, not time-trial. 4+ karts on track is
  the genre baseline.
