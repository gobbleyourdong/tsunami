# Observation 002 — Grid mode is a schema-level split, not a mechanic

**Sources:** prompt_001 (Sokoban), prompt_002 (Tetris), prompt_008
(Roguelike) — 3/10 coverage entries. Plus retro: game_002 (Tetris),
game_003 (Pac-Man corridors), game_008 (SimCity), game_010 (Chrono
overworld grid). Cross-track: 5 retro + 3 coverage = 8/20 sources.

**Claim:** the absence of grid mode in v0 is not a missing mechanic —
it's a missing **mode**. Multiple mechanics are required simultaneously
(`GridController`, `GridPlayfield`, `TurnManager`, quantized collision,
grid-aware AI) and they depend on schema-level choices (positions are
integers not Vec3, updates are tick-driven not dt-driven, physics is
off).

**Design-track choice needed:**
- (A) Add `mode: 'grid'` to `GameRuntimeConfig`. Compiler routes grid
  mode through a different lowering path; no physics world, tick-based
  updates, grid coordinates.
- (B) Second schema root entirely (`GridDesignScript`). Clean separation
  but duplication overhead on Archetype/Flow/Mechanic shapes that
  should be shared.

**My recommendation:** (A). The overlap with continuous mode is 70–80%
(archetypes, flow, HUD, Difficulty, WinOnCount all apply unchanged).
A mode flag + compiler branch is cheaper than a duplicate schema.

**Required mechanics for v1 grid mode:**
1. `GridController` (controller name)
2. `GridPlayfield` (arena kind in `config.arena`)
3. `TurnManager` (mechanic; gates dt updates to player-input ticks)
4. `FallingPieceMechanic` (covers Tetris clones immediately)
5. `TileRewriteMechanic` — already in v0; upgrade from placeholder to
   full rewrite-rule DSL now that grid mode justifies it.

**Expected coverage gain:** puzzle + roguelike + grid-arcade families —
easily > 15% of retro-corpus mechanics become expressible. Highest-
leverage single addition.
