# Observation 007 — Emergence thesis validated across the corpus

**Sources:** positive-side finding, not a gap. Corpus entries exhibiting
"small primitive catalog × composition = signature feel" directly:

- game_003 Pac-Man — 4 ghost AIs over 1 maze = 4-agent opera from 3
  primitives (Chase + Flee + TimedStateModifier on power-pellet)
- game_005 Zelda — ItemGate × RoomGraph = entire Metroidvania design
  space from 3 primitives
- game_010 Chrono Trigger — Party-pair combo techs (7 characters × 7 =
  ~20 tech combinations from base per-character abilities)
- game_019 Beatmania — 1 RhythmTrack mechanic × N beatmaps = infinite
  song library from one engine
- game_021 NetHack — systemic interactions (wand × fountain, altar ×
  item, cockatrice × egg) — thousand-hour depth from a finite primitive
  count
- game_022 GTA III — one open world + N missions + M activities = the
  "sandbox plus structure" feeling from composition
- game_023 Silent Hill — horror = Resource scarcity + clumsy controls +
  ProximityTrigger audio + hand-drawn map + narrative ambiguity. NO
  horror primitive needed; the emergent property arises from the
  combination.
- game_025 Mario Kart — RubberBanding + WeightedRandomReward =
  accessible arcade racing. Two small mechanics produce the genre's
  signature feel.

**Claim:** the method's central bet — that a small composable catalog
generates a large design space — is **empirically supported by shipped
retro games**. The bet isn't "games are composable in theory." It's
"shipped successful games are built this way whether the developers
named the pattern or not." This is post-hoc pattern-matching, not a
proof, but the pattern is consistent across the 8 sampled examples
spanning genre clusters.

**Implication for design-track:** the v0-to-v1 expansion is not just
"add more mechanics for coverage." It's **"add composable primitives
that multiply." The right 10 v1 mechanics are the ones that compose
orthogonally with v0 to produce many new genre-fits.**

Ranking v1 candidates by *composability* (loosely, how many other
mechanics they enable) — not just by frequency:

1. `Resource` (generic) — composes with Shop, Difficulty, HUD, and
   enables N new Resource-bearing mechanics (mana, stamina, currency,
   energy).
2. `EmbeddedMinigame` (note_006) — composes with every mechanic; turns
   any mechanic into a sidequest/set-piece.
3. `GridPlayfield` + `GridController` (note_002) — enables all grid-
   genre mechanics.
4. `WorldFlags` — composes with DialogTree, EndingBranches, gating
   conditions, scripted events. High multiplicative value.
5. `DirectionalContact` (note_003) — platformer stomp, fighter block,
   stealth takedown, horror grab. Trigger-layer revision with genre-
   spanning impact.

Composability is the **sigma-compatible metric** for v1 priorities —
maps-include-noise says keep the per-candidate data, but the
design-track should look at which additions multiply outward most.

**Falsifier:** if v1 adds the top-5 above and a re-sweep of the 25
prompts still shows ≤30% clean-expressible, then composition doesn't
multiply as expected and the catalog needs to grow horizontally (more
primitives) rather than compose vertically. v1 → v1.5 checkpoint: re-
sweep after top-5 lands.
