# Game 025 — Mario Kart 64 (1996, N64)

**Mechanics present:**
- Kart racing on fixed track — partial (VehicleController + TrackSpline noted)
- 8 racers (1 player + 7 AI) — multi-unit race, AI opponent
- Lap counter (3 laps per race) — LapCounter (noted)
- Item boxes (pickup random weapon) — PickupLoop variant + RandomSelect
- Weapon items (shells, bananas, stars, lightning, bomb) — each a one-shot ActionRef on use
- Rubber-banding AI (catchup) — same as F-Zero (noted)
- Drift boost (hold drift → release for speed) — controller mechanic; input-held-release action
- Position in race (running rank) — noted in F-Zero
- Coin collection (boosts top speed) — PickupLoop with max-accumulate + speed-multiplier
- Grand Prix mode (4 tracks, point total) — tournament wrapper over LevelSequence
- Time Trial with ghost — ReplayGhost (noted in Gran Turismo)
- Mirror mode + 150cc mode (difficulty variants) — Difficulty scaling
- 4-player split-screen — **not in v0** (local multiplayer + split-screen rendering)
- Battle mode (separate mode, pop balloons) — EmbeddedMinigame variation
- Shortcuts (hidden faster path) — part of track geometry

**Coverage by v0 catalog:** ~1/14

**v1 candidates from this game:**
- Same as F-Zero (prompt_010) racing primitives
- Plus: `ItemBoxPickup` — randomized-reward pickup (PickupLoop + RandomTable)
- `TournamentMode` — grouped LevelSequence with aggregated score across instances
- `LocalMultiplayer` + split-screen — v2+ (engine-level)
- `DriftBoost` — input-timing-based speed modifier

**Signature move:** **rubber-band + item-RNG for accessibility**. Racing sims (GT) reward skill at the expense of newcomers. Mario Kart's blue shell / rubber-band keeps 1st and 8th close. Players near the back get better items; players near the front get bananas. The game's appeal is *the design tempers skill gap* — emergent drama from stochasticity layered on simulation.

**Method implication:** the rubber-band is a mechanic (`RubberBanding` — alter AI speed inversely proportional to rank). The item weighting is another (`WeightedRandomReward` — drop probabilities by rank). Layering them creates the Mario Kart feel. Two small v1 mechanics turn arcade racing into "accessible arcade racing." A clean example of "small mechanics → signature feel" that the design-script approach can express directly.

**Genre classification:** Kart racing is arcade racing (distinct from sim like GT). Much closer to v1 reach — doesn't need full `VehiclePhysics`. `VehicleController` + `TrackSpline` + `LapCounter` + Mario-Kart-style items gets most of the way.
