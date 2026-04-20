# Tsunami Gamedev — Platformer Scaffold

2D platformer scaffold covering three canonical lineages: Super Mario Bros. (1985 — world-stage progression + mushroom/fire-flower powerups + goomba/koopa enemies), Mega Man 2 (1988 — boss-gauntlet + weapon-swap), Celeste (2018 — dash + coyote-frames + precision-jumping). Ships 4-5 levels + 5-7 enemy archetypes + 4-6 powerups + PhysicsModifier/CheckpointProgression/PickupLoop/LockAndKey prewired.

## Scene flow

`Title → Level → GameOver → (Title on continue)`

- **Title** — splash + press-start. Mounts `ChipMusic` + `HUD`.
- **Level** — the gameplay loop. Mounts `PhysicsModifier` (gravity/friction/time-scale tunable per level) + `CheckpointProgression` + `PickupLoop` + `LockAndKey` + `CameraFollow` + `LoseOnZero` + `WinOnCount` + `HUD` + `SfxLibrary`.
- **GameOver** — hit on lives=0. Continue prompt.

## Customization paths

### Add a level

Append to `data/levels.json::levels`:
```json
{"1-3": {
  "display_name": "World 1-3",
  "width": 200, "height": 14,
  "gravity_scale": 1.0,
  "starting_point": [2, 2],
  "exit_point": [195, 2],
  "checkpoints": [[80, 3]],
  "enemies": ["goomba", "koopa"],
  "powerups": ["mushroom", "1up"],
  "secret_areas": [],
  "tags": ["level", "world_1"]
}}
```

Make sure the `exit_point` + at least one `checkpoint` are reachable from `starting_point`.

### Change jump feel (gravity)

Edit `Level.ts::setup()` — adjust the `PhysicsModifier` mount's `gravity_scale`:
- `1.0` — default (SMB-like fall)
- `0.85` — floatier (Celeste)
- `1.5` — heavier fall (Mega Man)
- `-1.0` — inverted gravity (VVVVVV)

Or tune per-level by adding `gravity_scale` to a level entry — `loadLevel()` reads it and retunes PhysicsModifier on entry.

### Add an enemy

Append to `data/enemies.json::enemies`:
```json
{"new_enemy": {
  "display_name": "New Enemy",
  "sprite_ref": "sprites/enemies/new_enemy",
  "hp": 2,
  "ai_kind": "walker",
  "speed": 1.5,
  "components": ["Health(2)", "Velocity(1.5, 0)"],
  "tags": ["enemy", "ground"]
}}
```

AI kinds (seed uses these): `walker` (SMB Goomba), `patrol` (Koopa), `fly` (Paratroopa), `charge` (SMB Bowser-throw-line), `static` (Thwomp).

### Add a powerup

Append to `data/powerups.json::powerups`:
```json
{"mushroom_super": {
  "display_name": "Super Mushroom",
  "sprite_ref": "sprites/powerups/mushroom_super",
  "effect": "grow",
  "duration_sec": null,
  "tags": ["powerup", "mushroom"]
}}
```

Effects in seed: `grow` (small→big), `shoot` (fireball), `invincibility` (star), `extra_life` (1up), `dash` (Celeste-style). The mounted `PickupLoop` dispatches via `effect_on_collect`.

## Directory layout

```
platformer/
├── package.json, tsconfig.json, vite.config.ts
├── index.html
├── src/
│   ├── main.ts
│   └── scenes/
│       ├── Title.ts      # press-start
│       ├── Level.ts      # gameplay loop — PhysicsModifier + progression chain
│       └── GameOver.ts   # continue-prompt
└── data/
    ├── config.json            # starting_level + lives + scoring + win_condition
    ├── player.json            # walk_speed + jump_height + coyote_frames + dash
    ├── enemies.json           # 5-7 archetypes (walker/patrol/fly/charge/static)
    ├── powerups.json          # mushroom / fire-flower / star / 1up / dash-token
    ├── levels.json            # 4-5 levels with checkpoints + exits
    ├── mechanics.json         # 9 mechanic instances
    └── SEED_ATTRIBUTION.md    # essence sources (JOB-G output)
```

## Mechanics prewired (from @engine/mechanics)

- **PhysicsModifier** — gravity / friction / time-scale, tunable per level
- **CheckpointProgression** — mid-level respawn + life-loss on death
- **PickupLoop** — coins + powerup collection + Mario-style effects
- **LockAndKey** — keys gate doors to bonus areas
- **CameraFollow** — horizontal lead on the player
- **LoseOnZero** / **WinOnCount** — lives=0 = game over, end-flag = next level
- **HUD** / **ChipMusic** / **SfxLibrary** — universal scene glue

## Seed attribution

Content from `1985_super_mario_bros` (goomba/koopa/piranha enemies + mushroom/fire-flower/star powerups + world-stage structure), `1988_mega_man_2` (boss gauntlet + weapon variety + charge patrols), `2018_celeste` (dash + coyote-frames + precision-movement) via JOB-G. See `data/SEED_ATTRIBUTION.md`.

## Running

```bash
npm install
npm run dev  # localhost:5177
```
