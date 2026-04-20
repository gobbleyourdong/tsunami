---
applies_to: [gamedev]
mood: fast, weighty, spatial, texture-of-violence
corpus_share: 10
default_mode: dark
anchors: doom, quake, half_life, goldeneye_007, halo_ce
default_mechanics: [CameraFollow, BulletPattern, HUD, WaveSpawner, AttackFrames, StateMachineMechanic]
recommended_mechanics: [LoseOnZero, LockAndKey, PickupLoop, BossPhases, ItemUse]
would_falsify: if an FPS delivery tagged with this genre ships without a first-person camera (CameraFollow in FPS mode), or uses third-person projectile mechanics, the genre directive was ignored — measured via mechanic adoption probe for CameraFollow presence AND BulletPattern OR AttackFrames on weapons
---

## Pitch

First-person traversal of closed-room arenas with weapon-driven
combat. The core verb is SHOOT — aim-and-destroy resolves every
encounter. Levels are gated by keycards, switches, or boss-kills;
weapons are the progression axis. Doom 1993 defines the baseline;
Quake 1996 adds vertical movement; Half-Life 1998 adds scripted
sequence; Halo CE 2001 adds regenerating shield + vehicle.

## Mechanic set (anchor examples)

1. `CameraFollow` — first-person mount to player head; mouse-look.
2. `BulletPattern` — hitscan (instant) or projectile (tracked) emitters.
3. `WaveSpawner` — room-gated enemy spawning on player entry.
4. `AttackFrames` — per-weapon fire rate, reload windows, alt-fire.
5. `StateMachineMechanic` — weapon-select / reload / ready states.
6. `HUD` — health, armor, ammo, weapon icon, minimap (optional).
7. `LoseOnZero` — HP=0 triggers restart at checkpoint.
8. `LockAndKey` — keycards (blue/yellow/red) unlock locked rooms.
9. `PickupLoop` — ammo/med/armor/keycard pickups on map.
10. `BossPhases` — level-ending boss with 2-3 distinct patterns.

## Common shape

- **Level count**: 6-20 maps organized into 2-4 episodes.
- **Enemy variety**: 4-10 enemy archetypes across all maps; reuse
  heavily.
- **Fail state**: HP=0 → restart map with starting weapons OR checkpoint.
- **Progression curve**: weapon unlocks gate room difficulty (super
  shotgun, rocket launcher, bfg). Each weapon owns a niche.
- **Control**: WASD movement, mouse aim, LMB fire, 1-9 weapon select,
  space jump.

## Non-goals

- NOT a top-down shooter (use `top_down_shooter` — different camera, different
  combat rhythm).
- NOT a third-person shooter (use `third_person_shooter` or `action_adventure`
  for over-shoulder combat).
- NOT a tactical shooter (use `tactical_fps` — squad commands, cover
  system, realism pretensions).
- NOT a bullet-hell (use `bullet_hell` — 2D twin-stick-style pattern
  dodging, not FPS).

## Anchor essences

`scaffolds/.claude/game_essence/1993_doom.md` —
canonical FPS. Hitscan weapons, keycard progression, room-gated spawning.

`scaffolds/.claude/game_essence/1996_quake.md` —
true 3D (Doom's 2.5D resolves here). FPSMovement in 3 dimensions,
rocket jumps, movement-tech skill ceiling.

`scaffolds/.claude/game_essence/1998_half_life.md` —
scripted sequence + tram intro + physics puzzles. The "scripted FPS"
sub-family. Weapon: HEV suit voice feedback (VoiceoverFeedback).

`scaffolds/.claude/game_essence/1997_goldeneye_007.md` —
console-FPS with mission-based objectives (DifficultyScaledObjectives)
and LocalVersus. Control-scheme reference for gamepad.

`scaffolds/.claude/game_essence/2001_halo_combat_evolved.md` —
regenerating shield (RegenShield), limited-weapon-loadout
(LimitedCarryLoadout), vehicle traversal (VehicleSystem). The
"modern console FPS" template.

## Pitfalls the directive is trying to prevent

- Wave ships a 2D top-down "shoot-em-up" when prompt says "FPS" — the
  first-person CameraFollow mount is non-negotiable.
- Wave omits keycard progression; rooms are all accessible from start.
  FPS level design needs LOCKED regions with keyed unlocks.
- Wave re-invents weapon select as React dropdown; `StateMachineMechanic`
  with weapon-select state handles it in the catalog.
- Wave makes all enemies instant-reaction hitscan; real FPS enemies
  have windup → fire → recovery cadence (`AttackFrames` with startup
  frames).
