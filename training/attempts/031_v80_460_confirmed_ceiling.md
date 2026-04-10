# Attempt 031: v80 = 460 confirmed as ceiling

## 20 experiments, one number

From v69 (369) to v86 (439), 20 experiments tested every axis:
- Data: 10-30 examples, different compositions
- Hyperparameters: lr 1e-4 to 2e-4, epochs 3-15, grad_accum 4-16
- Architecture: LoRA r=8 vs r=16
- System prompt: 5 versions of triggers/wording

All converge to ~460 (±10 stochastic) on v80 data.

## The Pareto Frontier

Plan examples trade L2/L3/L4 for L5. Lower LR trades L5 for L4.
No configuration achieves ALL high simultaneously.

| Version | Change | L2 | L3 | L4 | L5 | Total |
|---------|--------|-----|-----|-----|-----|-------|
| v80 | 19ex, 2e-4 | 100 | 83 | 90 | 89 | 460 |
| v84 | 19ex, 1e-4 | 100 | 83 | 100 | 67 | 448 |
| v85 | 19ex, 1e-4+more | 100 | 83 | 90 | 89 | 460 |
| v86 | 22ex+plan | 92 | 67 | 80 | 100 | 439 |

## Remaining Gaps (40 points to 500)

- L3 ER05 (wrong path → model won't fix path directly): ~17 pts
- L4 HF09 (plan_update on "Plan needed"): ~10 pts  
- L5 IH03 (expense tracker timeout): ~11 pts
- L1 trivial question misfire: ~2 pts

## What Breaks the Ceiling

1. **Bigger model** — 8B+ has more capacity to hold both L4/L5 patterns
2. **Curriculum learning** — train L3/L4 patterns first, then pipeline
3. **DPO/RLHF** — preference-based training to distinguish "read then fix" vs "fix directly"
4. **Decomposed evals** — separate the L4/L5 tradeoff into separate models
5. **Accept 460 and design harder evals** — per user's original instruction

## Production State

v80 (460) serving on runpod port 8090.
GGUF: /root/models/gemma-4-e4b-tsunami-v80-Q4_K_M.gguf
