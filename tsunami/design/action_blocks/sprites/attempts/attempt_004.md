# Sprite pipeline — attempt 004

> Architecture thread, fire 4. Recipes thread fire 2 still hasn't
> landed (no priors, no fixtures). Rather than audit-only-churn, this
> fire's deliverable is the consolidated programmer handoff:
> `IMPLEMENTATION.md`. This IS structural — it turns 3 attempts +
> 5 recipes + 2 notes into one executable spec.

## Fire 4 state

- `priors/` — empty
- `recipes/fixtures/` — empty
- `observations/` — note_001 (theirs, fire 1) + note_002 (mine, fire 3)
- No new content signal since attempt_002.

## Fire 4 output: `IMPLEMENTATION.md`

Landed at `sprites/IMPLEMENTATION.md`. Self-contained programmer
brief, ~500 lines, covering:

1. TL;DR + 2–3 week estimate
2. Files to build (9 Python + 3 TS + 3 Tsunami)
3. Context read order
4. 10-phase build sequence (backends → cache → ops → scorers →
   registry → generate_asset → manifest + build → engine runtime →
   Tsunami → E2E)
5. Full type spec (CategoryConfig, MetadataFieldSpec, AssetRecord,
   AssetManifest, Backend ABC)
6. Ops table (17 v1.1 + 4 v1.2 deferred)
7. Atlas JSON shape
8. 7 validator error classes
9. Asset manifest format (authoring + runtime)
10. 11-test ship gate
11. Out-of-scope table (v1.2 / v2 / v3 with deferral rationale)
12. Content thread deliverables as test inputs (recipes = SoT for
    per-category config; priors + fixtures pending)
13. Ambiguity-resolution protocol + discipline lesson carried from
    audio thread

This is the primary handoff document. All 3 attempts are archival;
programmer reads `IMPLEMENTATION.md` + 5 recipe files.

## Why this fire counts as structural

Not a re-statement of attempts. Consolidation that turns design
rationale into PR-sized engineering tasks. Every spec decision from
attempts 001–003 is preserved with build-order + test criteria.

Fire 4 produces a NEW artifact that didn't exist before — the
programmer handoff consolidation. Data Ceiling counter stays at 0.

## Stop-signal projection

Fire 5 outlook depends on recipes thread:

- **If fixtures land:** attempt_005 stress-tests attempt_002's fan-
  out runner + attempt_003's atlas JSON via the fixtures. May find
  0–2 gaps. Structural possible.
- **If priors land without fixtures:** minor absorption work; no
  fan-out stress-test. Counter = 1 of 2.
- **If nothing lands:** genuine hold. Counter = 1 of 2. Fire 6 hold
  if also empty.

## Self-check

- Sprite-architecture scope? ✓
- Re-checked files directly (priors-over-status)? ✓ — confirmed dirs
  empty.
- Zero-dep / LLM-authorable / category-extensible? ✓ (IMPLEMENTATION.md
  preserves all of these).
- Each deliverable landable in one programmer-sitting? ✓ — 10 phases
  are each PR-sized.
- New structural movement? ✓ — IMPLEMENTATION.md is a new artifact
  not present before.

5/5 yes. Counter: 0 of 2 no-signal fires.

## Operator visibility

If operator wants to start implementer now: `IMPLEMENTATION.md` is
ready. Architecture won't block.

If recipes thread produces fixtures before implementer starts:
fire-5 attempt_005 will validate + potentially catch last gaps via
stress-test. Otherwise implementer may catch them first and ping
back.
