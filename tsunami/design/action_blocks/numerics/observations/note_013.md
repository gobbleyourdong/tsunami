# Observation 013 — Scaffold library scoping correction

**Source:** operator input 2026-04-17 — *"also re multiple game modes
they have a scaffold library, we will have those expertly built and
fine tuned."*

**Claim:** I was treating "v0 vs v1 extensions for IF / RTS / grid /
card / deckbuilder" as if the action-blocks schema had to stretch to
cover every game mode. **It doesn't.** Each alternative game mode
(grid-puzzle, IF, RTS, deckbuilder, …) will be its **own scaffold** in
`ark/scaffolds/` — **expertly hand-authored**, not LLM-composed from
action-blocks primitives.

Reference: `ark/scaffolds/` already contains `game/`, `auth-app/`,
`chrome-extension/`, `realtime/`, `api-only/`, `data-viz/`, `fullstack/`,
etc. Each is a genre-specific template with its own authoring surface.
The action-blocks system is *one* scaffold — for real-time single-
protagonist spatial games (per note_005). Other scaffolds will be
added as separate templates with their own schemas, each "expertly
built and fine-tuned."

## Impact on existing observations

**note_002 (grid-mode bundle):** scope revision. Grid mode is NOT an
action-blocks extension; it's a separate scaffold (`scaffolds/
grid-puzzle/` or similar, when built). **Drop from action-blocks
v1 priorities.** The grid-related mechanics I ranked highly
(GridPlayfield, GridController, TurnManager, FallingPieceMechanic,
LineClearMechanic, TileRewriteMechanic) likely belong in that
future scaffold, not in action-blocks/v1.

**note_001 (IF schema mismatch):** *"recommend separate schema"* was
the right call, now confirmed. IF = separate scaffold. Don't bolt
dialogue-parser / WorldFlags into action-blocks to fake IF; wait for
the IF scaffold.

**note_007 (composability):** still applies within action-blocks. The
emergence thesis doesn't require action-blocks to cover all genres —
it requires that within *its* scope, small catalog × composition =
large design space.

**note_009 (content-multiplier):** mostly still applies, but scope-
aware:
- `RhythmTrack` — fits action-blocks (real-time spatial)
- `DialogTree`/`DialogScript` — partial fit; narrative-heavy games
  probably get their own scaffold eventually
- `TileRewriteMechanic` — belongs in grid-puzzle scaffold, not action-blocks
- `ProceduralRoomChain` — fits action-blocks (roguelite)
- `BulletPattern` — fits action-blocks (shmup)

**note_005 assumptions remain correct** — they describe *the action-blocks
scaffold's* scope, not "the universal Tsunami scope." Other scaffolds
will have their own assumption sets (grid scaffold: discrete + turn-
based; IF scaffold: text + state-graph; RTS scaffold: multi-unit).

## Revised impossible-set for action-blocks

Not "impossible" — **"out-of-action-blocks-scaffold; belongs in X
scaffold":**

| Prompt | Verdict | Target scaffold |
|---|---|---|
| 006 Zork | out-of-AB | IF scaffold |
| 012 StarCraft | out-of-AB | RTS scaffold |
| 016 FE Tactics | out-of-AB | turn-based tactics scaffold |
| 017 Deckbuilder | out-of-AB | card-game scaffold |
| 021 Madden | out-of-AB | sports-sim scaffold (multi-unit) |
| 026 MMO | out-of-AB | networked-multiplayer scaffold (infrastructure-heavy) |
| 028 Western CRPG | out-of-AB | CRPG scaffold (real-time-with-pause + deep RPG) |
| 002 Tetris, 001 Sokoban, 008 Roguelike, 039 Bejeweled (was "grid awkward") | out-of-AB | grid-puzzle scaffold |

That's ~11 prompts (out of 40) that belong in other scaffolds. Action-
blocks' job is the remaining 29, which are real-time spatial.

## Revised action-blocks v1 priorities

Top-5 minus grid-mode bundle:

1. **`Resource` (generic)** — real-time spatial games commonly need
   mana/currency/boost/stamina.
2. **`EmbeddedMinigame`** (note_006) — composability multiplier.
3. **`WorldFlags` + `DialogTree` + `DialogScript`** — narrative
   layering for action-adventure, narrative-RPG. Content-multiplier
   per note_009.
4. **`DirectionalContact`** schema revision (note_003) — platformer/
   fighter/stealth in the spatial scaffold.
5. **Concretize `RhythmTrack`** — content-multiplier for rhythm-action
   (which IS real-time spatial).

**Removed from top-5:** grid-mode bundle. That's the grid-puzzle
scaffold's problem.

**Estimated action-blocks coverage after top-5:** ~70–75% of the 29
in-scope prompts (raised from the previous 65–70% estimate because
grid-mode was inflating the "impossible" count with prompts that were
never action-blocks' problem).

## Method lesson (round 2)

Same as note_012 but deeper: **I was extrapolating action-blocks'
scope from "what the design script can express" without checking the
broader system. note_005 named the scope correctly, then I forgot and
started stretching.**

Sigma discipline: "Priors Don't Beat Source" — check the repo structure
before extending the schema. `ark/scaffolds/` IS the source; my model
of it was outdated. Next time, re-scan the scaffolds dir before pushing
any schema-extension recommendation that smells like "new mode."

## Implication for the design track

attempt_011's handoff package (schema.ts + catalog.ts + prompt
scaffold) is **correctly scoped** for the action-blocks scaffold.
Design track was disciplined; I was the one drifting. The handoff
stands. No v1.0.3 revision needed from this note.

## Non-blocking question for operator

Current scaffolds in `ark/scaffolds/`: game, auth-app, chrome-extension,
realtime, api-only, data-viz, dashboard, electron-app, form-app,
fullstack, landing, ai-app, react-app. **The `game/` scaffold IS
action-blocks?** Or is the action-blocks system deliberately separate
from the existing `game/` scaffold (which currently imports `@engine`
freehand per `agent.py:2696-2716`)?

If `game/` and action-blocks are the same thing, noted. If they're
distinct, I want to understand the boundary. Low priority — design
track's handoff will make this clear in context.
