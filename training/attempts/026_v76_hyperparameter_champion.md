# Attempt 026: v76 hyperparameter tuning — 417 total (NEW CHAMPION)

## The Experiment
Same v73 data (16 examples). Only change: training hyperparameters.
- v73: grad_accum=16, epochs=3 → 3 training steps, loss 14.19
- v76: grad_accum=4, epochs=5 → 20 training steps, loss 8.05

## Results

| Version | L1 | L2 | L3 | L4 | L5 | Total |
|---------|-----|-----|-----|-----|-----|-------|
| v73 (prev best) | 100 | 92 | 50 | 70 | 78 | 390 |
| **v76** | **98** | **100** | **50** | **80** | **89** | **417** |

L4 +10: HF10 (undertow/QA before delivery) now passes for first time.
L5 +11: 8/9 pass. Markdown editor (IH02) passes for first time.
shell_loops: 17 (down from 23 in v73, 43 in v72).
Only failure: IH03 expense tracker (timeout 180s).

## Why It Worked
At 3 steps, the model barely adjusted weights (loss 14.19 = almost base model).
At 20 steps, the model had 6.7x more gradient updates. Loss 8.05 = learned
the training patterns without memorizing (1.44 = memorized in v72).

The "sweet spot" is loss ~8 where the model has internalized the fix-direct
pattern, pipeline flow, and oceanic behavior deeply enough to generalize,
without overfitting to the exact training examples.

## Implications
- Data was never the bottleneck — TRAINING DEPTH was
- v73's data (10 happy + 6 pipeline L3) is correct
- v74/v75 regressions were from changing data, not from training being wrong
- More steps on good data >>> more data with few steps

## Remaining Gaps
- L1 98%: T01 still returns NONE (trivial question edge case)
- L3 50%: ER03 syntax / ER05 path / ER06 css still fall to file_read
- L4 80%: HF02 research gate / HF09 plan (both expect non-build first actions)
- L5 89%: IH03 expense tracker (timeout, likely JSON parse on large content)

## Next Experiments
1. Try even more steps (40, 60) to see if L3/L4 improve further
2. Try grad_accum=2 (more steps but smaller effective batch)
3. Try epochs=10 with grad_accum=4 (40 steps)
4. If 40 steps doesn't move L3, it's a DATA gap (need different examples)
