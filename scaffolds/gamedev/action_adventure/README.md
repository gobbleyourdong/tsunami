# Tsunami Gamedev — Action Adventure Scaffold

Top-down action-adventure (Zelda-like). Ships with 5 overworld rooms + 3 dungeon rooms + 4 enemy archetypes + 6 items wired and playable out of the box.

## Customization paths

### Add a new enemy (easiest)
Append to `data/entities.json`:
```json
{"id": "new_enemy", "type": "enemy", "components": {
  "Health": {"current": 2, "max": 2},
  "Tags": ["enemy", "melee"],
  "Sprite": {"id": "enemies/grunt"}
}}
```
Reference the id in any room's `spawns[]` in `data/rooms.json`.

### Add a new room
Append to `data/rooms.json`:
```json
{"new_room": {"kind": "overworld", "size": [16,16], "biome": "forest",
  "spawns": ["grunt_melee"], "connections": {"west": "overworld_start"}}}
```
Then add the reverse connection in `overworld_start`.

### Add a new item
Append to `data/items.json` with a `use_effect` (for weapons/consumables) or `tags: ["key"]` (for progression items).

### Change rules
`data/config.json` has `starting_room`, player HP, viewport size. `data/mechanics.json` controls camera lerp, room-transition style, lock-and-key pairs.

## Directory layout

```
action_adventure/
├── package.json              # engine dep
├── tsconfig.json, vite.config.ts
├── index.html                # #game-canvas + boot banner
├── src/
│   ├── main.ts               # boots, renders heartbeat, mounts starting scene
│   └── scenes/
│       ├── Overworld.ts      # top-down exploration (5 rooms)
│       ├── Dungeon.ts        # lock-and-key + boss (3 rooms)
│       └── GameOver.ts
└── data/
    ├── config.json           # starting_room, HP, viewport
    ├── entities.json         # player + 4 enemies + boss
    ├── rooms.json            # 5 overworld + 3 dungeon
    ├── items.json            # sword / bow / bomb / key / heart / compass
    ├── mechanics.json        # CameraFollow + RoomGraph + LockAndKey + HUD + Checkpoint
    └── SEED_ATTRIBUTION.md   # essence sources (Zelda / Super Metroid / Tomb Raider)
```

## Mechanics prewired (from @engine/mechanics)

- **CameraFollow** — player-centered lerp + deadzone
- **RoomGraph** — screen-flip transitions between rooms
- **LockAndKey** — small-key opens dungeon 1's locked door
- **ItemUse** — weapon/consumable dispatch (sword attack, bow shot, bomb place)
- **HUD** — hearts (health) + item inventory
- **CheckpointProgression** — respawn at last cleared room
- **BossPhases** — 2-phase boss at dungeon 1 end

## Seed attribution

See `data/SEED_ATTRIBUTION.md` — content sourced from `1986_legend_of_zelda` (primary), `1994_super_metroid` (movement reference), `1996_tomb_raider` (camera/checkpoint pattern) via JOB-D.

## Running

```bash
npm install  # first time
npm run dev  # localhost:5174
```
