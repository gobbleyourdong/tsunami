# Game 007 — Ms. Pac-Man (1982, arcade)

**Mechanics present:** (mostly inherited from Pac-Man; diffs below)
- 4 distinct mazes (rotated per level group) — **not in v0** (`MazeSet` / level-to-geometry mapping)
- Randomized ghost AI (Pinky/Inky less deterministic than original) — **partial** (would want stochastic BT nodes)
- Moving fruit (fruit travels through maze, not static) — **not in v0** (animated path fruit)
- Intermission cutscenes between level groups — **not in v0** (`Intermission` / non-interactive scene)
- All other Pac-Man mechanics — same coverage as game_003

**Coverage by v0 catalog:** ~4/10 (same base)

**v1 candidates from this game:**
- `MazeSet` — level → one-of-N geometry rotation
- Stochastic/noise nodes in BT library
- `PathAnimation` — entity follows authored path over time (used for moving fruit, also cutscene actors)
- `Intermission` / cinematic non-interactive scene

**Signature move:** maze variation. Pac-Man had one maze; Ms. Pac-Man cycling 4 mazes increased replay value with minimal new content. Data point: level variation is a high-leverage low-cost mechanic.
