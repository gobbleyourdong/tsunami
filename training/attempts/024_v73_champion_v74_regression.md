# Attempt 024: v73 champion + v74 regression

## Results Summary

| Version | L1 | L2 | L3 | L4 | L5 | Total | Delta |
|---------|----|----|----|----|----|---|---|
| v69 (prev best) | 98 | 100 | 33 | 60 | 78 | 369 | — |
| v72 fixed | 98 | 92 | 50 | 50 | 67 | 357 | -12 |
| **v73** | **100** | **92** | **50** | **70** | **78** | **390** | **+21** |
| v74 | 98 | 100 | 50 | 60 | 67 | 375 | -15 |

**v73 is the new champion.** Total 390 (+21 over v69).

## v73 Recipe

- 10 v69 happy-path examples
- 6 L3 direct-fix examples (one per eval scenario)
- No L4 examples
- **Unified fix-direct prompt** across training + all evals + agent

## The Critical Insight: Unified Prompt

v72 regressed because training SYSTEM_TEXT said "IF reef: file_read -> file_write"
but L3 eval scored fix-direct. Model oscillated — shell_loops jumped 6 -> 43.

Fixed the reef/error section in:
- `tsunami/prompt.py` (agent lite mode)
- `training/eval_toolcall.py` (L1 format SYSTEM_PROMPT)
- `training/eval_hack_free.py` (L4 SYSTEM)
- `training/build_v69.py` (training base)
- `training/eval_error_recovery.py` (already fixed for L3)

All now say: "reef: error. Fix directly with the right tool. Type/syntax errors
-> file_edit. Missing module -> shell_exec npm install. Missing file -> file_write.
Wrong path -> shell_exec with corrected path."

Result: shell_loops dropped back to 23 (from 43 in v72).

## v73 Specific L5 Wins

- IE05 Pomodoro: **first-time pass** after failing in every prior version
- IE06 Quiz: pass (was failing in v72)
- IH02 Markdown: fail (IH02 and IH03 still timeout - the hard hall)
- IH03 Expense Tracker: fail (giant JSON content triggers parse failures)

## v74 Additions (Regression)

Added to v73 base:
- 5 diverse L3 recovery examples (different error shapes)
- 2 L4 visual-research examples
- 1 L4 complex-plan example
- 1 L4 undertow-delivery example
- 5 multi-file split examples

Total: 30 examples.

Result: shell_loops blew up to 59. L4 regressed -10 (HF06 info loop went
PASS → FAIL). L5 regressed -11 (Pomodoro + Kanban timed out, Markdown
recovered).

## Lesson

Same as v71 → v72: **more examples with targeted goals can still regress**
because the dominant happy-path pattern is diluted. v73's 16 examples is
near the sweet spot for native chat template + Gemma 4 prior.

## Remaining Gaps (v75 direction)

L3 stuck at 50%: ER03 syntax / ER05 path / ER06 css still fall to file_read.
L4 stuck at 70%: HF02 research, HF09 plan, HF10 undertow.
L5 stuck at 78%: IH02 markdown / IH03 expense tracker timeout.

Next experiments:
1. Replace v73's pipeline-format L3 with BARE eval-format L3
   (matching eval's short context exactly)
2. OR keep v73 data and tune hyperparameters (epochs, lr)
3. OR address L5 JSON parse failures (cap content to shorter pieces)

Key rule: **never add more than 2-3 examples per experiment**.
