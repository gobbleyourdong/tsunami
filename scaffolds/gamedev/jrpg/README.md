# Tsunami Gamedev — JRPG Scaffold

Classic JRPG scaffold covering three canonical lineages: Final Fantasy IV (1991 — ATB combat + party of 4), Dragon Quest III (1988 — turn-based combat + overworld travel + shops), Chrono Trigger (1995 — ATB refinement + haste mechanic). Ships 4 party members + 8 world regions + 12 spells + 15 equipment items + full ATB combat prewired.

## Scene flow

`Title → World → Town → Battle → (World on victory/fled, Title on defeat)`

- **Title** — splash + press-start. Mounts `ChipMusic` + `HUD`.
- **World** — overworld. Mounts `WorldMapTravel` (8 regions) + `PartyComposition` + `CameraFollow` + `HUD`. Rolls random encounters per region's `encounter_rate`.
- **Town** — safe hub. Mounts `EquipmentLoadout` + `Shop` + `DialogTree` + `HUD`.
- **Battle** — ATB combat. Mounts `ATBCombat` + `LevelUpProgression` + `HUD` + `LoseOnZero`. Grants XP on victory.

## Customization paths

### Add a party member

Append to `data/party.json::characters`:
```json
{"new_member": {
  "role": "monk",
  "display_name": "New Member",
  "hp": 90, "mp": 30, "speed": 9,
  "level": 1,
  "sprite_ref": "sprites/party/new_member",
  "components": ["Health(90)", "Resource('mana',30)", "Resource('xp',0)", "Resource('level',1)"],
  "equippable_tags": ["monk"],
  "tags": ["party", "monk"]
}}
```

### Add a world region

Append to `data/world_map.json::regions`:
```json
{"new_region": {
  "kind": "dungeon",
  "display_name": "New Dungeon",
  "map_sprite_ref": "sprites/maps/new_dungeon",
  "encounter_rate": 0.12,
  "encounter_table": ["goblin", "skeleton"],
  "connections": ["baron_field"],
  "boss": "new_boss",
  "tags": ["dungeon"]
}}
```

Make sure at least one `connections` entry points to an existing region so the graph stays reachable.

### Add a spell

Append to `data/spells.json::spells`. Follow the canonical target_scope taxonomy: `single_enemy` / `all_enemies` / `single_ally` / `all_allies` / `self`.

### Add an equipment item

Append to `data/equipment.json::equipment` with `slot` ∈ `{weapon, armor, accessory_1, accessory_2, consumable}` and `stat_modifiers: { [stat]: delta }`. `equippable_by_tags` gates who can wear it.

### Swap ATB → turn-based combat

Edit `Battle.ts::setup()`: replace the `ATBCombat` mount with `TurnBasedCombat` and adjust params to `{turn_order: 'speed_desc', party_size: 4, command_menu: [...], can_flee: true}`. Both mechanics expose `startCombat(party, enemies)` + `queueCommand(actor, kind, target)` — the scene hand-off doesn't change.

## Directory layout

```
jrpg/
├── package.json, tsconfig.json, vite.config.ts
├── index.html
├── src/
│   ├── main.ts
│   └── scenes/
│       ├── Title.ts      # press-start splash
│       ├── World.ts      # overworld + WorldMapTravel + PartyComposition
│       ├── Town.ts       # shop + equip menu + dialog
│       └── Battle.ts     # ATBCombat loop + LevelUpProgression
└── data/
    ├── config.json              # starting party/region/combat_style/win_condition
    ├── party.json               # 4 fighters (Cecil/Rydia/Rosa/Edge FF4 heritage)
    ├── world_map.json           # 8 regions (Baron/Mist/Kaipo/Antlion/overworld/Zeromus)
    ├── battles.json             # 5 grunts + 3 bosses + encounter groups
    ├── spells.json              # 12 spells across offense/heal/status trees
    ├── equipment.json           # 15 items across 5 slot types
    ├── mechanics.json           # 9 mechanic instances (ATBCombat + v1.2 cluster)
    └── SEED_ATTRIBUTION.md      # essence sources
```

## Mechanics prewired (from @engine/mechanics)

- **ATBCombat** — real-time ATB meter per combatant, command queue
- **PartyComposition** — roster + active party + formation
- **LevelUpProgression** — XP → level → stat deltas + spell learns
- **WorldMapTravel** — scene-graph traversal with encounter rolls
- **EquipmentLoadout** — per-character slot system + stat-modifier diffs
- **Shop** / **DialogTree** / **HUD** / **LoseOnZero** / **CameraFollow** / **ChipMusic** — universal scene glue

The five `v1.2` mechanics (first four listed above + EquipmentLoadout) all landed in Phase 3; see `scaffolds/.claude/GAMEDEV_PHASE_TRACKER.md` cycles 3 / 10-14 for the runtime history.

## Seed attribution

Content from `1991_final_fantasy_iv` (Cecil/Rydia/Rosa/Edge + Baron/Mist/Kaipo/Antlion regions + Mist Dragon/Antlion/Zeromus bosses + ATB pacing), `1987_final_fantasy` (Fire/Cure/Blizzard spell trinity), `1988_dragon_quest_iii` (XP curve + sleep-status + shop norms), `1995_chrono_trigger` (haste + ATB refinement) via JOB-F. See `data/SEED_ATTRIBUTION.md`.

## Running

```bash
npm install
npm run dev  # localhost:5176
```
