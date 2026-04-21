# Bullet Hell RPG — cross-genre scaffold

**Pitch:** vertically-scrolling bullet-hell arcade + persistent RPG progression
(Cave lineage × Phantasy Star lineage). One run at a time; gear and levels
carry over. Architecture canary — proves bullet-hell + rpg composes from
`@engine/mechanics` without new primitives.

## Heritage mix (13 mechanics across 4 genre buckets)

| Heritage    | Mechanics                                                         |
|-------------|-------------------------------------------------------------------|
| bullet-hell | `BulletPattern` × 5 enemy archetypes, `WaveSpawner`, `BossPhases`, `ScoreCombos`, `Difficulty` |
| rpg         | `LevelUpProgression`, `EquipmentLoadout`, `StatusStack`           |
| fighting    | `AttackFrames` (player shot hitbox timeline — same primitive as Fight.ts jab/punch) |
| universal   | `CameraFollow`, `HUD`, `LoseOnZero`, `CheckpointProgression`      |

Four heritages, single scene. If a new cross-genre combo needs a new mechanic,
the abstractions are leaking — push the fix to `scaffolds/engine/src/mechanics/`,
not this scaffold.

## Quick start

```bash
npm install
npm run dev        # localhost:5183
npm run check      # tsc typecheck against @engine/mechanics
```

## Customize

- **Add an enemy type** → add to `data/enemies.json`, reference in
  `data/waves.json`. `BulletPattern` auto-mounts one per enemy archetype.
- **Add a boss phase** → append to `bosses.json::the_archon.phases`.
  `BossPhases` mechanic reads the array.
- **Add equipment** → add to `data/equipment.json` with a slot. Unlock
  it via `progression.json::level_rewards`.
- **Swap scroll direction** → `config.json::run.mode`. Horizontal-scroll
  needs camera deadzone tuning in `src/scenes/Run.ts`.

## Don't

- Don't add new mechanic files here. The scaffold's whole role is proving
  composition is enough. If you find yourself reaching for one, that's a
  signal Layer 1/2 needs an extension, not that this scaffold needs a
  local special case.
- Don't remove mechanics from `Run.ts::setup()` to simplify — the canary
  test verifies ≥ 3 heritages are represented. Reducing to one heritage
  makes this scaffold redundant with the plain `fps` / `fighting` /
  `jrpg` scaffolds.

## Anchors

`Touhou`, `DoDonPachi`, `Mushihimesama`, `Soldner-X`, `CrossCode`
(for the RPG-meets-arcade pacing), `Vampire Survivors` (for the
gear-drives-builds feel on a simpler input surface).

## Canary

`scaffolds/engine/tests/bullet_hell_rpg_canary.test.ts` — verifies
tree, data shape, scene imports ONLY from `@engine/mechanics`, every
`tryMount()` name is in the registry, and ≥ 3 heritages are represented.
