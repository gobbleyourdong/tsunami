# Game 006 — Galaga (1981, arcade)

**Mechanics present:**
- Fixed-screen shooter (player locked to bottom edge) — partial in v0 (`controller:"topdown"` + movement-axis clamp; no dedicated "rail" controller)
- Wave-based enemy spawning — ✅ `WaveSpawner`
- Formation flight (enemies fly in entry patterns then hold formation) — **not in v0** (`FormationPath`)
- Dive attacks from formation — **not in v0** (state-driven behavior change; `BossPhases` shape but per-enemy)
- Boss Galaga capture → rescue-for-double-ship — **not in v0** (capture/rescue mechanic; very Galaga-specific)
- Score curve by wave — ✅ `Difficulty` + `ScoreCombos`
- Extra life at score threshold — **not in v0** (flagged in Pac-Man entry)
- Challenging stage (bonus, no enemies shoot back) — **not in v0** (stage-type variant in wave sequence)
- HUD (score, high score, lives) — ✅ `HUD`
- Lose on zero lives — ✅ `LoseOnZero`
- Perfect-wave bonus — **not in v0** (`PerfectClearBonus`)

**Coverage by v0 catalog:** ~4/11

**v1 candidates from this game:**
- `RailController` (axis-locked player)
- `FormationPath` mechanic — enemies follow authored entry spline, then hold
- `PerfectClearBonus` / streak-by-wave (distinct from ScoreCombos)

**Signature move:** the capture → dual ship. A mechanic that briefly flips player into a stronger mode via an interaction with an enemy. Echoes Pac-Man power-pellet (TimedStateModifier) but as a player-upgrade path rather than a mode flip.
