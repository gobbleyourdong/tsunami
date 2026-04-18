# Game 039 — Bejeweled (2001, PC)

**Mechanics present:**
- 8×8 grid of gems — GridPlayfield (v1)
- Swap adjacent gems with mouse drag — GridController (v1) + drag input
- Match 3+ same-color in row/column → gems disappear — **MatchRule** (noted prompt_039)
- Above gems fall to fill gaps — **GravityDrop** (noted)
- New gems spawn at top to refill board — RandomSpawn
- Score per match, chain bonus on cascade — ScoreCombos ✓ + CascadeScore
- Endless mode (no win; play until no moves) — SandboxMode (v1)
- Timed mode variant — LoseOnZero on timer
- Puzzle mode (pre-authored board states) — LevelSequence (v1)
- Special gems (4-in-row → line-clear, 5-in-row → rainbow, T-shape → bomb) — pattern-triggered spawn
- "No moves" detection → auto-shuffle — specialized grid analysis
- Casual-friendly (no game over pressure) — design tone

**Coverage by v0 catalog:** ~2/10

**v1 candidates from this game:**
- Confirms MatchRule, GravityDrop, RandomSpawn, CascadeScore from prompt_039
- `NoMovesCheck` — grid-state analyzer that detects unresolvable state and triggers reshuffle (specialized TileRewrite eval)

**Signature move:** **cascades.** One match triggers gravity, falling
gems may match again, producing chain reactions. Exponential scoring
on chain depth makes near-random initial boards occasionally produce
satisfying 10x cascades. Bejeweled's appeal is the *stochastic chain
payoff* — a dopamine hit the player feels they earned but mostly
didn't.

**Content-multiplier:** match-3 is a massive commercial genre
(billions in mobile revenue). Candy Crush, Puzzle Quest, Shariki,
hundreds more. One mechanic + different art + different special-gem
rules = many games. Confirms match-3 via TileRewriteMechanic DSL as
high-priority for content-multiplier strategy (note_009).

**Dedupe signal:** match-3 is the 2nd "grid puzzle with emergent
cascades" game (after Tetris). Primitives stable.
