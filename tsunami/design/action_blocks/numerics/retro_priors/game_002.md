# Game 002 — Tetris (1984, Electronika 60 / 1989 Game Boy)

**Mechanics present:**
- Falling piece with player shift/rotate — **not in v0** (dedicated mechanic needed)
- Line clear (full row → remove + cascade) — **not in v0**
- Grid playfield (10×20 fixed) — **not in v0** (singleton arena pattern)
- Piece generator (random / 7-bag) — **not in v0**
- Drop-speed curve by level — ✅ `Difficulty`
- Score curve (single/double/triple/Tetris multiplier) — ✅ `ScoreCombos` (close)
- Next-piece preview — **not in v0** (HUD variant)
- Hold piece (later versions) — **not in v0**
- Top-out lose condition — ✅ `LoseOnZero` via grid-height threshold
- HUD (score, lines, level, next) — ✅ `HUD`

**Coverage by v0 catalog:** ~3/10

**v1 candidates from this game:**
- `FallingPieceMechanic`, `LineClearMechanic`, `GridPlayfield` archetype kind, `RandomBagGenerator`, preview-slot in HUD

**Signature move:** the cascade. Clearing multiple rows at once is mechanically identical to clearing one, but the score curve makes the decision about when to wait ("go for the Tetris") vs. clear now. Risk/reward from a single rule.
