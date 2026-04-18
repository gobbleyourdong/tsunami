# Prompt 008 — Grid-based roguelike (Rogue/NetHack-style)

**Pitch:** procedurally generated dungeon on a grid; turn-based; permadeath; scrolling loot tables; monster variety; line-of-sight.

**Verdict:** **awkward → impossible-without-grid-mode**

**Proposed design (sketch):**
- archetypes: `player` (grid mover), `monster_*` (many types), `item`, `dungeon_tile` (floor/wall/door/stairs)
- mechanics: `GridController` (not in v0), `TurnManager` (not in v0), `ProceduralDungeon` (not in v0), `LineOfSight` (not in v0), `LootTable` (not in v0), `LoseOnZero` (permadeath), `LevelSequence` (dungeon depth)

**Missing from v0:**
- **Turn-based tick** — "every player input = one tick; all enemies move one step." v0 is real-time continuous. Huge structural gap.
- **Procedural layout generation** — BSP dungeon, cellular automata caves. `tilemap_gen.py` exists in engine tools, not wired.
- **Line-of-sight / fog of war** — camera-facing dependent visibility. No v0 mechanic.
- **Loot tables** — weighted random drop on monster death. `PickupLoop` is respawn; this is conditional drop.
- **Permadeath save semantics** — delete save on death, not respawn.
- **Many monster types with simple AIs** — each needs its own behavior. BT library gap (see Pac-Man).

**Forced workarounds:**
- Real-time with tiny `onUpdate` tick + quantized positions — loses turn-based feel entirely.

**v1 candidates raised:**
- `TurnManager` mechanic — gates all updates on player-action events
- `ProceduralDungeon` mechanic — generates a `GridPlayfield` from seed + algorithm param
- `LineOfSight` — visibility mask over grid
- `LootTable` component — weighted drop list
- `PermadeathSave` — erase on death

**Stall note:** roguelikes double down on grid-mode + turn-based. Confirms grid-mode is not a "nice to have" but a second canonical mode alongside realtime. v0 → v1 likely splits schema into `realtime` vs `turn_based` as config.mode values with different compiler paths.
