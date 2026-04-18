# Prompt 032 — Arcade racing (Out Run / Sega Rally-style)

**Pitch:** drive fast car down branching road; reach checkpoint before time runs out; no opponents directly — beat the clock; music swap via roadside choice; scenic tracks.

**Verdict:** **expressible with caveats (close fit after kart additions)**

**Proposed design (sketch):**
- archetypes: `player_car` (VehicleController, arcade tuning), `checkpoint_gate`, `road_segment`, `hazard_*`, `music_box` (jukebox roadside)
- mechanics: `VehicleController` (v1), `LapCounter` or `CheckpointRace` (v1, timer-based), `LoseOnZero` (timer), `AudioStreamChannel` (music swap, noted), `Difficulty` (faster time as you get further), `HUD` (speed + timer + time-bonus), `TrackSpline` (v1)

**Missing from v0:**
- **`CheckpointRace`** — sequence of timed checkpoints; each extends the timer. Variant of LapCounter for A→B rather than closed loop.
- **Branching track at intersections** — "fork left or right at next intersection". `TrackBranchChoice` — player-input-gated node in a track spline graph.
- **Arcade-physics tuning** — car is forgiving; drifting is easy. Tuning constants on VehicleController, not a new primitive.
- **Scenery unlockables** — pass through certain checkpoints → visual variant. Mostly content-driven; no new mechanic.

**Forced workarounds:**
- `AudioStreamChannel` (noted for GTA) covers music swap.
- Branching track via two parallel TrackSpline instances + choice-gate. Works.

**v1 candidates raised:**
- `CheckpointRace` — timer + sequence of gates; extension of LapCounter
- `TrackBranchChoice` — fork in track spline gated on player input at the moment

**Stall note:** arcade racing is very close once v1 ships vehicle + track primitives. Out Run's appeal is the 2D-sprite-over-perspective-road trick — engine-level, not mechanic-level. Reachable with modest v1 investment. Second-simplest genre after rhythm to saturate via content multiplication (drive a different car through a different tileset = different game).
