# Game 005 — The Legend of Zelda: A Link to the Past (1991, SNES)

**Mechanics present:**
- Topdown action-adventure movement — ✅ (controller=topdown)
- Melee attack (sword swing, directional hitbox) — partial (needs directional hitbox, same as Mario)
- Enemy AI (various: chase, patrol, projectile, static) — partial (`ai:"chase"/"patrol"` exist, projectile variants missing)
- Items / inventory (bombs, bow, hookshot, boomerang) — partial (`Inventory` component exists, item-use action blocks don't)
- Dungeon rooms (screen-to-screen transitions) — **not in v0** (room graph / portal)
- Lock and key — ✅ `LockAndKey`
- Dungeon map + compass (meta-items change HUD) — **not in v0**
- Heart containers (max-health upgrades) — **not in v0** (`UpgradeHealth` / `MaxHealthIncrement`)
- Overworld vs. dungeon scenes — ✅ via `flow` scene switching
- NPCs + dialogue — partial (engine has `Dialog` class; `DialogTree` mechanic not in v0)
- Shops (buy items with rupees) — **not in v0** (`Shop` mechanic)
- Light/dark world parallel overworld — **not in v0** (`ParallelWorldLayer`)
- Save/load progression — partial (checkpoint exists; persistent save across sessions isn't spec'd)

**Coverage by v0 catalog:** ~4/13

**v1 candidates from this game:**
- `RoomGraph` (screen-by-screen transitions distinct from full scene changes), `ItemUse` action blocks, `MaxHealthIncrement`, `DialogTree`, `Shop`, persistent-`Save`, `ParallelWorldLayer`

**Signature move:** item-gated progression. Every new item unlocks a previously-inaccessible region. Without `ItemUse` action blocks + `GatedTrigger` (door requires item), the Zelda loop collapses to "kill enemies in rooms."
