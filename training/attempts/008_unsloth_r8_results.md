# Attempt 008: Unsloth r=8 vs Our r=64

## Results

| Layer | v14 (r=64, LR 5e-5) | v14u (r=8, LR 2e-4) |
|-------|---------------------|---------------------|
| L1 | 95% | 95% |
| L2 | **100%** | 83% |
| L3 | **33%** | 17% |
| L4 | 60% | **70%** |
| L5 (300s) | **89%** | 22% |

## Analysis

### r=8 is too small for path-first arg ordering
The v14 training data has file_write args in `path,content` order (not alphabetical).
With r=64 (169M params), the LoRA adapter can fully override the base model's
alphabetical preference. With r=8 (21M params), it can't — the model reverts
to generating content first and often forgets the path.

**The NUMBER: 5/9 L5 builds had files=0 on r=8 vs 0/9 on r=64.**

### r=8 is better for L4 routing decisions
L4 tests single-turn routing (search vs build, plan vs scaffold). Smaller LoRA
preserves more of the base model's general reasoning while learning the specific
routing patterns. r=64 over-specializes on the training data distribution.

### Unsloth training is faster
- 25 min total vs 38 min (old pipeline)
- 37GB VRAM vs 127GB
- But GGUF export failed (interactive prompt issue)

## Recommendation
Try r=32 with Unsloth — middle ground. Or use our existing pipeline with r=64 
but adopt Unsloth's LR (2e-4) and optimizer (adamw_8bit).
