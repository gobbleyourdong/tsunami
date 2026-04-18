# Game 018 — Gran Turismo (1997, PS1)

**Mechanics present:**
- Realistic driving physics (tire grip, suspension, weight transfer) — **not in v0** (`VehiclePhysics` beyond `VehicleController`)
- Real-world-licensed cars with distinct stats — archetype variants per car
- Tracks (real or fictional) as closed loops — partial (`TrackSpline` noted in F-Zero prompt)
- Lap counting + timing — ✅ `LapCounter` (noted)
- AI opponents with race lines — ✅ `WaypointAI` (noted)
- Career mode (buy cars, win prize money, upgrade, buy better) — **not in v0** (persistent economy + Shop + tuning)
- Licenses (gated progression via driving tests) — `LevelSequence` with per-step skill gate
- Tuning / upgrades — part swaps affecting vehicle stats (RPG-level depth applied to cars)
- Replay mode — cinematic camera playback of captured run
- Ghost car (race against own best lap) — `ReplayGhost` mechanic; record-playback
- Damage / no-damage (depending on mode) — optional damage model
- Weather (rain affects grip) — environmental modifier; DayNightClock-analog
- Time of day (visual + grip) — `DayNightClock` could fit

**Coverage by v0 catalog:** ~0/12

**v1 candidates from this game:**
- Confirms racing-genre primitives from prompt_010
- Adds: `VehiclePhysics` component (beyond basic controller), `ReplayGhost` mechanic, `CareerMode` (persistent economy + Shop + vehicle stats)
- `WeatherModifier` (GlobalModifier variant, affects physics multipliers)

**Signature move:** simulation-level authenticity as gameplay. The game is "good" because the physics are real. Hard to author declaratively — every car needs a data file of physics params, every track needs geometry. The design-script approach would mostly PUNT to imported physics models and focus on race-structure mechanics (laps, AI, career).

**Genre verdict:** racing sim sits squarely at v2+. Arcade racing (F-Zero-style) is closer to v1-reachable with `VehicleController` + `LapCounter` + `WaypointAI`.
