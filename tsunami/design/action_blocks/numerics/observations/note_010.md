# Observation 010 — Dedupe signal: sweep approaching diminishing returns

**Sources:** batch 7 (games 031–035) — 3 racing games (GT, MK64,
Daytona) now in corpus, 3 narrative/adventure (Monkey Island, Phoenix
Wright, Grim Fandango), 3 shmups (Galaga, Gradius, Ikaruga). Each
genre cluster's v1 primitives are stable across its members.

**Claim:** the sweep has reached the point where further samples within
an already-sampled genre add **no new primitives**. Batch 7 introduced
a handful of small primitives (`PowerSelectBar` from Gradius,
`GestureRecognizer` from B&W) but no new structural gaps.

**Evidence:**
- v1 top-5 unchanged since n=20 (5 batches).
- Top-13 v1 candidates unchanged since n=25 (2 batches).
- Rankings stable across last 3 batches.
- Impossible set unchanged since batch 6 (7 genres per note_005 + addendum).
- Structural-gaps list additions per batch: 1 in batch 6, 1 in batch 7 (diminishing).

**Diminishing returns quantified:**
- Batches 1–3 (games 1–15): added major structural gaps 1–6 + note_001,
  002, 003, 004, 005 (5 observations).
- Batch 4 (games 16–20): added note_006 (1 observation).
- Batch 5 (games 21–25): added note_007, 008 (2 observations;
  composability framing + grid-mode correction).
- Batch 6 (games 26–30): added note_009 + note_005_addendum (1
  observation + 1 scope correction).
- Batch 7 (games 31–35): note_010 (this — a meta-observation about
  the process, not a new primitive).

**Implication:** **further numerics work past n=35 is low-leverage for
gap-map updates**. Continuing the sweep to n=100 is mostly useful for:
1. Edge-case genres (party, MMO-lite, educational, dating-sim-subtypes)
2. Validating that the impossible-set is truly stable
3. Building out the retro_priors catalog for training-data value

**Recommendation:**
- Option (A): Stop at n=35 or n=40 if JB agrees. Design-track has all
  the signal it needs to commit v1 priorities.
- Option (B): Continue to n=100 but **broaden the per-entry analysis**
  — more depth on compositions rather than more breadth on genres.
  Shift from "does this genre fit v0" to "what interesting mechanic
  compositions surface when re-examining already-covered genres."
- Option (C): Stop numerics; have me switch modes to support design
  track directly (e.g., sketching mechanic specs from the gap_map,
  running cross-audits per Sigma Three-Source Triangulation).

**My preference: (A) or (C).** Continuing the sweep beyond n=35
produces data the design track doesn't need yet. Switching modes puts
me on work that *does* produce new information: if the design track
wants to implement v1 top-5, I can help spec the mechanics or validate
the compiler output once it exists.

**Sigma framing:** this is Data Ceiling (v8 principle) applied to the
numerics sweep itself. I've been sweeping a parameter space (genres)
and the output metric (v1 gap candidates) has pinned. Per D1: "run the
same recipe twice on the same data. If outputs cluster, the data is
the ceiling — don't sweep, collect differently."

The *recipe* here is "enumerate genre → gap-map entries." The *data*
is the current catalog. They've pinned at 16.5% coverage and a stable
top-20 v1 list. Per Sigma: collect differently (option C) or stop
(option A).

**Flag to operator.** Will continue to n=40 in the next batch with
careful under-represented picks, then await direction.
