# Observation 008 — Puzzle genre ≠ grid mode; correction to note_002

**Source:** game_024 Lemmings. Lemmings is a puzzle game that is NOT
grid-based and NOT turn-based. Movement is continuous, time is real-
time, the puzzle is "assign roles to a crowd to reshape the path."

**Correction to note_002:** grid-mode unlocks GRID-BASED puzzle games
(Sokoban, Tetris, Lights Out, Sudoku, NetHack). It does NOT cover all
puzzle games. Real-time continuous puzzle games (Lemmings, Pikmin,
Braid per prompt_023) stay within v0's real-time assumption (note_005
#1) and need different v1 primitives:

- `RoleAssignment` (runtime BT swap on instance) — Lemmings
- `CrowdSimulation` (many allied archetypes with ambient behavior) —
  Lemmings, Pikmin
- `TimeReverseMechanic` (record/playback) — Braid
- `PhysicsModifier` (toggle gravity/time) — Braid, VVVVVV
- `PuzzleObject` (mutable world object) — Myst, Lemmings terrain

**Implication:** v1 should target both "grid-mode puzzle" (via
note_002 extensions) AND "continuous puzzle" (via these real-time
mechanics) as separate bundles. They don't share primitives.

**For the gap_map.md:** "puzzle genre" as a single line-item is
misleading. Break into:
- Grid-puzzle: Sokoban, Tetris, NetHack, Sudoku (needs grid-mode)
- Continuous-puzzle: Lemmings, Pikmin, Braid, Limbo (needs RoleAssignment, TimeReverse, PhysicsModifier)
- Adventure-puzzle: Myst, Monkey Island, RE (needs PuzzleObject, Hotspot, WorldFlags)

Three sub-genres, three different primitive sets. Confirms the overall
finding that v0 is genre-narrow — "puzzle" alone needed 3 distinct v1
bundles for full coverage.

**Design-track implication:** sequence v1 work by sub-genre, not by
umbrella genre. Pick the sub-genre with highest leverage first:
probably *adventure-puzzle* because PuzzleObject + HotspotMechanic +
WorldFlags overlap with narrative/VN/horror and multiply hardest.
*Continuous-puzzle* second because TimeReverse/PhysicsModifier are
self-contained curiosities that produce distinctive games. *Grid-puzzle*
third despite coverage breadth because the schema-level investment
(grid-mode) is larger than the others.

**Sigma check:** note_002 is not wrong — grid-mode is a valid v1
direction — but its framing was over-broad. Noise keeps (Maps Include
Noise), correction layered on top. Treat note_002 as "one of three v1
puzzle bundles, highest schema cost."
