# Tsunami Gamedev — Racing Scaffold

Racing scaffold covering three canonical lineages: Out Run (1986 — arcade pseudo-3D cruising + timer-based checkpoint chase), Super Mario Kart (1992 — kart racing + item boxes + rubberband AI), Gran Turismo (1997 — sim-style vehicle tuning + handling physics). Ships 3-5 tracks + 4-6 vehicles + AI racers + CheckpointProgression prewired.

## Scene flow

`Title → Race → Finish → (Title on restart)`

- **Title** — splash + track select. Mounts `ChipMusic` + `HUD`.
- **Race** — gameplay loop. Mounts `CheckpointProgression` (lap counting) + `CameraFollow` (vehicle-anchored with look-ahead) + `PickupLoop` (powerup boxes) + `WinOnCount` (N laps = win) + `LoseOnZero` (DNF timer) + `HUD` + `ChipMusic` + `SfxLibrary`.
- **Finish** — results screen with final position + best lap + retry prompt.

## Customization paths

### Add a track

Append to `data/tracks.json::tracks`:
```json
{"snowpeak_raceway": {
  "display_name": "Snowpeak Raceway",
  "theme": "mountain",
  "lap_length": 1600,
  "checkpoints": [
    { "id": "cp_1", "position": [100, 50] },
    { "id": "cp_2", "position": [200, 100] },
    { "id": "cp_finish", "position": [0, 0] }
  ],
  "surface_kind": "snow",
  "weather": "light_snow",
  "tags": ["track", "snow", "medium_difficulty"]
}}
```

Ensure `checkpoints` form a closed loop (last checkpoint connects back to first at lap complete).

### Add a vehicle

Append to `data/vehicles.json::vehicles`:
```json
{"sports_coupe": {
  "display_name": "Sports Coupe",
  "top_speed": 220,
  "acceleration": 0.85,
  "handling": 0.7,
  "weight": 0.6,
  "vehicle_kind": "car",
  "sprite_ref": "sprites/vehicles/sports_coupe",
  "components": ["Health(100)", "Velocity(0, 0)"],
  "tags": ["vehicle", "car", "sport"]
}}
```

Stat ranges in seed: top_speed 80-250, acceleration 0.3-1.0, handling 0.4-0.95, weight 0.3-1.0.

### Swap kart-style ↔ sim-style

- **Kart**: `data/powerups.json` has boost / shell / banana. `PickupLoop` trigger_tag is `powerup_box`. WinCondition is "first_place_after_N_laps".
- **Sim**: rename `powerups.json` → `tuning.json` with engine_upgrade / tires / aero entries. Remove `PickupLoop` from Race.ts. WinCondition becomes "finish_under_time".

### Tune AI difficulty

Edit `data/racers.json::racers` → AI kind:
- `fixed` — constant speed, predictable pathing (easy mode).
- `rubberband` — slows when ahead, speeds up when behind (Mario Kart default — dramatic finishes).
- `adaptive` — learns player racing line over laps (hard mode).

## Directory layout

```
racing/
├── package.json, tsconfig.json, vite.config.ts
├── index.html
├── src/
│   ├── main.ts
│   └── scenes/
│       ├── Title.ts      # splash + track select
│       ├── Race.ts       # race loop — 8 mechanics
│       └── Finish.ts     # results
└── data/
    ├── config.json            # starting_track / laps_per_race / racer_count
    ├── tracks.json            # 3-5 tracks w/ checkpoints + theme
    ├── vehicles.json          # 4-6 vehicles w/ stat ranges
    ├── racers.json            # player + 3-5 AI racers
    ├── powerups.json          # kart items OR sim tuning parts
    ├── mechanics.json         # 8 mechanic instances
    └── SEED_ATTRIBUTION.md    # essence sources (JOB-T output)
```

## Mechanics prewired (from @engine/mechanics)

- **CheckpointProgression** — lap counter + mid-track respawn if off-track
- **CameraFollow** — vehicle-anchored with look-ahead lerp
- **PickupLoop** — powerup boxes (kart-style) or tuning parts (sim-style)
- **WinOnCount** — finishing N laps triggers Finish scene
- **LoseOnZero** — DNF timer exhaustion triggers failure
- **HUD** / **ChipMusic** / **SfxLibrary** — universal scene glue

## Seed attribution

Content from `1986_out_run` (pseudo-3D scrolling + timer-based checkpoint chase + Ferrari Testarossa archetype), `1992_super_mario_kart` (kart items + item boxes + Rainbow Road + rubberband AI + Lakitu), `1997_gran_turismo` (vehicle stat ranges + handling physics + tuning categories) via JOB-T. See `data/SEED_ATTRIBUTION.md`.

## Running

```bash
npm install
npm run dev  # localhost:5181
```
