---
applies_to: [gamedev]
mood: patient, cerebral, unmasked-means-dead, state-reading
corpus_share: 7
default_mode: dark
anchors: metal_gear_solid, thief_the_dark_project, splinter_cell, hitman_codename_47
default_mechanics: [VisionCone, UtilityAI, StateMachineMechanic, HUD, LockAndKey]
recommended_mechanics: [ItemUse, CheckpointProgression, BossPhases, RouteMap, GatedTrigger, PickupLoop]
would_falsify: if a stealth delivery tagged with this genre ships without VisionCone or equivalent detection-state mechanic, OR the player is expected to win through combat rather than evasion, the genre directive was ignored — measured via mechanic adoption probe for VisionCone presence AND runtime-check for alarm/detection state transitions
---

## Pitch

Evade observation, not defeat. The core verb is SNEAK — combat is
either impossible, heavily penalized, or tactically last-resort.
Detection is a LEGIBLE state the player reads from enemy AI cues
(sight cones, sound rings, alarm timers). Thief 1998 defines the
light-based variant; MGS 1998 the radar-based; Splinter Cell 2002
the dual (light + sound + visor). Hitman 2000 extends into
disguise-driven social stealth.

## Mechanic set (anchor examples)

1. `VisionCone` — per-enemy sight cones with distance falloff.
2. `UtilityAI` — enemy state machines for patrol / alerted /
   searching / chasing / lost.
3. `StateMachineMechanic` — GLOBAL alarm state (quiet / suspicious /
   alerted / lockdown).
4. `HUD` — detection meter, sound meter, visibility indicator (diegetic
   or overlay).
5. `LockAndKey` — keyed doors, KeyPickup items, RFID cards.
6. `ItemUse` — lockpicks, distractions (noisemaker, water arrow),
   non-lethal takedowns.
7. `RouteMap` — minimap showing revealed patrol paths; maps as
   collectible items in some titles.
8. `GatedTrigger` — mission-objective flags (steal-without-kills,
   complete-under-timer).
9. `PickupLoop` — loot rewards for skilled play.
10. `CheckpointProgression` — usually sparse; failure reverts far.

## Common shape

- **Mission count**: 6-15 levels, each self-contained arena.
- **Enemy count per mission**: 4-20 patrolling guards; dense enough
  to create overlapping vision cones.
- **Fail state**: on detection → alarm → chase. Death rare; failure is
  loud (guards converge, mission-rank drops).
- **Progression curve**: unlock tools (silencer, EMP, camo). Mission
  ranks reward no-kills / no-detect.
- **Control**: WASD, shift=crouch, control=prone, E=interact, Q=lean.

## Non-goals

- NOT a tactical shooter (use `tactical_fps` — breach-and-clear; stealth
  is pre-combat, not combat-adjacent).
- NOT a survival horror (use `survival_horror` — horror-themed, not
  skill-expression).
- NOT a strategy game (use `rts` or `tactics_rpg` — high-level command,
  not first/third-person single-unit).
- NOT a pure puzzle game — stealth has a RUNNING-CLOCK tension pure
  puzzles don't.

## Anchor essences

`scaffolds/.claude/game_essence/1998_thief_dark_project.md` —
**light-based stealth canonical**. Light-gem HUD (LightBasedStealth).
`SoundBasedDetection` from surfaces. Rope arrow + water arrow as
environment-manipulation (`EnvironmentManipulation`). Loot gating
(`LootThreshold`).

`scaffolds/.claude/game_essence/1998_metal_gear_solid.md` —
radar-based stealth. `VisionCone` with radar-reveal. `CompanionNPC`
(Mei Ling, Otacon codec). `CodecCommunication`. `MetaInteraction`
(Psycho Mantis).

`scaffolds/.claude/game_essence/2002_splinter_cell.md` —
dual stealth (light + sound + visor modes). `VisionModeToggle`.
`BodyDragHide`. `NonLethalAlternatives`. `AlarmBudget` —
mission-limited alarm count before lockdown.

`scaffolds/.claude/game_essence/2000_hitman_codename_47.md` —
social stealth via disguise. `DisguiseSystem`. `SandboxMissionArena`.
`PreMissionLoadout`. `NPCSchedule` per target.

## Pitfalls the directive is trying to prevent

- Wave builds a "shooter with light enemies" — stealth is NOT easy
  shooting. Detection must be MEANINGFULLY punishing; `VisionCone` and
  `UtilityAI` with state-transition cost are non-negotiable.
- Wave makes enemies omniscient — real stealth REQUIRES the player to
  read AI state. Enemies need LIMITED sensing (cone, not sphere) and
  PRE-ALERT cues (head-turn, questioning voice line) before they
  commit to attack.
- Wave omits global alarm state — raising detection should escalate
  the world, not just trigger local combat. `StateMachineMechanic` on
  a session-level alarm var is the right pattern.
- Wave conflates stealth with RPG sneak-skill — real stealth genres
  don't use dice rolls. Detection is binary-per-observer, driven by
  geometry + audio, not stat checks.
