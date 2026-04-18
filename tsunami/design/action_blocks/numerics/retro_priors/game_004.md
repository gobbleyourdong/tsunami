# Game 004 — Street Fighter II (1991, arcade)

**Mechanics present:**
- Combo input detection (↓↘→+P etc.) — ✅ `ComboAttacks` (wraps ComboSystem)
- Frame data (startup/active/recovery per move) — **not in v0**
- Hitbox/hurtbox separation — **not in v0**
- Dual health bars — ✅ `HUD`
- Best-of-3 rounds — **not in v0** (`RoundManager`)
- Round timer → draw/judge — **not in v0**
- Block stun vs. hit stun — **not in v0**
- Character-specific move lists — partial (ComboSystem per-archetype works; but frame data is missing)
- Super meter (later editions) — **not in v0** (`Resource` component)
- CPU difficulty ladder — ✅ `Difficulty`
- Throw / command grab — **not in v0** (contact-based grab mechanic)

**Coverage by v0 catalog:** ~3/11

**v1 candidates from this game:**
- `RoundManager`, `AttackFrames` metadata, `Hitbox`/`Hurtbox`, `Resource` (super meter generalization), `StunState` in state machine, `RoundTimer` mechanic

**Signature move:** frame advantage. The mathematical structure underneath what feels like "reads." You cannot fake this at the design level — either the schema exposes frame data or the fighting game isn't one.
