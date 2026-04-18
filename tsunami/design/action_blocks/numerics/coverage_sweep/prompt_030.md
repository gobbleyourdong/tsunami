# Prompt 030 — Simulation puzzle (The Incredible Machine / Zachtronics-style)

**Pitch:** arrange physics objects to achieve a goal state (e.g., guide the ball into the bucket); limited parts inventory; start simulation → watch it play out → reset if failed; complex levels with chains of object interactions.

**Verdict:** **awkward (close — primitives mostly in v0 + v1 bundle)**

**Proposed design (sketch):**
- archetypes: `goal_state_checker` (triggers win when matched), `part_type_*` (ropes, pulleys, balloons, cats, gears, etc.), `fixed_obstacle_*` (walls, floors)
- mechanics: `PartInventory` (limited parts to place), `PlacementMode` (pre-simulation authoring), `SimulationPlay` (run/reset toggle), `WinOnTrigger` (goal matched), `Physics` (existing engine — part interactions)

**Missing from v0:**
- **Author-mode vs. run-mode split** — player arranges parts in a "build mode", then presses play. v0 has no "editor mode" concept at runtime.
- **Limited part inventory** — "you have 3 ropes, 2 balloons, 1 gear. Use them all or fewer." Resource-like but per-part-type. Parts placed consume inventory.
- **Snap-to-grid placement vs. free placement** — some games grid, others freeform. Both needed.
- **Deterministic replay** — reset to start state, preserve part placement, re-run. Requires state snapshot at run-start.
- **Goal-state check** — "when THE ball is in THE bucket" — specific instance-pair contact. v0 has generic contact triggers; this is specific instance referencing.

**Forced workarounds:**
- Author mode as a pre-game scene, run mode as the "actual" scene. Flow steps toggle. Clunky but works.
- Part inventory via Resource generic (v1).
- Goal check via specific-instance contact trigger. Needs `instance_ref` on triggers.

**v1 candidates raised:**
- `AuthorRunMode` — schema-level toggle between "player places" and "simulation runs". Applies to sim-puzzle, Tower Defense (place phase vs. wave phase), Lemmings (role-assignment pre-release).
- `PartInventory` — per-type `Resource` with consume-on-place semantics
- `DeterministicReplay` — state-snapshot + reset + re-run cycle
- `InstanceRefTrigger` — trigger between specific named instance pair (`ball_1` × `bucket_1`)

**Stall note:** sim puzzle is close to Tower Defense structurally — both have placement-then-simulate phases. Adding `AuthorRunMode` would simultaneously unlock both genres plus RTS-lite (build then fight). High-composability addition. The Zachtronics-style (SpaceChem, Opus Magnum, Shenzhen I/O) deep-programming variants push further into DSL-as-authoring territory — for now, just physics-puzzle is in scope.
