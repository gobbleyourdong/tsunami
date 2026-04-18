# Prompt 023 — Puzzle-platformer (Braid / Limbo / Inside-style)

**Pitch:** 2D platformer with a mechanical twist (time reversal, shadow, gravity flip, light/dark); each level's puzzle uses the twist; no combat focus; narrative through environment; atmospheric.

**Verdict:** **awkward → expressible with `mechanic wrappers` concept**

**Proposed design (sketch):**
- archetypes: `player` (platformer controller), `puzzle_object_*` (levers, boxes, doors), `enemy_hazard` (simple threats), `goal`
- mechanics: `PlatformerController` (v1), `LevelSequence` (v1), `TimeReverse` (not in v0, signature Braid mechanic), `PuzzleObject` (Myst, v1), `LoseOnZero`, `CheckpointProgression`

**Missing from v0:**
- **Time reversal / rewind** — Braid's core mechanic. All entity states recorded into ring buffer; press button → replay in reverse. Generic: `TimeReverseMechanic` — record-playback of archetype state.
- **Mechanic-as-modifier wrapping** (gravity flip, shadow follower, world-mirror) — these aren't mechanics in the "action" sense; they're *modes* that alter physics or render. `GravityFlip` is a global modifier; `ShadowFollower` spawns a delayed copy of the player that mirrors inputs.
- **Limbo's trial-and-error death loop** — frequent death expected; instant checkpoint respawn; no score, no lives. `InstantRespawn` variant of `CheckpointProgression`.
- **Environmental narrative** — no dialogue, but scripted environmental events (character silhouette appears, object falls). Scripted-event system.
- **Atmospheric audio/visual tuning** — `vibe` field captures it in design meta, but nothing enforces consistent atmosphere.

**Forced workarounds:**
- Time reversal as a custom `StateMachineMechanic` on every entity, recording/playing back — O(N) per-entity hack.
- Gravity flip as a `GlobalModifier` on physics (if that existed) — clean.

**v1 candidates raised:**
- `TimeReverseMechanic` — record/playback window of entity states
- `PhysicsModifier` — global gravity/friction/time-scale overrides toggled by conditions (overlap with SimCity GlobalModifier)
- `InstantRespawn` / zero-penalty death variant
- `ShadowFollower` — delayed-mirror archetype (Braid's Tim's shadow, also Ocarina's hero shade)
- Puzzle-platformer `PuzzleObject` shared with Myst/RE entries

**Stall note:** Braid/Limbo are mid-2000s indie gems. Each is "one novel mechanic + platformer primitives." The v1 top-10 covers the platformer; the novel mechanics are each small individually (`TimeReverseMechanic` ≈ 200 lines). The method's emergence thesis says authors combine existing mechanics in novel ways — puzzle-platformers are a test case of "emergent games from 2-3 mechanic interactions." Targeting them in v1 is a forcing function to validate the emergence claim.
