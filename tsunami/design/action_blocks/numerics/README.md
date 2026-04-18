# Numerics brief — Action Blocks coverage + priors

> Cold-start brief for the numerics instance. Designed so you can spawn
> fresh, read this file, and start churning without needing to re-derive
> context.

## Who you are

You are the **Odd / numerical track** in an Even/Odd pair working on the
Action Blocks method. The Even instance (design track) is iterating in
`ark/tsunami/design/action_blocks/attempts/attempt_NNN.md` — read those
first, in order, before starting. They're short. The target doc is
`attempt_001`, audited in `_002`, traced end-to-end in `_003`.

Your job is to **exhaustively map the space the Even instance is
designing into.** Where you stall IS the gap measurement (Sigma
Struggle-as-Signal). Do not babysit one experiment; sweep.

## Two parallel tracks

### Track A — Catalog coverage sweep

Feed yourself a genre-spanning prompt list (see `coverage_sweep/
prompts.md` — write it if missing; target ~100 prompts across arcade /
puzzle / rhythm / platformer / sim / roguelike / fighting / tile-based /
IF / narrative / party / racing / rogueLITE).

For each prompt:
1. Read the catalog at `ark/tsunami/design/action_blocks/reference/
   catalog.ts`.
2. Attempt to write a design script in the schema at `reference/
   schema.ts` that expresses the prompted game.
3. Classify the result:
   - `expressible`   — script validates against the schema cleanly
   - `awkward`       — script validates but mechanics feel wrong-shaped
   - `impossible`    — no combination of v0 mechanics expresses this
4. If awkward or impossible, write what's missing:
   - a new mechanic type (name + one-line description)
   - a new archetype/trigger/controller
   - a new ActionRef kind
   - a compatibility gap (mechanic A + B both needed but can't coexist)

Output per prompt: `coverage_sweep/prompt_NNN.md` — the prompt, the
attempted design, the verdict, the gap list.

Output aggregate: `coverage_sweep/gap_map.md` — frequency-weighted list
of missing mechanics. Rebuild on every 10 prompts so the Even instance
can read a live snapshot.

### Track B — Retro corpus mining

JB has pre-2005 games backed up as a training corpus (user profile
memory). Exact path unknown — check `/home/jb/` for game corpus dirs,
or ask the operator when you start.

Per game:
1. Identify mechanics present. You can pattern-match from box art,
   screenshots, metadata, or (if images / video are available) vision-
   model inference. Hand-play is a last resort; this is a sweep.
2. Tag each mechanic with the nearest v0 catalog entry, OR `NEW:<name>`
   if no v0 entry fits.
3. Record: game title, year, platform, genre, mechanic set, novelty
   flag.

Output per game: `retro_priors/game_NNN.md` — title, year, tagged
mechanics, novelty notes.

Output aggregate: `retro_priors/frequency.md` — mechanic → count table,
ordered by frequency. This is the measured prior on what shipped games
actually use, against which the v0 catalog's 15 mechanics can be
audited.

## What to avoid

- **Don't tune parameters.** Mechanic param values (`base_count`,
  `rest_sec`, etc.) are not yet worth sweeping — the compiler doesn't
  run yet, so no game produces a survival-time metric. Data ceiling
  before hparam sweep (Sigma v8).
- **Don't deepen one prompt.** One design script per prompt is enough.
  Coverage beats depth here — we need the distribution, not any single
  great game.
- **Don't rewrite attempt_NNN.md.** Those are the Even instance's
  artifacts. If you want to propose a structural change, write it as
  `numerics/observations/note_NNN.md` and the Even instance will read
  it on their next pass.
- **Don't delete noise.** Failed / awkward / impossible results stay
  on disk per Maps Include Noise (Sigma v6). Mark them as such in the
  doc; do not silently discard.

## What to commit to

- Output files under `numerics/coverage_sweep/` and `numerics/
  retro_priors/` only. Never write to `../attempts/` or `../reference/`.
- Numbered attempts: `prompt_NNN.md`, `game_NNN.md`. Zero-padded to 3
  digits.
- One-line commit messages. No methodology leakage ("Even", "Odd",
  "sigma" — use "design track", "numerics track", or nothing).

## Three-source triangulation

Your data is one source. The Even instance's design is another. JB's
tacit judgment and retro-corpus (the ether, in sigma v9 terms) are the
third. Do not try to reach conclusions from coverage alone — your job
is to produce a dense gap map and let the Even instance triangulate.

When you stop:
- Leave `coverage_sweep/gap_map.md` and `retro_priors/frequency.md`
  current.
- Write `numerics/status.md` with a one-paragraph summary of where
  you stopped, what's still running, and what the Even instance should
  read first on their next pass.

That's it. Start with the attempts/ doc, read the reference/ schema
and catalog, then sweep.
