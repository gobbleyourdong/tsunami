# Game 009 — Super Metroid (1994, SNES)

**Mechanics present:**
- Side-scrolling action platformer with morph-ball mode switching — partial (`PlatformerController` gap + state-mode switch)
- Metroidvania room graph (non-linear map, backtracking) — **not in v0** (`RoomGraph` with door/lock types)
- Item-gated progression (missiles, super-missiles, morph ball, grapple) — **not in v0** (`GatedTrigger` + `ItemUse`)
- Map-filling discovery (scan reveals room layout) — **not in v0** (`ExplorationMap` HUD)
- Save rooms (checkpoint archetype) — ✅ `CheckpointProgression` (close)
- Boss phases (multi-stage boss battles) — ✅ `BossPhases` (finally exercised!)
- Energy tanks / missile expansions (upgradeable max resource) — **not in v0** (`MaxHealthIncrement` + generalized `MaxResource`)
- Environmental storytelling (no dialogue, visual narrative) — not mechanical
- Sequence breaks (speed-runner tech) — emergent, not authored
- Health/damage with type resistances — ✅ `Health` + resistances already in engine
- Beam weapons with swappable modes — **not in v0** (`WeaponLoadout` / active-slot mechanic)

**Coverage by v0 catalog:** ~3/10

**v1 candidates from this game:**
- `RoomGraph` with typed doors (normal/missile-lock/super-lock/boss-lock) — generalizes `LockAndKey`
- `ItemUse` / `WeaponLoadout` — active-item system distinct from inventory-of-consumables
- `MaxResource` upgrade mechanic (heart containers, energy tanks, missile packs — same shape)
- `ExplorationMap` HUD variant (auto-revealing map)
- Player-mode switch (morph ball, varia suit) — `PlayerStateSwitch` wrapping StateMachineMechanic

**Signature move:** the item-gate → revisit loop. Find item → backtrack through earlier rooms → access new areas. Without a `RoomGraph` + `GatedTrigger` pair, the whole genre collapses to "linear levels with pickups." First game in Track B to use `BossPhases` — confirming that mechanic's v0 inclusion was right.
