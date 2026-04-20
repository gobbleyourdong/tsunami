# Ninja Garden — Cross-Genre Canary #2

> **Role**: second architecture-correctness gate for the gamedev framework. Paralleling `magic_hoops/` (which proved sports+fighting+RPG composes cleanly), this scaffold proves the abstractions also handle **sandbox + action + stealth**.
>
> If this scaffold compiles + tests clean **without adding any new mechanic types**, the framework has passed its second cross-genre composition test.

## Concept

Terraria × Ninja Gaiden × Shinobi mashup:
- Open 2D sandbox (dig / build / craft, procedural terrain, day-night cycle with phase-dependent encounter economy)
- Sidescrolling shinobi action (wall-grab + double-jump + combo attacks + stealth kills + boss gauntlet)
- Ninja tool economy (shuriken / kunai / smoke bomb / grappling hook / kusarigama) with ammo + crafting-bench recipes
- Day phase favors open combat; night phase favors stealth with a 1.5× kill-XP bonus

## What this proves

Every mechanic wired in `src/scenes/Match.ts` already exists in `@engine/mechanics`:

| Heritage | Mechanics |
|---|---|
| Sandbox (Terraria) | `ProceduralRoomChain`, `InventoryCombine` |
| Action (Ninja Gaiden) | `ComboAttacks`, `AttackFrames`, `PhysicsModifier` |
| Stealth (Shinobi/MGS) | `VisionCone`, `ItemUse`, `LockAndKey` |
| Universal scene glue | `BossPhases`, `CheckpointProgression`, `CameraFollow`, `HUD` |

**Zero new mechanic types needed.** Same assertion shape as magic_hoops, different composition.

## Architectural invariants this canary tests that magic_hoops doesn't

1. **Procedural-terrain persistence across scene boundaries** — `ProceduralRoomChain` with `persist_modifications=true`. magic_hoops has one static arena; ninja_garden generates + persists terrain.
2. **Stealth/combat co-resolution on the same enemy** — `VisionCone` + `ComboAttacks` composing on each enemy entity. The same guard can be silently eliminated (night + full stealth meter) OR brawled openly (day + combo attacks). Tests that two mechanics can both mount AttackFrames-relevant state on a single entity without collision.
3. **Day/night phase modifier flipping encounter economy without scene swap** — arena.json's `open_combat_phase_modifier` applies alert-decay + loot multipliers per phase. Tests that scene-scoped state can toggle game-loop economy without scene_manager transitions.

## Concept → scene wiring

Single `Match` scene (no scene flow — canary is single-screen like magic_hoops). The scene mounts 12 mechanics and exposes `mechanicsActive()` + `getWinConditionKind()` for the canary test to assert against.

## Directory layout

```
ninja_garden/
├── package.json
├── tsconfig.json         # @engine alias (three levels up — deeper nesting than sibling scaffolds)
├── vite.config.ts        # port 5182
├── index.html
├── src/
│   ├── main.ts
│   └── scenes/
│       └── Match.ts      # 12 mechanics across 3 heritages
└── data/
    ├── config.json             # meta + starting_biome + day_night_cycle_sec + architectural-invariants comment
    ├── player.json             # shinobi with chakra + stealth_meter + noise_radius + craft_recipes_known
    ├── enemies.json            # 6 archetypes (grunt / ninja / samurai / yokai / boss-minion / shrine-sentinel)
    ├── biomes.json             # 4 biome templates (forest_outskirts / stone_caverns / shrine_canopy / volcanic_depths)
    ├── tools.json              # 5+ ninja tools + craftable items
    ├── bosses.json             # 3 bosses w/ multi-phase patterns
    ├── arena.json              # world_size + day_night cycle + phase-modifier matrix
    ├── rules.json              # compound_any win condition + persistence flags + stealth-kill economy
    └── mechanics.json          # 12 mechanic instances — sister-authored exactly per JOB-U composition target
```

## Running

```bash
npm install
npm run dev  # localhost:5182
```

## Architecture canary result

See `scaffolds/.claude/GAMEDEV_PHASE_TRACKER.md` cycle 24 for the verdict:
whether this scaffold built clean on first try determines whether the
abstractions are correctly factored for sandbox + action + stealth
composition.

If this needs NEW Layer 1 components or Layer 2 mechanics to compose, go
fix those abstractions — not this scaffold.
