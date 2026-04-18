# Game 022 — Grand Theft Auto III (2001, PS2)

**Mechanics present:**
- Open-world city with freeform exploration — **not in v0** (streaming / open-world schema)
- Vehicle enter/exit — **not in v0** (ArchetypeControllerSwap / VehicleEntryExit)
- Wide vehicle roster (cars, trucks, boats, motorcycles) — archetype family with shared VehicleController + per-type params
- Mission giver NPCs (stand in specific location, trigger cutscene + mission) — Hotspot + Dialog + scripted flow
- Mission success/failure → story progress — MissionGraph
- Wanted level (0–6 stars, escalating police response) — scaled AlertState
- Pedestrian AI (walk, flee, react to violence) — BT library
- Radio in vehicles (switchable stations) — AudioStreamChannel
- Weapons with ammo and pickup — Inventory + Ammo resource
- Combat (gunplay + melee) — standard Health + WaveSpawner adversarial
- Day/night cycle — DayNightClock ✓
- Save safe-houses — checkpoint with restrictive placement
- Hidden packages (collectible for reward) — PickupLoop variant (one-time)
- Unique stunts (named bonus jumps) — NamedTrigger + reward
- Side activities (taxi, vigilante, ambulance, firefighter) — EmbeddedMinigame variations
- Turf / rampages — bounded mini-challenges within open world
- Radio chatter + news broadcasts responsive to player actions — contextual audio (advanced)
- Cheat codes — meta-mechanic
- Pedestrian density / traffic spawner — ambient world system

**Coverage by v0 catalog:** ~2/17

**v1 candidates from this game:**
- Everything in prompt_022 list
- `SafeHouseSave` — checkpoint with placement constraints
- `HiddenPackage` — PickupOnce variant (previously noted in RE)
- `NamedStuntTrigger` — specific geometry-triggered one-time achievement
- `SideActivity` — EmbeddedMinigame with reward on completion

**Signature move:** **the juxtaposition of freedom and mission**. The same world used for 100 linear missions and for aimless play. Authors a single world with many opt-in activities layered on it. Composition of:
- One shared open world (shared archetypes + streaming)
- Many small hub-and-spoke mission chains (MissionGraph)
- A small number of always-available activities (EmbeddedMinigame instances)

This is the method's emergence thesis at the open-world scale — v0's composition approach scales here once `VehicleEntryExit` + `MissionGraph` + `EmbeddedMinigame` (all v1) are in place.
