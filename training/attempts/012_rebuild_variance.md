# Attempt 012: Rebuild Reveals Training Variance

## Results

| Run | L1 | L2 | L3 | L4 | L5 (300s) | files=0 |
|-----|----|----|----|----|-----------|---------|
| v14 original | 95% | 100% | 33% | 60% | **89%** | 0/9 |
| v14 rebuild | 95% | 92% | **50%** | **70%** | 22% | 7/9 |

## The Finding

Same data (v14, path-first), same config (r=64, LR 5e-5, adamw_torch_fused),
different outcome. The rebuild got BETTER L3/L4 but WORSE L5.

**Training has high stochastic variance for L5.** The path-first arg ordering
is a fragile behavior that depends on the specific random initialization of
LoRA weights. Some seeds learn it deeply (0/9 files=0), others don't (7/9 files=0).

## The NUMBER

- L5 variance across 2 identical training runs: 22% to 89% (67 point spread)
- files=0 variance: 0/9 to 7/9

## Implications

1. The original v14 GGUF was the best model we ever produced — and it's gone
   (deleted during disk cleanup). **Always preserve the best GGUF.**
2. Retraining doesn't guarantee reproducing the same scores.
3. To reliably get L5>80%, either:
   - Train multiple seeds and select the best
   - Find a deterministic training config
   - Use a fixed random seed that's known to work
4. The v14 rebuild is still good for L3=50% L4=70% — best L1-L4 combo.
   Can use it for production if L5 is handled by agent loop.
