# Tsunami Gamedev — Stealth Scaffold

Stealth scaffold covering three canonical lineages: Metal Gear Solid (1998 — cone-vision + radar + alert escalation + silenced pistol / stun grenade), Thief (1998 — light/shadow detection + lockpicking + ambient tension), Splinter Cell (2002 — night-vision + body-drag + light/noise meters). Ships 3-4 levels + 3-5 guard archetypes + 5-7 tools + VisionCone/HotspotMechanic/LockAndKey prewired.

## Scene flow

`Title → Level → GameOver → (Title on continue)`

- **Title** — splash + press-start. Mounts `ChipMusic` + `HUD`.
- **Level** — the gameplay loop. Mounts `VisionCone` (guard detection) + `HotspotMechanic` (hiding spots + vents) + `LockAndKey` (keycards) + `ItemUse` (silenced pistol / smoke / rock / stun baton / lockpick / body-drag) + `PickupLoop` + `HUD` (health + stealth meter + alert level) + `LoseOnZero` + `ChipMusic` + `SfxLibrary`.
- **GameOver** — hit on Health=0 or alarm_tolerance exceeded.

## Customization paths

### Add a guard archetype

Append to `data/guards.json::guards`:
```json
{"sniper_lookout": {
  "display_name": "Sniper Lookout",
  "hp": 80,
  "vision_cone": { "fov_deg": 120, "range": 12, "alert_threshold": 0.4 },
  "patrol_kind": "stationary",
  "patrol_path_ref": "tower_overlook",
  "components": ["Health(80)", "Weapon('sniper_rifle')"],
  "tags": ["guard", "stationary", "ranged"]
}}
```

Patrol kinds in seed: `stationary` (tower guard), `patrol` (MGS soldier), `roaming` (sweeper), `camera` (fixed surveillance).

### Add a tool

Append to `data/tools.json::tools`:
```json
{"night_vision": {
  "display_name": "Night Vision Goggles",
  "effect": "enable_nv_mode",
  "stealth_impact": 0,
  "duration_sec": null,
  "tags": ["tool", "utility", "nv"]
}}
```

Effects in seed: `fire_silenced` (silenced pistol), `throw_smoke` (smoke grenade), `distract_audio` (throw rock), `stun` (baton), `pick_lock` (lockpick), `drag_body` (body hide).

### Add a level

Append to `data/levels.json::levels`:
```json
{"mission_3": {
  "display_name": "Embassy Infiltration",
  "rooms": ["entrance", "lobby", "upper_hall", "vault"],
  "patrol_paths": [
    { "id": "lobby_circuit", "waypoints": [[5,5],[15,5],[15,10],[5,10]], "guard_ref": "patrol_guard" }
  ],
  "hiding_spots": [[8, 7], [12, 3]],
  "objective_items": ["intel_briefcase"],
  "extraction_point": [20, 15],
  "alarm_tolerance": 3,
  "tags": ["level", "infiltration"]
}}
```

Every level has patrol_paths (guard waypoints), hiding_spots, objective_items, and an extraction_point. `alarm_tolerance` sets how many detections the player can survive before mission fail.

### Tune detection

Edit `Level.ts::setup()` — `VisionCone` params:
- `fov_deg`: 60 = tight forward cone, 120 = wide sweep, 360 = omnidirectional (security camera).
- `range`: 4-8 tiles typical; snipers longer.
- `alert_threshold`: 0.3 = twitchy guards (Splinter Cell hard), 0.7 = lenient (MGS easy).
- `degrade_on_break_los`: `true` = line-of-sight break decays alert; `false` = alert persists.

## Directory layout

```
stealth/
├── package.json, tsconfig.json, vite.config.ts
├── index.html
├── src/
│   ├── main.ts
│   └── scenes/
│       ├── Title.ts      # splash
│       ├── Level.ts      # gameplay loop — 9 mechanics
│       └── GameOver.ts   # retry prompt
└── data/
    ├── config.json            # starting_level / inventory / alarm_tolerance
    ├── player.json            # Health + Stealth + Inventory
    ├── guards.json            # 3-5 archetypes w/ vision_cone params
    ├── tools.json             # 5-7 player tools
    ├── levels.json            # 3-4 levels w/ patrol_paths + hiding_spots
    ├── mechanics.json         # 9 mechanic instances
    └── SEED_ATTRIBUTION.md    # essence sources (JOB-R output)
```

## Mechanics prewired (from @engine/mechanics)

- **VisionCone** — guard detection with FOV + range + alert-threshold
- **HotspotMechanic** — hiding spots + vent entries + ladder climbs
- **LockAndKey** — keycard-gated doors + lockpick pathways
- **ItemUse** — silenced_pistol / smoke_grenade / throw_rock / stun_baton / lockpick / body_drag
- **PickupLoop** — ammo / keycards / collectibles
- **HUD** / **LoseOnZero** / **ChipMusic** / **SfxLibrary** — universal scene glue

## Seed attribution

Content from `1998_metal_gear_solid` (cone-vision + radar + codec + silenced pistol + Snake's soliton radar), `1998_thief` (light/shadow detection + Garrett's blackjack + lockpicks + ambient tension music), `2002_splinter_cell` (night-vision + body-drag + light/noise meters + Sam Fisher's stealth suit) via JOB-R. See `data/SEED_ATTRIBUTION.md`.

## Running

```bash
npm install
npm run dev  # localhost:5179
```
