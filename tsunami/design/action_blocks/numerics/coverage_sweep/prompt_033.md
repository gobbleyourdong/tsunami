# Prompt 033 — Horizontal shmup (R-Type / Gradius-style)

**Pitch:** horizontal scrolling; player ship gathers power-ups to grow weapons (beams, options, shields); boss at end of each stage; death drops power to 0.

**Verdict:** **expressible with caveats (shmup bundle reuse + power-up system)**

**Proposed design (sketch):**
- archetypes: `player_ship` (rail controller), `enemy_*` (formation-spawned), `power_up` (pickup, typed), `boss` (BossPhases)
- mechanics: `AutoScroll` (v1, horizontal variant), `WaveSpawner` ✓, `FormationPath` (v1), `BossPhases` ✓, `LoseOnZero` (1-hit death), `PickupLoop` ✓ (power-ups), `PowerUpTier` (not in v0 — player weapon escalation ladder), `BulletPattern` (v1)

**Missing from v0:**
- **`PowerUpTier`** — player has a tier counter; each power-up increments tier; each tier unlocks/upgrades a specific weapon. Death resets tier to 0. Generalization: `ArchetypeTier` — numeric component that unlocks behaviors at thresholds.
- **Options / satellites** — secondary archetypes that orbit the player and fire alongside. `OrbitSatellite` archetype with attached-to + follow behavior. Generalizes to RPG summons, familiars.
- **Force pod (R-Type's Force)** — attachable/detachable power module that extends the ship or detaches as shield. Complex but specific.
- **Checkpoint respawn to last stage (permadeath from boss)** — CheckpointProgression variant with power-tier reset rules.

**Forced workarounds:**
- `PowerUpTier` as a Score component with branching BT on thresholds — hack.
- Options via separate archetypes with `ai:"follow_with_offset"` — works but needs the "follow" BT.

**v1 candidates raised:**
- `PowerUpTier` / `ArchetypeTier` — threshold-gated behavior unlocks
- `OrbitSatellite` — attached archetype with offset + firing behavior
- Shmup genre largely confirmed — similar to prompt_018 bullet-hell but with progressive-power twist

**Stall note:** horizontal shmup joins vertical-shmup (018) and bullet-hell in the shmup cluster. All three share `AutoScroll` + `WaveSpawner` + `BossPhases` + `BulletPattern`. Genre-group makes strong v1 target: 3 games in 1 bundle.
