# Tsunami Gamedev — Beat-em-up Scaffold

Beat-em-up scaffold covering three canonical lineages: Final Fight (1989 — CPS-1 genre-definer with Haggar/Cody/Guy roster + Belger boss + Metro City), Streets of Rage 2 (1992 — refined 4-character roster + grab-specials + co-op), TMNT Arcade (1991 — 4-player co-op beat-em-up). Ships 3 brawler archetypes + 6-8 enemies + 4-6 stages + grab/special/throw move tables + ComboAttacks/WaveSpawner prewired.

## Scene flow

`Title → Stage → GameOver → (Title on continue-timer expiry OR restart)`

- **Title** — splash + character select. Mounts `ChipMusic` + `HUD`.
- **Stage** — brawler gameplay loop. Mounts `ComboAttacks` (per-char moveset) + `AttackFrames` (startup/active/recovery) + `WaveSpawner` (position-gated spawns — beat-em-up canonical) + `CameraFollow` (locked-forward, ring-arena-lock on boss) + `PickupLoop` + `HUD` + `LoseOnZero` + `WinOnCount` + `SfxLibrary`.
- **GameOver** — all brawlers KO'd with no continues. Arcade 10s continue-timer — insert coin or reset.

## Customization paths

### Add a brawler

Append to `data/characters.json::characters`:
```json
{"new_brawler": {
  "display_name": "New Brawler",
  "archetype": "speed_fighter",
  "health": 100,
  "sprite_ref": "sprites/brawlers/new_brawler",
  "components": ["Health(100)", "Resource('stun',0)", "Resource('super_meter',0)"],
  "tags": ["brawler", "playable"]
}}
```

Then add a moveset in `data/moves.json` with attacks keyed by name + input + startup/active/recovery frames.

### Add an enemy

Append to `data/enemies.json::enemies`:
```json
{"knife_grunt": {
  "display_name": "Knife Grunt",
  "hp": 25,
  "attack_kind": "knife_thrust",
  "drop_table": ["knife", "jewels"],
  "sprite_ref": "sprites/enemies/knife_grunt",
  "components": ["Health(25)", "Velocity(1.2, 0)"],
  "tags": ["enemy", "mid_tier"]
}}
```

Archetype kinds in seed: grunt / knife-grunt / fatboy / runner-thief / mid-boss / andore-type heavy.

### Add a stage

Append to `data/stages.json::stages`:
```json
{"stage_4_rooftop": {
  "display_name": "Rooftop",
  "scroll_length": 1200,
  "boss_gate_at": 1000,
  "mid_boss": "abigail",
  "waves": [
    { "trigger_x": 200, "spawn": ["grunt", "grunt", "knife_grunt"] },
    { "trigger_x": 600, "spawn": ["fatboy", "runner_thief"] }
  ],
  "bg_sprite": "sprites/stages/rooftop",
  "music_ref": "rooftop_theme",
  "tags": ["stage", "act_4"]
}}
```

### Tune difficulty

Edit `data/config.json::difficulty` (easy/normal/hard) — affects enemy HP scale + spawn density.

## Directory layout

```
beat_em_up/
├── package.json, tsconfig.json, vite.config.ts (port 5186)
├── index.html
├── src/
│   ├── main.ts
│   └── scenes/
│       ├── Title.ts      # press-start + char-select
│       ├── Stage.ts      # 9 mechanics, locked-forward scroll
│       └── GameOver.ts   # arcade continue-timer
└── data/
    ├── config.json            # starting_stage / starting_character / lives_per_continue / difficulty
    ├── characters.json        # 3 playable brawler archetypes
    ├── enemies.json           # 6-8 enemy archetypes w/ drop tables
    ├── stages.json            # 4-6 stages w/ position-gated waves + boss-gate
    ├── moves.json             # per-character combos + grab + special + throw
    ├── pickups.json           # 6-8 ground items
    ├── mechanics.json         # 9 mechanic instances
    ├── rules.json             # co-op / continues / arcade-continue-timer / boss-gate
    └── SEED_ATTRIBUTION.md    # essence sources (JOB-INT-7)
```

## Mechanics prewired (from @engine/mechanics)

- **ComboAttacks** — per-character combo chains (3-hit punch / 3-hit kick / grab-into-throw / special)
- **AttackFrames** — startup/active/recovery frame windows
- **WaveSpawner** — position-gated spawns (enemies appear when scroll crosses trigger_x)
- **CameraFollow** — locked-forward scroll, ring-arena-lock on boss-gate
- **PickupLoop** — ground items (knife/pipe/chicken/jewels)
- **HUD** / **LoseOnZero** / **WinOnCount** / **SfxLibrary** — universal scene glue

**Proposed-but-unused** (from sister JOB-Y mechanic proposals) — scaffold runs without them but would tighten the fit if promoted to MechanicTypes:
- `SideScrollBeatEmUpStage` (explicit stage-scroll mechanic vs CameraFollow param-mode)
- `CoopSharedScreen` (2P/4P local co-op cam)
- `ArcadeContinueTimer` (GameOver 10s countdown)
- `BreakableEnvironmentObjects` (phone-booth / crate pickups)
- `SelfDamagingDesperation` (low-HP desperation move)

## Seed attribution

Content from `1989_final_fight` (Cody/Guy/Haggar + Belger + Metro City + canonical genre definer), `1992_streets_of_rage_2` (4-char roster + grab-specials + co-op refinement), `1991_turtles_in_time` or `1991_the_simpsons_arcade_game` (4-player co-op reference) via JOB-INT-7. See `data/SEED_ATTRIBUTION.md`.

## Running

```bash
npm install
npm run dev  # localhost:5186
```
