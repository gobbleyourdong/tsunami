# Prompt 025 — Tower defense (Kingdom Rush / Plants vs Zombies-style)

**Pitch:** enemies walk along fixed path toward base; place defensive towers on buildable tiles; towers cost resources earned from kills; waves escalate; lose when N enemies reach base.

**Verdict:** **awkward (close if grid mode + Resource land)**

**Proposed design (sketch):**
- archetypes: `enemy_*` (path-follower, health, reward-on-death), `tower_*` (static, attack range, rate), `buildable_tile` (clickable zone), `base` (lose condition)
- mechanics: `WaveSpawner` ✓ (waves already supported), `PathFollower` (noted, Galaga formation), `TowerPlacement` (grid-build mode), `Resource` (v1), `Shop`-for-placement (v1, cost per tower), `LoseOnCount` (N enemies reached base → lose), `HUD`

**Missing from v0:**
- **Fixed path for enemies** — enemies follow authored path from spawn to base. `PathFollower` from Galaga's `FormationPath` close fit; parameterize the path as a waypoint list.
- **Grid-placement mode for towers** — click buildable tile → place tower archetype there (consumes resource). Different from "grid game world"; this is grid-as-editor. Relates to Sims `BuildMode` and SimCity zoning.
- **Tower attack behavior** — stationary archetype with range-based auto-attack on enemies in radius. `AutoTurretAttack` primitive. Overlap with `BossPhases.ai:'patrol'` but cleaner as its own thing.
- **Kill-for-currency loop** — enemy death drops currency on map or grants directly. `PickupLoop` with `spawn_on_death` semantics.
- **Wave preview / next-wave info** — HUD variant showing upcoming enemy composition.
- **LoseOnCount** (enemies reaching base accumulator) — v0 has LoseOnZero and WinOnCount; the inverse (lose when archetype count ≥ N) isn't there. Symmetric addition.

**Forced workarounds:**
- Path as `patrol` AI with waypoint list toward base — WORKS. Galaga-style formation paths probably suffice.
- Tower attack as `ai:"patrol"` on radius-0 archetype — partially works; no native "attack nearest enemy in range" primitive.

**v1 candidates raised:**
- `TowerPlacement` / grid-build editor — player-authored archetype placement in-game with resource cost (Sims BuildMode generalization)
- `AutoTurretAttack` — stationary ranged attacker behavior
- `LoseOnCount` — symmetric with WinOnCount (lose when N instances reached state)
- `PathFollower` formal spec (generalize from Galaga FormationPath)

**Stall note:** tower defense is reachable with grid mode + Resource + `AutoTurretAttack` + `LoseOnCount` + `PathFollower`. Three of those overlap with top-10 v1. If v1 implements the top-10 plus these 2 small additions, tower defense is in. Worth tracking — mobile TD is a large indie category.
