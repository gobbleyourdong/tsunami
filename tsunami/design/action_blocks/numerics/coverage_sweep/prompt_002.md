# Prompt 002 — Tetris clone

**Pitch:** falling tetromino pieces; clear full rows; speed increases over time; game ends when stack reaches top.

**Verdict:** **awkward → impossible-without-v1**

**Proposed design (sketch):**
- archetypes: `tetromino_piece` (7 variants), `grid_cell` (10×20 playfield)
- mechanics: `FallingBlockDrop` (not in catalog), `LineClear` (not in catalog), `Difficulty` (drop-speed curve), `HUD` (score + lines + level), `LoseOnZero` (stack overflows top)

**Missing from v0:**
- `FallingBlockDrop` — periodic-tick descent + player rotate/shift, with collision halt. Not a tile-rewrite, not a chase AI — its own primitive.
- `LineClear` — row-detection + cascade-remove + shift-above-down. Very specific.
- `RandomBagGenerator` — 7-bag or pure-random piece selection
- Grid playfield as a typed archetype — `grid_cell` feels forced; the playfield is a singleton arena, not per-cell entities.

**Forced workarounds:**
- Represent playfield as a 2D array in a custom component on an invisible `playfield` archetype. `v0` has no "singleton logic container" concept.
- TileRewriteMechanic could in theory encode this, but 7 piece shapes × 4 rotations × 10 columns = 280 rules. Overkill.

**v1 candidates raised:**
- `GridPlayfield` — dedicated archetype kind for fixed-grid game boards with typed cells
- `FallingPieceMechanic` — parameterized by piece shape set, drop curve, control bindings
- `LineClearMechanic` — detects full rows/cols on a GridPlayfield, awards score, shifts remaining

**Stall note:** Tetris is a case where the mechanic IS the game. No amount of archetype composition expresses it. A dedicated mechanic is needed. Same shape for Match-3, Snake, Breakout.
