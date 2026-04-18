# Game 031 — Braid (2008, Xbox Live Arcade)

> Note: Braid is post-2005; include for mechanic breadth.

**Mechanics present:**
- 2D platformer base — PlatformerController (v1)
- **Time reversal** — hold button → rewind time; all entities reverse. Most entities respect rewind; some don't (green-tinted objects). **`TimeReverseMechanic`** (noted prompt_023)
- Per-world time-rule twists:
  - World 2: standard rewind
  - World 3: time dilation (moves when Tim moves)
  - World 4: parallel time zones
  - World 5: shadow replay (record one attempt, play it while doing another)
  - World 6: time-ring (rings create local-time bubble)
- Puzzle levels with key + door + exit — LockAndKey ✓, exit WinOnCount
- No combat per se (stomp enemies like Mario) — DirectionalContact (v1)
- Collect puzzle pieces (meta-progress) — PickupLoop variant
- Narrative via text between worlds — DialogScript (v1)
- Secret stars (challenge collectibles) — PickupOnce (noted)

**Coverage by v0 catalog:** ~2/10

**v1 candidates from this game:**
- TimeReverseMechanic (noted)
- `ShadowReplay` — record-and-replay archetype state (variant of TimeReverse with directionality)
- `LocalTimeBubble` — zone-based physics-modifier (`PhysicsModifier` specific case)
- `ParallelTimeZone` — split world into sections with different time-rules

**Signature move:** **one novel time-mechanic per world, reusing the
same platformer shell.** Each of 6 worlds is Mario 1-1 in mechanical
structure, but with a twist. The game's identity is the twist
sequence. Validates the emergence thesis at the *design-progression*
level: small catalog × N well-chosen variations = distinct feels.

**Method implication:** `PhysicsModifier` and `TimeReverseMechanic` are
small primitives individually but compose with the platformer stack to
produce Braid. If v1 ships platformer + TimeReverse + PhysicsModifier
+ LocalTimeBubble, Tsunami can emit "Mario with a time-twist" design
scripts. Good test case for the agentic loop.
