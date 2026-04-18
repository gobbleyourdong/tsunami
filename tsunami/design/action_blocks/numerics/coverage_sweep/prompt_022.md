# Prompt 022 — Open-world sandbox (GTA-style)

**Pitch:** explore a city freely; drive vehicles you enter; missions triggered by location or NPC; wanted level from police on rule-breaking; radio stations in cars; shops for weapons/clothes/food; side activities.

**Verdict:** **awkward → partially-impossible for full scope**

**Proposed design (sketch):**
- archetypes: `player_avatar`, `vehicle_*` (many), `npc_pedestrian`, `cop`, `mission_giver`, `shop_*`, `interior_building`
- mechanics: `VehicleEntryExit` (seat swap between avatar and vehicle) — **not in v0**, `OpenWorldStreaming` (load/unload chunks), `MissionGraph` (non-linear mission tree), `WantedLevel` (escalating consequence system), `DayNightClock` ✓, `Shop` (noted), `RadioStation` (audio streaming)

**Missing from v0:**
- **Enter/exit vehicle** — player archetype transfers control into/out of a vehicle archetype. Transient controller swap. Schema-level: `ArchetypeControllerSwap` or a `VehicleEntryExit` primitive.
- **Open-world streaming** — load geometry/NPCs in chunks as player moves. Engine-level not mechanic-level; still needs schema awareness (`streamed_world: true` flag?).
- **Mission-trigger graph** — NPCs offer missions based on state flags; missions run scripted sequences; success/failure advances global flags. Combination of `HotspotMechanic` + `WorldFlags` + `LevelSequence` + scripted events.
- **Wanted level (escalating police response)** — `AlertState` (noted, stealth) scaled: more cops spawn at higher wanted levels.
- **Pedestrian AI crowd** — many NPC archetypes with simple behaviors (walk around, flee if shot at). BT library needed (noted).
- **Radio stations** — multiple audio tracks available while in vehicle. `AudioStreamChannel` beyond single `RhythmTrack`.
- **Vehicle physics** — see Gran Turismo; GTA is arcade-physics simpler, but still needs VehicleController.
- **Save houses / checkpoints** — persistent save gap noted elsewhere.

**Forced workarounds:**
- Mission graph as flow steps with conditions — works for linear story but loses the "pick any mission from any NPC" affordance.
- Radio as looped background audio — loses channel-switching.

**v1 candidates raised:**
- `VehicleEntryExit` / `ArchetypeControllerSwap` — transient controller transfer between archetypes (generalizes to getting on horse in RPG, entering mech suit)
- `WantedLevel` / scaled `AlertState` — escalating spawn intensity
- `MissionGraph` — hub-and-spoke mission dispatch (distinct from LevelSequence)
- `AudioStreamChannel` — multi-track audio with swap input

**Stall note:** open-world is a *composition* of many v1 mechanics already on the list. Not a single blocker. The schema-level issue is `ArchetypeControllerSwap`, which is a small but genuinely new primitive. Everything else is additive. With `VehicleEntryExit` + the v1 top-10, GTA-lite is reachable; the open-world streaming piece is engine-level not design-level.
