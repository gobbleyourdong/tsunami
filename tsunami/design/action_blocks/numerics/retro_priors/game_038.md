# Game 038 — Tamagotchi (1996, keychain device)

**Mechanics present:**
- Virtual pet that ages, hungers, gets bored, gets sick — NeedsBars ✓ (v1, Sims)
- Feed / play / discipline / medicate as button actions — ActivitySelect (noted dating sim)
- Real-time clock drives state decay — DayNightClock ✓
- Pet dies if neglected too long — LoseOnZero variant on Needs → composite
- Life stages (egg → baby → child → teen → adult → senior) — StateMachineMechanic ✓ age-gated
- Different pets emerge depending on care quality — **`ConditionalEvolution`** — state branches based on accumulated stats
- Sparse interaction (a few minutes per day) — design mode, not mechanic
- Sound/visual reactions to actions — content
- Pet has "happiness" + "health" stats — standard stats
- Discipline balance (too harsh → grumpy pet; too soft → rude pet) — tuning

**Coverage by v0 catalog:** ~2/10

**v1 candidates from this game:**
- `NeedsBars` ✓ (confirmed from Sims)
- `ConditionalEvolution` — branching state machine gated on cumulative metric thresholds. Distinct from FSM on-transition; closer to *endpoint-classifier* based on history.

**Signature move:** **passive game with real-time decay**. Tamagotchi
is barely "played" — you check in periodically and respond. The
mechanic set is tiny (NeedsBars + DayNightClock + ActivitySelect +
ConditionalEvolution) but produces a surprising attachment effect.
Another example of "small catalog → distinctive feel."

**Genre note:** mobile/casual life-sims (Nintendogs, Pou, Dragon Quest
Walk) inherit this pattern. Content-multiplier adjacent: one Tamagotchi
engine × different pet art = many Tamagotchi-likes. Useful niche for
mobile indie.

**Method implication:** the "sparse interaction" mode requires
DayNightClock ticking while the game isn't in active play. For a web
engine, this means state persistence across sessions — note_004
(SandboxMode) + persistent save. Currently a structural gap.
