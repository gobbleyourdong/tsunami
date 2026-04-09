# Attempt 009: LoRA Rank Comparison — r=8, r=32, r=64

## Results

| Config | Params | L1 | L2 | L3 | L4 | L5 (300s) | files=0 |
|--------|--------|----|----|----|----|-----------|---------|
| r=8 Unsloth (LR 2e-4) | 21M | 95% | 83% | 17% | **70%** | 22% | 5/9 |
| r=32 Unsloth (LR 2e-4) | 85M | 92% | 92% | 17% | 60% | 22% | 5/9 |
| **r=64 old (LR 5e-5)** | 169M | 95% | **100%** | **33%** | 60% | **89%** | **0/9** |

## The Finding

**It's not the LoRA rank — it's the learning rate.**

Both r=8 and r=32 with Unsloth's LR 2e-4 have identical L5 (22%) and identical
files=0 count (5/9). Quadrupling the rank from 8 to 32 didn't help L5 at all.

But r=64 with LR 5e-5 gets 89% L5 with ZERO files=0 failures.

**The NUMBER: LR 2e-4 vs LR 5e-5 = 4x difference in learning rate.**

Higher LR learns fast (Unsloth loss reaches 0.86 vs old script's 15) but 
doesn't deeply internalize the arg ordering. The model memorizes the surface 
pattern but under inference pressure (long multi-turn contexts), it reverts to 
base model behavior (content before path).

Lower LR with more parameters = slower convergence but deeper adaptation.

## Recommendation

Keep our old training script settings (r=64, LR 5e-5, adamw_torch_fused).
The Unsloth framework is fine for VRAM savings but must use our hyperparameters.

Next experiment: Unsloth framework + r=64 + LR 5e-5 (best of both worlds).
