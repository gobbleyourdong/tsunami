# Game 003 — Pac-Man (1980, arcade)

**Mechanics present:**
- Grid/maze movement (topdown, rail-locked to corridors) — partial in v0 (topdown controller is continuous)
- Pellet collection — ✅ `PickupLoop`
- Power-pellet (temporary mode flip: chase → flee) — **not in v0** (`TimedStateModifier`)
- Four distinct ghost AIs (Blinky=direct, Pinky=+4 ahead, Inky=relative, Clyde=distance toggle) — **not in v0** (`ai:"chase"` is one-size)
- Fruit spawn (timed bonus pickup) — **not in v0** (timed spawn)
- Warp tunnels (left edge → right edge) — **not in v0**
- Lives + extra-life-at-score — partial (`Lives` component, not the at-score trigger)
- Level progression (speed up, ghost behavior shift) — ✅ `Difficulty`
- Win on all-pellets-eaten — ✅ `WinOnCount`
- HUD (score, high score, lives) — ✅ `HUD`

**Coverage by v0 catalog:** ~4/10

**v1 candidates from this game:**
- `TimedStateModifier` (power-pellet pattern), per-ghost BT library, timed spawn mechanic, warp/teleport trigger, `ExtraLifeAt` score threshold mechanic

**Signature move:** the four ghost personalities. Identical AI for all four → feels mindless. Four distinct targeting rules over the same maze → feels like an opera. Emergence from heterogeneous agents sharing an arena.
