# Observation 005 — Document v0's domain explicitly

**Sources:** prompts 006 (Zork), 012 (StarCraft), 011 (Monkey Island
partial), game_011, game_012 — 4/30 sources where the genre is
*structurally* incompatible with v0's schema assumptions.

**Claim:** v0 makes three implicit assumptions that define its domain:

1. **Real-time** — game ticks at frame rate; mechanics run `onUpdate(dt)`.
   (Violated by: turn-based, rogue-likes, classic RPG, chess.)
2. **Single-protagonist** — one player archetype drives. Input targets
   that archetype.
   (Violated by: RTS multi-unit, Sims multi-sim, Civilization multi-
   character, party-based JRPG at the combat layer.)
3. **Spatial** — archetypes have positions in a scene. Contact, collision,
   proximity all derive from geometry.
   (Violated by: IF/text adventure state-graph, card games, board games
   abstracted from board.)

Everything in v0 works when all three assumptions hold; everything
strains or breaks when any fail. The sweep data supports this cleanly:
high-coverage games satisfy 3/3 (arcade, platformer, action-adventure);
low-coverage games fail on ≥ 1 (StarCraft: #2; Zork: #2 + #3; SimCity:
#2; Sims: #2; Chrono JRPG combat: partial #1 + #2).

**Recommendation:** document this in the catalog or a doc sibling:

> v0 targets **real-time single-protagonist spatial games.** Games
> violating these assumptions (RTS, turn-based strategy, text adventure,
> multi-protagonist sim) are either out of scope or require separate
> schema extensions.
>
> v1 planned extensions:
> - grid mode (relaxes "continuous physics" but keeps #1–#3)
> - sandbox mode (relaxes "must have win/lose" but keeps #1–#3)
> - dialogue subset (relaxes #3 partially for narrative-heavy action)
>
> Out of v1 scope:
> - RTS (violates #2)
> - full IF (violates #2 + #3)
> - turn-based strategy (violates #1)

**Why this matters:** authoring expectations. A user who prompts
Tsunami with "make me a StarCraft clone" should get a schema validator
response saying *"v0 does not support RTS; closest supported: arena
shooter with wave enemies"* — rather than Tsunami producing a degraded
RTS attempt that fails silently. The catalog should know its own
limits.

**Composition with note_001 + note_002 + note_003 + note_004:** each
of those named a specific v1 extension. This note provides the
overarching frame. The three assumptions above are what keeps v0
small; relaxing each is one v1 direction at a time.
