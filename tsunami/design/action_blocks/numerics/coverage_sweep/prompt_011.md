# Prompt 011 — Point-and-click adventure (Monkey Island-style)

**Pitch:** click on hotspots to examine/take/use items; dialogue trees with multiple-choice responses; inventory combine; puzzle state tracked across rooms; progress via solving puzzles.

**Verdict:** **awkward → partially-impossible**

**Proposed design (sketch):**
- archetypes: `player` (no controller — cursor driven), `room_bg` per room, `hotspot` (clickable), `npc` (dialogue), `item` (inventory)
- mechanics: `RoomGraph` (not in v0), `DialogTree` (not in v0), `HotspotMechanic` (not in v0), `InventoryCombine` (not in v0), `WorldFlags` (not in v0)

**Missing from v0:**
- **Cursor-driven input** — no `controller:"pointer"` type. Player is not an in-world entity; the cursor is the controller.
- **Hotspots as clickable regions** — v0 triggers fire on archetype contact. Adventure hotspots fire on click. Different affordance.
- **Verb × noun × noun interface** — "USE key WITH door". v0 has no action verbs.
- **Dialogue trees** (see Zork note_001 gap) — branching conversations with state.
- **Item combining** — inventory items → new item via recipe.
- **Persistent puzzle state (WorldFlags)** — "troll_paid", "recipe_book_found" track over entire game. `WorldFlags` component missing.
- **No spatial physics** — adventures are drawn backgrounds, not simulated worlds.

**Forced workarounds:**
- Treat rooms as scenes + hotspots as trigger archetypes that fire on mouse input (if mouse input existed). Loses click-on-scene-region affordance; requires invisible colliders everywhere.
- Dialogue in HUD overlays with flow-condition toggling. Verbose and loses tree structure.

**v1 candidates raised:**
- `PointerController` / `CursorInput` — click/drag, drag-from-inventory-to-world
- `HotspotMechanic` — named clickable regions with enter/examine/use actions
- `DialogTree` mechanic — graph of lines + player choices + state-gated branches
- `InventoryCombine` — recipe table of (item A + item B → item C) rules
- `WorldFlags` (noted in IF observation) — persistent boolean/enum world state, queriable in conditions

**Stall note:** adventures share the IF problem (note_001) in spatial-schema-wrongness. But less bad: adventures DO have spatial scenes (rooms with backgrounds and characters). The click affordance + verb interface is the novel shape, not the state-graph entirely. Recommend note_001's option (C) — narrow dialogue+hotspot support — covers this genre without a full IF schema. Still awkward without cursor input.
