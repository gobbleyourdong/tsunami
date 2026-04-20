# Tsunami Gamedev — FPS Scaffold

FPS scaffold covering three canonical lineages: Doom (1993 — room-graph levels + keycard progression + hitscan+projectile weapons + demon enemies), Quake (1996 — 3D movement refinement), Half-Life (1998 — narrative FPS + weapon variety). Ships 3-4 levels + 4-6 enemies + 6-9 weapons + BulletPattern/WaveSpawner/AttackFrames prewired.

## Scene flow

`Title → Level → GameOver → (Title on continue)`

- **Title** — splash + press-start. Mounts `ChipMusic` + `HUD`.
- **Level** — the gameplay loop. Mounts `BulletPattern` (weapon projectiles) + `WaveSpawner` (enemy waves on trigger zones) + `AttackFrames` + `PickupLoop` + `ItemUse` + `LockAndKey` + `CameraFollow` (first-person, lerp=0) + `HUD` + `LoseOnZero`.
- **GameOver** — hit on player Health=0.

## Customization paths

### Add a weapon

Append to `data/weapons.json::weapons`:
```json
{"plasma_rifle": {
  "display_name": "Plasma Rifle",
  "damage": 20,
  "ammo_per_shot": 1,
  "ammo_kind": "cells",
  "spread": 0.01,
  "rate_of_fire": 10,
  "reload_sec": 1.2,
  "projectile_kind": "projectile",
  "sprite_ref": "sprites/weapons/plasma_rifle",
  "tags": ["weapon", "energy"]
}}
```

`projectile_kind`: `hitscan` (instant, Doom pistol/shotgun/chaingun), `projectile` (travel time, rocket/plasma), `aoe` (explosive, BFG-like).

### Change equipped weapon

Edit `Level.ts` — call `equipWeapon(id)` at runtime, or change `starting_weapon_equipped` in `config.json`.

### Add an enemy

Append to `data/enemies.json::enemies`:
```json
{"imp_fireball": {
  "display_name": "Imp",
  "hp": 40,
  "damage": 10,
  "attack_kind": "projectile",
  "speed": 1.2,
  "projectile_ref": "fireball",
  "drop_table": ["ammo_bullets", "medkit_small"],
  "sprite_ref": "sprites/enemies/imp",
  "components": ["Health(40)", "Velocity(1.2, 0)"],
  "tags": ["enemy", "demon", "mid-tier"]
}}
```

Attack kinds in seed: `melee` (zombieman-bite), `hitscan` (former-human), `projectile` (imp fireball), `charge` (pinky-demon rush), `aoe` (revenant rocket-swarm).

### Add a level

Append to `data/levels.json::levels`:
```json
{"e1m2": {
  "display_name": "Nuclear Plant",
  "rooms": ["start", "hall_n", "control", "reactor", "exit"],
  "doors": [
    { "from": "start", "to": "hall_n" },
    { "from": "hall_n", "to": "control", "requires_key": "blue" },
    { "from": "control", "to": "reactor", "requires_key": "yellow" },
    { "from": "reactor", "to": "exit" }
  ],
  "enemy_spawns": [
    { "room": "hall_n", "archetype": "zombieman", "count": 4 },
    { "room": "reactor", "archetype": "imp", "count": 6 }
  ],
  "pickups": [
    { "room": "start", "item": "shotgun" },
    { "room": "control", "item": "blue_keycard" }
  ],
  "exit_target": "e1m3",
  "tags": ["level", "episode_1"]
}}
```

Every level is a room-graph with `rooms[]` + `doors[]`; keys gate progression via LockAndKey.

## Directory layout

```
fps/
├── package.json, tsconfig.json, vite.config.ts
├── index.html
├── src/
│   ├── main.ts
│   └── scenes/
│       ├── Title.ts      # splash
│       ├── Level.ts      # gameplay loop — 9 mechanics prewired
│       └── GameOver.ts   # restart prompt
└── data/
    ├── config.json            # starting_level/weapons/ammo/difficulty
    ├── player.json            # Health + Armor + Ammo pools per family
    ├── weapons.json           # 6-9 weapons w/ damage+ammo+spread+rate
    ├── enemies.json           # 4-6 archetypes w/ drop tables
    ├── levels.json            # 3-4 levels as room-graph + keys/switches
    ├── mechanics.json         # 9 mechanic instances
    └── SEED_ATTRIBUTION.md    # essence sources (JOB-H output)
```

## Mechanics prewired (from @engine/mechanics)

- **BulletPattern** — weapon projectiles + hitscan rays
- **WaveSpawner** — enemy spawn waves on trigger zones
- **AttackFrames** — windup/active/recovery windows
- **PickupLoop** / **ItemUse** — ammo + medkit + armor pickups + useable items
- **LockAndKey** — keycard-gated doors
- **CameraFollow** — first-person (lerp=0, deadzone=[0,0])
- **HUD** / **LoseOnZero** / **ChipMusic** — universal scene glue

## Seed attribution

Content from `1993_doom` (zombieman/imp/pinky/caco/revenant + pistol/shotgun/chaingun/rocket + E1M1 keycard-gated levels), `1996_quake` (3D movement refinement + nailgun mechanics), `1998_half_life` (crowbar + HEV-suit armor + narrative level progression) via JOB-H. See `data/SEED_ATTRIBUTION.md`.

## Running

```bash
npm install
npm run dev  # localhost:5178
```
