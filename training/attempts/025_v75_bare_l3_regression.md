# Attempt 025: v75 bare-format L3 → regression to 352

## Hypothesis
v73 L3 at 50% because training L3 uses full-pipeline context
(project_init → file_write → build → error → fix) but eval uses
bare 5-message context (user + shell_exec + error → fix).
Try training on bare format to match eval exactly.

## Result
v75 = 352 total (WORST EVER): L1 98 / L2 100 / L3 50 / L4 60 / L5 44

L3 didn't improve at all. L5 COLLAPSED to 44% (from 78%).
Counter app failed for the first time ever.

## Why It Failed
The full-pipeline L3 examples in v73 serve a DUAL purpose:
1. L3: teach error → direct-fix pattern
2. L5: teach the build PIPELINE flow (project_init → write → build → fix → deliver)

Bare L3 examples only teach #1. Without #2, the model loses its
pipeline understanding and can't complete even simple L5 builds.

The 6 pipeline-format L3 examples are NOT just recovery training.
They're full end-to-end pipeline examples that INCLUDE recovery.
Removing them removes 6/16 (37.5%) of the model's pipeline knowledge.

## Updated Scoreboard

| Version | Examples | L1 | L2 | L3 | L4 | L5 | Total |
|---------|----------|-----|-----|-----|-----|-----|-------|
| v69 | 10 happy | 98 | 100 | 33 | 60 | 78 | 369 |
| v72f | 10+6L3+4L4 | 98 | 92 | 50 | 50 | 67 | 357 |
| **v73** | **10+6L3** | **100** | **92** | **50** | **70** | **78** | **390** |
| v74 | 10+6L3+14new | 98 | 100 | 50 | 60 | 67 | 375 |
| v75 | 10+6bare L3 | 98 | 100 | 50 | 60 | 44 | 352 |

## Key Insight
Every experiment is a SUBSTITUTION (v75) or ADDITION (v74).
Both hurt. v73's 16 examples (10 happy + 6 pipeline L3) are at a
LOCAL OPTIMUM. No small perturbation improves total score.

## Next Ideas (not yet tested)
1. KEEP v73 data (16 examples) + add 6 bare L3 = 22 examples
   (add bare format WITHOUT removing pipeline format)
2. Increase training steps (grad_accum 4 → 12 steps instead of 3)
3. Increase LoRA rank (r=16 instead of 8)
4. Accept 390 as ceiling for this approach, focus on harder evals
