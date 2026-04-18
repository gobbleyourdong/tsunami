# Prompt 024 — Roguelite (Hades / Dead Cells-style)

**Pitch:** real-time action combat through procedurally-arranged rooms; die and return to hub; hub persistence (upgrades bought with collected resources) while per-run state resets; story advances across runs.

**Verdict:** **expressible but incomplete — close to v0**

**Proposed design (sketch):**
- archetypes: `player`, `enemy_*`, `boss_*`, `room_door` (exit to next room with reward choice), `currency_drop`, `upgrade_station` (hub)
- mechanics: `WaveSpawner` (per room — good fit), `BossPhases` ✓, `LoseOnZero` (per run), `PickupLoop` (currency), `RoomGraph` (v1, procedurally assembled), `Shop` (v1, hub upgrades), `NewGamePlus`-analog (v1, hub persistence with per-run reset), `CheckpointProgression` (hub is the only save)

**Missing from v0:**
- **Procedural room assembly** — rooms drawn from a pool, chained into a run. `ProceduralRoomChain` (generalization of `LevelSequence`).
- **Meta-progression vs. run-progression split** — two persistence layers: per-run (resets) and meta (persists). Schema-level: `PersistenceScope: 'run' | 'meta'` attribute on components.
- **Room exit choice** — player picks between 2-3 rewards mapped to next room. Branching `RoomGraph` with player-choice edges (same as deckbuilder's RouteMap).
- **Build variety from permanent upgrade + temporary boons** — each run accumulates boons that stack. `BoonStack` with decay-on-death.
- **Narrative across runs** — dialogue increments per run. Hades-specific: `DialogueProgression` with per-NPC state counter advanced on contact per run.

**Forced workarounds:**
- Procedural chain as randomized flow — WaveSpawner already randomizes spawn location; extending to "randomized next-room pick" is close. Feasible.
- Meta-vs-run persistence via component tags (some persist, some don't) — cleaner to express as schema attribute.

**v1 candidates raised:**
- `ProceduralRoomChain` — randomized `LevelSequence` with pool + constraints
- `PersistenceScope` attribute on components/mechanics — `'run' | 'meta'`
- `RoomExitChoice` — branching next-step with player selection (overlap with deckbuilder's RouteMap)
- `BoonStack` — stackable temporary modifiers with stated decay

**Stall note:** roguelite is the closest modern action-genre fit. v0 + 4 additions + the top-10 v1 picks gets to full expressibility. Might be the FIRST post-v0 target if the design track wants a complex game authored. Validates `WaveSpawner` + `BossPhases` + `ScoreCombos` patterns.
