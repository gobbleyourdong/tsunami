# Prompt 031 — Flight combat sim (Ace Combat / X-Wing-style)

**Pitch:** 3rd-person aircraft; pitch/yaw/roll + throttle; dogfights with enemy planes; missile locks; campaign missions with objectives; radar HUD.

**Verdict:** **awkward → expressible with v1 + vehicle bundle**

**Proposed design (sketch):**
- archetypes: `player_plane` (aircraft controller), `enemy_plane` (dogfight AI), `missile_*` (seeker + dumb variants), `ground_target_*`
- mechanics: `ArchetypeControllerSwap` (v1, board-the-plane), `VehicleController` variant (`aircraft` — pitch/yaw/roll/throttle, not wheel-based), `LockOn` (target-acquisition primitive), `WaveSpawner` (enemy waves), `MissionGraph` (v1, campaign), `HUD` (radar + target-box), `WinOnCount` (objectives), `LoseOnZero`

**Missing from v0:**
- **`AircraftController`** — 6DOF inputs (3 rotation axes + throttle). Different from `VehicleController` (wheel-based) and `platformer`/`fps`. Subtype of vehicle.
- **Lock-on targeting** — cursor tracks target with assist; missile seeker follows target until lost. `LockOn` mechanic: range + cone + breakable lock.
- **Seeker missile archetype** — spawned projectile with pursuit AI on named target. Extension of `ai:"chase"` with designated target on spawn.
- **Radar HUD** — position of all enemies + allies in a circular minimap. `RadarHUD` variant.
- **Chaff / flares** — resource consumables that break missile lock. Event-based Resource consumption (noted elsewhere).

**Forced workarounds:**
- Aircraft as `VehicleController` + custom pitch/yaw on top — partial; misses roll.
- Lock-on via proximity trigger — loses cone-of-view requirement.

**v1 candidates raised:**
- `AircraftController` — adds to vehicle bundle (alongside kart, sim car, boat)
- `LockOn` mechanic — generalizes to RPG tab-target, stealth FPS paintball-tag
- `SeekerProjectile` — pursuit projectile on spawn-targeted archetype
- `RadarHUD` — position-plot HUD variant

**Stall note:** flight sim is a *vehicle-family* extension. If v1 ships `ArchetypeControllerSwap` + `VehicleController` with subtypes (car/kart/aircraft/boat/mech), flight sim is reachable. The aerial-combat-specific primitives (lock-on, radar, missiles) are small. Full sim-grade flight (X-Plane, DCS) remains out-of-scope — authentic flight physics is its own project.
