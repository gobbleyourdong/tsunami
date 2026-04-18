# Game 001 — Super Mario Bros (1985, NES)

**Mechanics present:**
- Platformer movement (run/jump, variable jump height, momentum) — **not in v0** (no `PlatformerController`)
- Directional collision (stomp kills, side damages) — **not in v0**
- Pickup (coins, power-ups) — ✅ `PickupLoop`
- Destructible blocks (head-bump bricks) — **not in v0** (directional trigger)
- Item-spawn blocks (`?` blocks drop power-ups) — **not in v0** (chained trigger)
- Power-up state (Super, Fire) — **not in v0** (player state escalation; `StateMachineMechanic` partial fit)
- Scrolling camera (horizontal, one-way) — **not in v0** (no `CameraFollow`)
- Checkpoint / mid-level respawn — ✅ `CheckpointProgression` (close)
- Level sequence (1-1, 1-2, …) — **not in v0** (`LevelSequence`)
- Time limit — partial (`LoseOnZero` on a Timer component could work)
- Secret warp pipes — **not in v0** (teleport trigger + graph)
- Score + lives + coins HUD — ✅ `HUD`

**Coverage by v0 catalog:** ~3/12

**v1 candidates from this game:**
- `PlatformerController`, directional triggers, `CameraFollow`, `LevelSequence`, power-up state escalation, teleport trigger

**Signature move:** the jump. Momentum-carrying, variable-height, coyote-time. Feel is in controller tuning.
