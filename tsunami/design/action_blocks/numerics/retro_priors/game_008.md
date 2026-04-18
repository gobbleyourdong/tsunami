# Game 008 — SimCity 2000 (1993, multiple platforms)

**Mechanics present:**
- Grid-based city placement — **not in v0** (`GridPlayfield` + click-to-place)
- Zoning (residential/commercial/industrial) — **not in v0** (`ZoneTag` mechanic; region-typed tiles)
- Simulation tick (monthly/yearly game-time steps) — **not in v0** (related to `DayNightClock` but with much coarser granularity)
- Resource flow (power/water grids, propagation rules) — **not in v0** (`ResourceNetwork` / graph flow mechanic)
- Budget / taxes — **not in v0** (`Budget` / income+expense accumulator)
- Disasters (fire, tornado, monster, nuclear) — **not in v0** (`RandomEvent` triggered by RNG+time)
- Population + demand curves — **not in v0** (`Population` mechanic driving zone fill)
- Ordinances / policies (toggleable modifiers) — **not in v0** (`GlobalModifier` toggle set)
- Mayor's office (reports, advisor dialogue) — partial (`Dialog` close)
- Save/load sessions — partial (persistent save gap)
- Camera pan/zoom over grid — partial (`CameraFollow` close)

**Coverage by v0 catalog:** ~1/11

**v1 candidates from this game:**
- Grid-as-canvas for player editing (vs. grid-as-game like Sokoban)
- `ResourceNetwork` — connected-tile propagation (power/water/roads) as a rule engine
- `Budget` / economic mechanic
- `Population` / demand-driven fill mechanic
- `RandomEvent` mechanic
- `GlobalModifier` toggles

**Signature move:** emergent population from zoning + service provision. No enemy, no win condition; engagement from watching the city grow. A category of game v0 doesn't target: **no lose state, no fail, pure simulation**. v0 has `LoseOnZero`/`WinOnCount` as mandatory flow completions — sims have neither, or only soft ones. Flag as structural gap.
