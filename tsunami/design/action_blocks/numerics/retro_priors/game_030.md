# Game 030 — Ikaruga (2001, arcade/Dreamcast)

**Mechanics present:**
- Vertical-scrolling shmup — ✅ AutoScroll (v1, noted)
- **Polarity system (player ship is black OR white; can switch)** — **not in v0** (`PolaritySwitch` — binary state with affinity effects)
- Absorb same-color bullets (black ship absorbs black bullets → charges special); damaged by opposite color — complex trigger semantics (same-polarity = heal/charge; opposite-polarity = damage)
- Homing-laser release on charge — spend Resource (charged bullets) to fire laser
- Chain scoring (3 same-color kills in a row = combo +) — ScoreCombos ✓ but polarity-aware
- Boss-per-stage with elaborate patterns — BossPhases ✓ + BulletPattern (noted shmup)
- 5 stages — LevelSequence (v1)
- 1-hit death (lives system) — standard
- 2-player co-op — local multiplayer (v2+)

**Coverage by v0 catalog:** ~3/9

**v1 candidates from this game:**
- `PolaritySwitch` — binary-state with affinity-to-contact-outcome rule table. Generalization: `AttributeState` where each entity has a tag (polarity/element/faction) and contact outcomes depend on tag-pair lookup.
- Confirms BulletPattern (shmup cluster)

**Signature move:** **the polarity matrix IS the game.** One mechanic (switch polarity) × contact table (same = absorb, opposite = damage) = a completely different shmup. Treasure (the developer) built the game around this single mechanic. It composes with WaveSpawner, BossPhases, ScoreCombos — existing v0 primitives — and transforms their feel entirely.

**Method thesis validation (5th direct example):** a single well-chosen mechanic × existing primitives = new genre. `PolaritySwitch` would ship as a ~50-line mechanic and unlocks the entire "element-swap shmup" pattern (also applies to: ZX Spectrum TLL, Outland 2010, PolaritySwitchGames-everywhere). The emergence thesis predicts this should work; Ikaruga proved it in 2001.

**Strongest takeaway so far:** Ikaruga + Beatmania + Mario Kart + Pac-Man together say: **the right 3–5 small mechanics, composed with a solid primitive catalog, produce games that get called "classics."** The design-script method's bet is that LLM-driven recombination of a well-chosen catalog can produce novel but playable games. This is the closest empirical evidence that the bet has merit at the *micro* (per-game) level.

What remains unproven is whether LLM emissions discover these combinations in practice, or only recapitulate known genres. That's a compiler-required experiment, not a numerics one.
