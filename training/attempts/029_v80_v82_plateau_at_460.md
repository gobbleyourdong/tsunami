# Attempt 029: Plateau at 460 across multiple v80/v82 variants

## The Plateau

v78b → v80 → v82 all converge to ~460:

| Version | Change | L1 (correct) | L3 | L4 | L5 | Total |
|---------|--------|-----|-----|-----|-----|-------|
| v78b | baseline | 100 (36) | 67 | 80 | 89 | 436 |
| v79 | + plan over-trigger | 100 (7) | 83 | 80 | 100 | 463* |
| v80 | + tight plan | 98 (34) | 83 | 90 | 89 | 460 |
| v81 | + 1 plan example | 98 (35) | 83 | 80 | 89 | 450 |
| v82 | r=16 | 98 (36) | 83 | 90 | 89 | 460 |

\* v79 = 463 only by lenient L1 metric. correct_first 7/40 is honest.

## Convergence Pattern

Different training configurations on similar data all hit ~460:
- LoRA r=8 vs r=16 — same L3/L4
- 1 plan example vs 0 — same L4 (regression on HF06 with 1)
- Training depth 48 steps — locked at this sweet spot

Conclusion: the system prompt triggers (CSS, path, visual clone)
unlock L3 ER06 and L4 HF02. The plan trigger is load-bearing for
L5 IH03 but breaks L1 if too aggressive. Beyond this, the model's
priors are too strong for marginal data/hyperparameter changes.

## Stuck Failures

- **L3 ER05** (wrong path → model says shell_exec but uses old path
  OR uses message_chat). ~50% chance of either failure.
- **L4 HF09** (plan_update for "Plan needed") — system trigger present,
  training example present, but model still does project_init.
- **L5 IH03** (expense tracker) — only passes when plan trigger fires
  for the build itself (gives the model structure). v79 had this, v80+ doesn't.
- **L5 IH02** (markdown editor) — sometimes passes, sometimes times out.
  Stochastic.

## What Hasn't Been Tried

1. Lower LR (1e-4 or 5e-5 instead of 2e-4)
2. More plan_update training examples (3-5 instead of 0/1)
3. Combining v74's broader examples with v80's system triggers
4. Different prompt phrasing (more imperative)
5. Training on bigger model variant
6. Fixing the eval scoring bug (use correct_first as L1 metric)

## Honest Score Comparison

If we use `correct_first` instead of `produced_tool_call` for L1:
- v78b: 90 + 100 + 67 + 80 + 89 = 426
- v79:  17.5 + 100 + 83 + 80 + 100 = 380.5
- v80:  85 + 100 + 83 + 90 + 89 = 447
- v82:  90 + 100 + 83 + 90 + 89 = 452

By honest scoring, **v82 is the best at 452** and v79 is the worst at 380.

But by the eval's pct, v79 = 463 (champion) and v82/v80 = 460.

The eval scoring bug favors models that produce ANY tool call, even
if wrong. This rewards v79's plan_update spam.
