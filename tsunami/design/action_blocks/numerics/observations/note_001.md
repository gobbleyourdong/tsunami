# Observation 001 — Schema mode mismatch with Zork-class IF

**Source:** prompt_006 (Zork-like text adventure).

**Claim:** v0's schema is *spatial-simulation-first* — archetypes in arenas
with physics and meshes. IF (Zork, Inform-class) is *state-graph-first* —
rooms are nodes, world state is a flag tuple, input is parsed prose.
Forcing IF through the v0 schema produces a worst-of-both hack: scene-per-
room wastes transition cost and loses state coherence; a single-archetype
blob collapses the schema's benefit.

**Recommendation:** v0 does **not** cover IF, and should not try.
Options for the design track:

- (A) Accept the limit. Document v0 as "real-time spatial games" and
  direct IF authoring to a different tool (e.g., Inform 7, Twine).
- (B) Build a parallel schema (`if-design.ts`?) with room-graph,
  parser, world-flags as first-class. Separate compiler path. Big
  investment; small addressable genre; probably not worth v1.
- (C) Add a narrow subset: **dialogue-heavy action-adventure**. Use
  `DialogTree` + `WorldFlags` components, keep the spatial schema.
  Covers Zelda conversations, Chrono branching — NOT Zork-style
  parse-anything prose. A pragmatic middle.

**My recommendation:** (C) for v1. (A) for Zork-like full IF. (B) flagged
as v2 if authorship demand materializes.

**Falsifier:** if ≥ 3 upcoming prompts in the Track A sweep are full IF
(Anchorhead, Galatea, Hadean Lands), revisit. Given the retro corpus skew
toward action, doubt it fires — but the check should run at prompt_030.
