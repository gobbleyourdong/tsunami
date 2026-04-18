# Prompt 010 — F-Zero-style racing

**Pitch:** top-down or pseudo-3D track; hovering vehicles; boost mechanic; other racers; lap counter; track position; win on 3-lap completion first place.

**Verdict:** **awkward**

**Proposed design (sketch):**
- archetypes: `player_craft` (controller=racing), `rival_craft` (ai=race), `track_segment` (static collision geometry), `boost_pad` (trigger), `checkpoint_gate` (lap counting)
- mechanics: `LapCounter` (not in v0), `Difficulty` (rival AI speed curve), `HUD` (position + lap + time), `WinOnCount` (3 laps + rank 1)

**Missing from v0:**
- **`controller:"racing"`** — vehicular physics: acceleration curve, turn rate, drift. Not in v0 list (fps/topdown/orbit/platformer). 
- **Track geometry as first-class** — the track IS the arena. v0 arena is shape:rect|disk — can't describe a closed loop. Need imported track mesh or spline.
- **`LapCounter`** — ordered checkpoint traversal, detects out-of-order (cheating), counts full loops.
- **Race-AI for rivals** — waypoint-following, rubber-banding (AI catches up if behind), overtaking. None in v0 (`ai:"chase"` is direct pursuit).
- **Split-time / position tracking** — where is player in field of N racers, running rank.
- **Boost/drift resource** — `Resource(boost)` with recharge on drift or boost-pad hit. Same `Resource` gap as sim/fighter.

**Forced workarounds:**
- Track as imported mesh with hand-placed checkpoint_gate triggers. Possible but the design script ends up 80% coordinate data. Not the goal.
- Rival AI via `ai:"patrol"` with waypoint list. Too robotic — no overtaking/catching-up behavior.

**v1 candidates raised:**
- `VehicleController` / `RacingController`
- `TrackSpline` / `LapCounter` mechanic pair
- `WaypointAI` BT preset (distinct from chase/flee/patrol)
- `RubberBanding` — difficulty adjustment for trailing AI
- `Rank` mechanic — sorts field by checkpoint progress, publishes per-racer rank

**Stall note:** racing is a third canonical mode — not realtime-action, not turn-based-grid, but **track-bounded continuous**. Track geometry dominates the design. v0 with free arenas is the wrong shape. Flag: is this a v1 priority or a v2? Probably v2 — niche, high-complexity, low-leverage compared to grid-mode.
