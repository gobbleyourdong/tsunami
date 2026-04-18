# Numerics — status

**Last updated:** 2 operator directions received 2026-04-17.
**Cron:** **STOPPED** (job 4d8dbcd9 cancelled).
**Sweep size:** n=40. **Final.**
**Mode:** standby under Option C.

## Operator directions this session (chronological)

1. **(C) Option selected** — stop numerics, support mode for implementer.
2. **Multiplayer correction** (note_012) — engine provides multiplayer
   wiring; local multiplayer is not out-of-scope; note_005_addendum
   revised.
3. **Scaffold-library scoping** (note_013) — alternative game modes
   (grid, IF, RTS, card, deckbuilder) belong in separate scaffolds
   (`ark/scaffolds/`), expertly hand-authored. Action-blocks is
   *one* scaffold, not the universal authoring layer.

## Corrections consolidated

- **Impossible-set:** shrinks from 8 → 7 genres (Mario Party back
  in-scope). Beyond that, 11 prompts total are "out-of-action-blocks;
  belongs in X scaffold" — not unreachable by Tsunami overall,
  just not action-blocks' problem.
- **v1 top-5 revised:** grid-mode bundle DROPPED from action-blocks
  v1 (belongs in grid-puzzle scaffold when that's built). Slot-3
  replaced with concretize-`RhythmTrack`. Full new top-5 in note_013.
- **Coverage estimate:** after revised top-5, ~70–75% of the 29 in-
  action-blocks-scope prompts (vs 65–70% previously).

## What I was wrong about and why

Two over-extrapolations caught within one session:

1. **Multiplayer → single-session-local.** Inferred from one MMO
   prompt; operator clarified the engine handles it.
2. **"V0 needs a grid-mode extension."** Inferred from sokoban/tetris/
   roguelike prompts; operator clarified each is its own scaffold.

Both are Sigma "Priors Don't Beat Source" hits. My model of the
broader system (engine capabilities + scaffold library) was stale;
I built schema-extension recommendations on that stale model. Lesson:
re-scan `ark/scaffolds/` and engine source before flagging any
"v0-needs-a-new-mode" gap.

## Current role: standby

Per Option C + corrections:
- No more `prompt_NNN` / `game_NNN` files. Cron paused.
- Design instance handles mechanic-spec support for the implementer.
- My contribution now: be available for re-sweep falsifier + any
  sanity-check the operator wants.

## Non-blocking requests / open questions

1. **Is `ark/scaffolds/game/` the action-blocks scaffold**, or is
   action-blocks a *new* scaffold parallel to it? Noted in note_013.
2. Ping me when v1 engine port lands → I re-sweep the 29 in-scope
   prompts to measure coverage delta (note_007 falsifier).
3. If the operator adds a new scaffold (grid-puzzle, IF, RTS, …), I
   could sweep THAT scaffold's coverage the same way I swept action-
   blocks. Offer stands; no action required now.

## Files current on disk (final)

- `coverage_sweep/prompt_001.md` through `prompt_040.md`
- `retro_priors/game_001.md` through `game_040.md`
- `observations/note_001.md` through `note_013.md` (+ revised
  `note_005_addendum.md` with note_012 correction banner)
- `coverage_sweep/gap_map.md` (n=30 aggregate; top-13 rankings still
  accurate per note_010)
- `retro_priors/frequency.md` (n=30 aggregate)
- `rolling_summary.md` (legacy)
- This `status.md`

## Headline signal delivered

- 40 prompts + 40 retro games with per-entry verdicts and gap data.
- 13 observations, 5 of which adopted into design-track's v1.0.3.
- Top-13 v1 candidates (post-correction) with ≥ 8 corpus sources each.
- 7 genres confirmed out-of-action-blocks-scaffold (belong in other
  scaffolds when built).
- Method thesis (composability + content-multiplier) validated across
  8 corpus examples (note_007).
