# Metroid Runs — Cross-Genre Canary #5

> **Role**: fifth architecture-correctness gate. Tests **per-run-reset vs. persistent-ability-progression** — an axis no prior canary splits.
>
> If this scaffold compiles + tests clean, the framework handles state-lifecycle distinction (per-run transient state wipes on death; persistent state survives).

## Concept

Metroid × Spelunky / Dead Cells:
- Procedurally-generated rooms (ProceduralRoomChain) — different layout each run
- Metroidvania ability-gating (GatedTrigger + LockAndKey) — abilities lock doors until unlocked
- Permadeath-lite (CheckpointProgression wipes HP + inventory on death)
- **Permanent ability progression** — abilities unlocked in one run carry forward to the next

## What this proves

Every mechanic wired already exists in `@engine/mechanics`:

| Heritage | Mechanics |
|---|---|
| Metroidvania (Super Metroid / Castlevania SOTN) | `LockAndKey`, `GatedTrigger`, `PhysicsModifier`, `BossPhases` |
| Roguelike (Spelunky / Dead Cells / Isaac) | `ProceduralRoomChain`, `CheckpointProgression` |
| Universal glue | `ItemUse`, `HUD` |

**Zero new mechanic types needed.**

## Architectural invariants this canary tests that prior canaries don't

1. **Per-run state wipes, persistent state survives** — Run.ts holds persistent abilities / boss_defeats / max_hp_upgrades in a static field that survives `teardown()` + `setup()`. Non-persistent state (HP, current_seed, held consumables) regenerates on every `newRun()`.
2. **Seed-determined layout** — ProceduralRoomChain takes a new seed each run → same seed yields same layout (deterministic). Canary test asserts `newRun(42)` + `newRun(42)` give the same chain.
3. **Ability-count gating** — GatedTrigger fires only when `abilities_count >= threshold`. Couples persistent-state (ability count) to in-run gate-firing. Cross-layer state dependency test.

## Concept → scene wiring

Single `Run` scene. `newRun(seed?)` tears down + re-sets-up with fresh seed while preserving the static `Run.persistent` field. `unlockAbility()` / `recordBossDefeat()` mutate persistent state; next run sees the updated state.

## Directory layout

```
metroid_runs/
├── package.json, tsconfig.json (@engine three levels up), vite.config.ts (port 5185)
├── index.html
├── src/
│   ├── main.ts             # boots Run + rotating ability-slot indicator
│   └── scenes/
│       └── Run.ts          # 8 mechanics + per-run/persistent split + newRun() API
└── data/
    ├── config.json             # starting_seed_policy + first_run_seed
    ├── player.json             # player archetype with persistent_abilities component
    ├── enemies.json            # room-variety archetypes
    ├── abilities.json          # 6-8 unlockable abilities with ability_unlock_gating
    ├── rooms.json              # room_templates keyed by requires_ability
    ├── seeds.json              # 3-5 seed_configurations for determinism demos
    ├── bosses.json             # 2-3 bosses that drop abilities on first defeat
    ├── mechanics.json          # 8-mechanic wiring per JOB-W composition
    └── rules.json              # per_run_reset + persistent_state_whitelist
```

## Essence attribution

- `1986_metroid` / `1994_super_metroid` — ability-gated progression canonical.
- `1997_castlevania_symphony_of_the_night` — metroidvania formula canonical.
- `2008_spelunky` / `2018_dead_cells` — procedural-room-chain + permadeath canonical.
- `2011_binding_of_isaac` — per-run seed determinism canonical.

## Running

```bash
npm install
npm run dev  # localhost:5185
```

## Architecture canary result

See `scaffolds/.claude/GAMEDEV_PHASE_TRACKER.md` cycle 28 for the verdict. If scaffold-smoke passes first try, the state-lifecycle distinction is correctly factored.

If this needs NEW Layer 1 components (e.g. a `PersistentState` component) or Layer 2 mechanics to compose, go fix those abstractions — not this scaffold.
