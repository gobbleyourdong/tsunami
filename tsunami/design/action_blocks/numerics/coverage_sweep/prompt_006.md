# Prompt 006 — Zork-style text adventure (IF)

**Pitch:** parse typed commands ("take lamp", "go north"); navigate rooms; inventory; puzzles gated on items; win on treasure collected.

**Verdict:** **impossible**

**Proposed design (sketch):**
- archetypes: `player` (no mesh, no controller), `room` (location nodes), `item` (takeable), `npc` (dialogue)
- mechanics: would want `RoomGraph`, `Parser`, `InventoryActions`, `DialogTree` — none exist in v0

**Missing from v0:**
- **Parser front-end** — input is typed natural language, not keyboard axes. `KeyboardInput` + `ActionMap` are wrong abstraction entirely.
- **Room graph as first-class topology** — no spatial position; `room_a north → room_b` is graph edge, not vector. v0 assumes spatial scene.
- **Textual rendering** — no canvas mesh for any entity. `HUD` mechanic is widget-over-canvas; here the entire "scene" is text output.
- **Inventory actions** (`use X on Y`, `examine X`) — need verb × noun × noun dispatch table.
- **State flags as world state** — "lamp is lit", "troll is dead" — game is a tuple of flags, not a scene.

**Forced workarounds:**
- Treat rooms as scenes, transition via SceneManager on parser keyword. Hack — wastes scene-transition cost per command, loses state coherence.
- Parser implemented in a single custom component on the `player` archetype. Entire game logic in one blob. Defeats the schema.

**v1 candidates raised:**
- `TextAdventureRoot` — whole new schema mode (or separate schema); game-as-graph not game-as-scene
- `Parser` — verb/noun tokenizer → action dispatch
- `WorldFlags` — boolean/enum world-state component, queriable in conditions
- `RoomGraph` (noted earlier) — specific instantiation: nodes + directional edges + descriptions

**Stall note:** IF is a different schema entirely. v0 is spatial-simulation-first; IF is state-graph-first. Trying to bolt IF onto v0 via archetype hacks would produce the worst of both. Recommend: **IF is a separate design schema**, not a v1 extension. Flag for operator decision — stay spatial, or add a second schema kind?
