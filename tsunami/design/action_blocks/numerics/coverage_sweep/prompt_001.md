# Prompt 001 — Sokoban-style box-pushing puzzle

**Pitch:** push boxes onto target tiles on a grid; can't pull; level complete when all targets covered.

**Verdict:** **awkward**

**Proposed design (sketch):**
- archetypes: `player` (grid-mover), `box` (pushable), `target_tile` (static trigger), `wall` (static blocker)
- mechanics: `TileRewriteMechanic` (grid movement + push rule), `WinOnCount` (all targets covered → win)
- flow: title → level_1 → level_2 → ... → victory

**Missing from v0:**
- No explicit `GridController` — `controller: "topdown"` is continuous-space, not grid-locked. Sokoban needs discrete tiles with one-input-one-move semantics.
- No `PushRule` / `BlockRule` block. TileRewriteMechanic can express it via rewrite rules but the rule syntax isn't defined yet.
- No `LevelSequence` — progression through hand-authored level files. `flow` is per-scene, not per-level.
- No `UndoHistory` — core Sokoban affordance. Player expects Ctrl+Z.

**Forced workarounds:**
- Simulate grid by quantizing positions in a custom `onUpdate` callback (breaks encapsulation).
- Emit multiple `WinOnCount` mechanics, one per level scene (verbose).

**v1 candidates raised:**
- `GridController` — discrete-move, typed directions, turn-based stepping
- `PushRule` (as Action Block) — when A collides with B in direction D, attempt to move B; fail if blocked
- `LevelSequence` mechanic — declarative list of level definitions, progression on WinCondition
- `UndoHistory` mechanic — records state snapshots on discrete turns

**Stall note:** the catalog assumes real-time 3D/2D continuous. Grid/turn-based is a structural gap, not a parameter gap. TileRewriteMechanic is a placeholder that needs a concrete rule DSL.
