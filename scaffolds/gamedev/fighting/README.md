# Tsunami Gamedev — Fighting Scaffold

2D and 3D fighting-game scaffold covering three canonical lineages: Street Fighter II (2D Capcom), Mortal Kombat II (2D Midway), Tekken 3 (3D Namco). Ships 6 fighters + 6 stages + full move tables + HUD/combat mechanics prewired.

## Customization paths

### Add a fighter
Append to `data/characters.json`:
```json
{"new_fighter": {
  "display_name": "New Fighter",
  "archetype": "grappler",
  "health": 1100,
  "stun": 110,
  "portrait_sprite_ref": "sprites/portraits/new_fighter",
  "fighter_sprite_ref": "sprites/fighters/new_fighter",
  "stage_affinity": "tokyo_rooftop",
  "move_list_ref": "new_fighter_moveset",
  "components": ["Health(1100)", "Resource('stun',110)", "Resource('super_meter',0)"],
  "tags": ["fighter", "grappler"]
}}
```

Then add a corresponding moveset entry in `data/moves.json` with the fighter's moves keyed by name → {input, startup, active, recovery, damage, hitbox}.

### Add a stage
Append to `data/stages.json` with background sprite + music ref + boundary type.

### Change match rules
Edit `data/config.json::match_rules`:
- `rounds_per_match` (default 3)
- `round_timer` (default 99s)
- `win_condition` (best_of_n)
- `super_meter_max` (default 100)

### Add a move to an existing fighter
Edit `data/moves.json` → fighter's moveset → append a move with input notation (numpad `236P` = qcf+punch; Tekken `1/2/3/4` = limbs) + startup/active/recovery frames + damage + hitbox spec.

## Directory layout

```
fighting/
├── package.json, tsconfig.json, vite.config.ts
├── index.html
├── src/
│   ├── main.ts
│   └── scenes/
│       ├── CharSelect.ts   # roster grid
│       ├── VsScreen.ts     # portrait splash
│       ├── Fight.ts        # combat loop (ComboAttacks + AttackFrames + HUD + CameraFollow)
│       └── Victory.ts      # win screen
└── data/
    ├── config.json          # mode, match_rules, super_meter
    ├── characters.json      # 6 fighters
    ├── moves.json           # per-character move tables with frame data
    ├── stages.json          # 6 stages with affinities + fatality flags
    └── SEED_ATTRIBUTION.md  # essence sources
```

## Mechanics prewired (from @engine/mechanics)

- **ComboAttacks** — input sequence → move dispatch (reads move_list_ref)
- **AttackFrames** — startup/active/recovery with hitbox activation timeline
- **HUD** — health bars + round timer + round indicators + super meter
- **CameraFollow** — midpoint tracking between fighters

Available to wire per-genre but not default-mounted: **StatusStack** (for buff/debuff), **BossPhases** (for arcade-mode bosses), **SfxLibrary** (for hit/block/whiff SFX).

## Seed attribution

Content from `1991_street_fighter_ii` (Ryu/Ken/Chun-Li + 3 stages + numpad notation), `1993_mortal_kombat_ii` (Scorpion/Raiden + 2 stages + stage-fatality), `1997_tekken_3` (Jin + Tokyo Rooftop + 4-limb notation) via JOB-E. See `data/SEED_ATTRIBUTION.md`.

## Running

```bash
npm install
npm run dev  # localhost:5175
```
