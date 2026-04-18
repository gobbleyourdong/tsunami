# Prompt 018 — Bullet-hell shmup (Touhou / Ikaruga-style)

**Pitch:** vertical scrolling; player ship with tiny hitbox; hundreds of enemy bullets in geometric patterns; graze-for-score; bomb to clear screen; boss patterns with phases.

**Verdict:** **expressible with caveats**

**Proposed design (sketch):**
- archetypes: `player_ship` (rail controller, vertical-locked movement), `enemy_fighter` (scripted path), `boss` (stationary with BossPhases), `bullet_*` (many kinds — straight, homing, spiral, laser)
- mechanics: `WaveSpawner` (partial — enemy bursts), `FormationPath` (noted in Galaga), `BossPhases` ✓, `LoseOnZero` (1-hit death), `ScoreCombos` (graze streak), `HUD`

**Missing from v0:**
- **Bullet pattern authoring** — `BulletPattern: 'radial(16)'`, `'spiral(5rpm)'`, `'aimed_at_player'`. A DSL or parameter-heavy spawner. Could live inside `FormationPath` but deserves its own primitive.
- **Dual-hitbox archetype** — player has a small scoring hitbox + larger graze hitbox. Same as SF2 hitbox/hurtbox observation.
- **Screen-clear bomb** — consumable that destroys all bullet archetypes on screen. `ScreenClearEffect` action.
- **Graze detection** — continuous proximity to bullet without collision — awards score. Proximity trigger, not contact trigger.
- **Vertical auto-scroll** — camera moves at fixed rate; spawners trigger on camera Y. `AutoScroll` mechanic + scroll-triggered `FormationPath`.
- **1-hit death** — Health(1) + LoseOnZero works; but lives system with respawn-after-delay + temporary invuln is common. `RespawnWithInvuln` mechanic.

**Forced workarounds:**
- Bullets as archetype with `ai:"bt:straight_fly"` — works but per-bullet BT authoring is tedious for 50+ pattern types.
- Screen clear as a `WinOnCount(0)` + despawn trigger — hack.

**v1 candidates raised:**
- `BulletPattern` mechanic — parameterized pattern generator (radial, spiral, aimed, laser)
- `AutoScroll` — camera + spawner-gate on scroll position
- `ProximityTrigger` — distance-threshold without contact (graze, radar detection)
- `DualHitbox` archetype spec (scoring + damage hitboxes)
- `RespawnWithInvuln` — checkpoint respawn with temporary invuln `TimedStateModifier`

**Stall note:** shmups are barely out of v0 reach. WaveSpawner + BossPhases + ScoreCombos + FormationPath cover 60%. Adding `BulletPattern` + `AutoScroll` + `ProximityTrigger` gets to ~85%. Genre is achievable with modest v1 investment. Worth prioritizing — bullet hell indie scene is active.
