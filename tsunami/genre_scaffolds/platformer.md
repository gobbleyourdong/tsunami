---
applies_to: [gamedev]
mood: kinetic, forgiving-but-tight, momentum-driven
corpus_share: 18
default_mode: dark
anchors: super_mario_bros, super_mario_64, super_metroid, castlevania_sotn
default_mechanics: [CameraFollow, PickupLoop, CheckpointProgression, PhysicsModifier, AttackFrames]
recommended_mechanics: [WaveSpawner, StateMachineMechanic, LevelSequence, LockAndKey, HUD, BossPhases]
would_falsify: if a platformer delivery tagged with this genre ships without PhysicsModifier or equivalent jump-physics tuning, or the player cannot traverse horizontally with momentum, the genre directive was ignored — measured via mechanic adoption probe on PhysicsModifier + CameraFollow imports
---

## Pitch

Traversal through discrete levels via run-and-jump navigation. The
core verb is MOVE — jump arcs and landing precision are the primary
skill surface. Enemies exist as traversal obstacles, not combat
opponents. SMB 1985 defines the 2D kinematic baseline; SM64 defines
the 3D camera-led variant; Super Metroid extends into backtracking
(metroidvania sub-family — see separate genre).

## Mechanic set (anchor examples)

1. `PhysicsModifier` — jump gravity, terminal velocity, bounce coeffs.
2. `CameraFollow` — scroll-behind or look-ahead smoothing.
3. `PickupLoop` — coins/fruit/rings as traversal rewards.
4. `CheckpointProgression` — mid-level restart anchors.
5. `AttackFrames` — per-move timing (stomp window, spin duration).
6. `StateMachineMechanic` — grounded / airborne / wall-slide states.
7. `LevelSequence` — world-1-1 → 1-2 → boss → world-2-1 ordering.
8. `WaveSpawner` — rare; spawners feed enemies as moving obstacles.
9. `LockAndKey` — keys for locked-door side-rooms (bonus/secret).
10. `HUD` — lives, coins, timer, world-level indicator.

## Common shape

- **Level count**: 4-16 levels, each ~30-90s playtime.
- **Fail state**: on HP=0 or fall-off-screen, return to checkpoint or
  level start.
- **Progression curve**: power-ups (fire-flower, super-mushroom) or
  ability-gated traversal. Speed and precision ramp.
- **Control**: d-pad/WASD left-right, space/jump, shift/run, attack on Z.

## Non-goals

- NOT a metroidvania (use `metroidvania` — backtracking + ability-gated
  world, NOT linear level list).
- NOT an action-adventure (use `action_adventure` — top-down scene
  graph, not side-scrolling).
- NOT a puzzle platformer (use `puzzle_platformer` — single-screen
  logic puzzles vs. kinematic traversal).
- NOT a beat-em-up (use `beat_em_up` — horizontal combat arenas).

## Anchor essences

`scaffolds/.claude/game_essence/1985_super_mario_bros.md` —
canonical 2D. PhysicsModifier + CameraFollow baseline.

`scaffolds/.claude/game_essence/1996_super_mario_64.md` —
3D variant with analog momentum and CameraFollow becoming a first-class
challenge. Use for "3D platformer" prompts.

`scaffolds/.claude/game_essence/1994_super_metroid.md` —
platformer + backtracking (falls under `metroidvania` genre when the
exploration is the primary progression). Use as a reference for wall-
jump / grapple mechanics that platformer can optionally adopt.

`scaffolds/.claude/game_essence/1997_castlevania_symphony_of_night.md`
— platformer + RPG elements; the `LevelUpProgression` cross-over.

## Pitfalls the directive is trying to prevent

- Wave defaults to a single-screen arcade loop ("one level, enemies
  walk left, player shoots"). Platformer REQUIRES at least a
  `LevelSequence` of 3 distinct levels and checkpoint state.
- Wave uses `position += velocity` naively — `PhysicsModifier` carries
  the catalog's tuned gravity + coyote-time params. Skipping it means
  jumps feel "floaty."
- Wave omits CameraFollow smoothing; player walks off-screen during
  long horizontal runs. The catalog entry handles look-ahead bias.
