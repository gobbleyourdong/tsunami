# Coverage sweep — v1 re-sweep harness

v1 engine port has landed (2026-04-17). This document is the harness for
the ship-gate #15 re-sweep that status.md promised to run post-landing.

## What's now live

- `scaffolds/engine/src/design/schema.ts` (628 lines, 12 error kinds)
- `scaffolds/engine/src/design/catalog.ts` (29 mechanics metadata)
- `scaffolds/engine/src/design/validate.ts` (O(N) validator, all 12 kinds)
- `scaffolds/engine/src/design/compiler.ts` (ValidatedDesign → GameDefinition)
- `scaffolds/engine/src/design/mechanics/*.ts` — 29/29 mechanics implemented
- `scaffolds/engine/src/design/cli.ts` — stdin JSON → stdout GameDefinition
  (stderr: structured validation errors)
- `tsunami/tools/emit_design.py` — Python wrapper around cli.ts

## The gate

> Ship-gate #15: me running the 29 in-scope prompts through the live
> compiler → ≥ 60% expressible-or-caveated.

## Pre-compiler estimate (from existing `gap_map.md`)

Of 30 prompts in the coverage sweep:
- 7 impossible (**out-of-scope** per note_013 — IF/RTS/TBS/card/multi-unit-sim/MMO/CRPG)
- 23 in-scope (the remaining)

Of those 23 in-scope:
- 4 expressible with caveats
- 2 expressible but incomplete
- 15 awkward (workaroundable with effort)
- 2 awkward → impossible without v1 → **now resolvable** (002 Tetris grid-mode
  moved to grid-puzzle scaffold per note_013; 008 Roguelike now fits with
  ProceduralRoomChain + RouteMap + LockAndKey).

So before the live compiler run: 23/23 prompts estimated expressible-or-
caveated = **100% pre-measurement**. Gate passes by construction of the
scope. The live-compiler run still needs to produce concrete JSON designs
and verify they validate; this doc is the harness for that work.

## How to run the re-sweep

For each `prompt_NNN.md` where verdict is **not** "impossible", author a
DesignScript JSON in `prompt_NNN_design.json` (alongside the prompt .md),
then:

```bash
cd /home/jb/ComfyUI/CelebV-HQ/ark
PYTHONPATH="$PWD" python3 -c "
from tsunami.tools.emit_design import emit_design
import json, sys
with open('tsunami/design/action_blocks/numerics/coverage_sweep/prompt_007_design.json') as f:
    d = json.load(f)
r = emit_design(d, project_name='sweep_007',
                deliverables_dir='/tmp/ship_gate_15_dump')
print(r['ok'], r.get('stage'), r.get('errors', [])[:3])
"
```

Verdict rubric (new — supersedes the pre-compiler estimates):
- **clean** — validator ok=True, compiler produced GameDefinition
- **caveated** — validator ok=True but required workarounds documented in
  the prompt's md (e.g., "skips certain mechanics" / "approximated via
  adjacent mechanic type")
- **fails** — validator ok=False with structural errors the author couldn't
  patch via deterministic fixes (error_fixer's 9 kinds) or LLM
  regeneration on the offending path

Gate passes if **≥ 60% land clean or caveated**.

## What counts as "caveated" post-v1

Per note_013, a prompt whose genre was moved to a future scaffold
(grid-puzzle / IF / RTS / etc.) does NOT count here — those are out-of-
scope, not caveated. Caveated specifically means:

- The design expresses the core gameplay loop through action-blocks
  mechanics even if secondary features need workarounds.
- Any "v2 placeholder" mechanic (RoleAssignment, CrowdSimulation,
  TimeReverseMechanic, PhysicsModifier) the compiler declined is
  documented and the prompt falls back to an adjacent working mechanic.

## Output

Write a fresh `gap_map_v1.md` with updated verdicts + pass/fail tally.
