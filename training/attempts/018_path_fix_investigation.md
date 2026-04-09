# Attempt 018: Path Fix Investigation — L5 Has Deeper Issues

## What I Tried

After v18 eval showed 2/9 L5 with files=0 on most fails, I suspected the
agent's auto-fix path prefix bug (`workspace/deliverables/...`) was the
culprit. Applied two fixes:

1. **agent.py**: auto-fix uses `deliverables/{project}/src/App.tsx` (not
   `workspace/deliverables/...`), removed `_project_init_called` guard so
   pre-scaffolded cases get the auto-fix. (Re-applied commit fe09e13.)
2. **filesystem.py**: `_resolve_path` now also strips literal `workspace/`
   prefix, handling the v14 training data convention regardless of
   actual workspace_dir name.

## What I Found

Path fix didn't help. Still 0/3 passing on the initial cases.

### Debug instrumentation revealed:
- Counter case: model outputs **absolute paths** `/tmp/tsunami_eval/deliverables/counter-plus-minus/src/App.tsx` (correct!)
- Clock case: model outputs mix of `src/App.tsx`, `workspace/deliverables/digital-clock/src/App.tsx`, and no-path (auto-fix fires)
- All cases: writes ARE going to the right location

### The real issue: project_init re-scaffolding
Counter case tool sequence:
```
match_glob → file_read → match_glob → project_init → match_glob → file_write → file_read × 8
```

The model calls `project_init("counter-plus-minus")` at iter 4, which
**re-scaffolds the already-pre-scaffolded project**. This likely wipes
the scaffold's src/App.tsx. Then the model writes ONCE at iter 6, then
spends 55 iters reading files.

After the eval completes, `project/src/` has 0 tsx files because:
- pre-scaffold created src/App.tsx (template)
- model's project_init call wiped it (re-scaffold)
- model's single file_write landed somewhere
- whatever got written got overwritten/deleted by cleanup

## The Pattern

The L5 files=0 failures have a consistent tool pattern:
1. Pre-scaffold already put files in src/
2. Model sees files, explores
3. Model calls project_init anyway (dedup guard doesn't stop this in
   all cases)
4. Project gets re-created
5. Model writes ONCE, then gets stuck in read loops

## Why This Isn't Easily Fixable

- Training data fix: add "don't call project_init on existing projects"
  examples. But v14 has some of these already and still fails.
- Agent fix: already has dedup guard on project_init, not catching all
  cases.
- Eval fix: could be done (don't reset src/ on re-scaffold) but that
  changes the test, not the model.

## Decision

**Stop debugging L5 eval internals. Accept L5 at ~22% baseline.**

L5 has variance-driven 2/9 ceiling across v14r, v16, v17, v18. Individual
cases swap but total never improves. The model CAN build (Picker, Quiz,
Kanban all pass sometimes) but the 61-iter cap + eval-side wipe interactions
cap the pass rate.

Focus energy on **L1/L2/L3/L4 improvements** where the signal is clearer
and gains are reproducible:
- v18 achieved: L1 88%, L2 100%, L3 33%, L4 60%
- Remaining gaps: L3 (33→100), L4 (60→100)

## Path Fixes Kept

Even though L5 didn't improve, the path fixes are MORE CORRECT and
should stay deployed:
- `deliverables/` prefix in auto-fix (was `workspace/deliverables/`)
- Literal `workspace/` strip in `_resolve_path`
- No `_project_init_called` guard on auto-fix

These make path handling consistent across training data conventions
and deployment configurations. Not a hack — a correctness fix.
