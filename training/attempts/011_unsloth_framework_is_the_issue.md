# Attempt 011: Unsloth Framework Is The Issue

## Results

| Config | Framework | Optimizer | VRAM | L5 | files=0 |
|--------|-----------|-----------|------|-----|---------|
| v14 old | HF/PEFT/TRL | adamw_torch_fused | 127GB | **89%** | **0/9** |
| v14u r=8 | Unsloth | adamw_8bit | 37GB | 22% | 5/9 |
| v14u r=32 | Unsloth | adamw_8bit | 54GB | 22% | 5/9 |
| v14u r=64 | Unsloth | adamw_8bit | 49GB | 11% | 6/9 |
| v14uf r=64 | Unsloth | adamw_torch_fused | 49GB | 11% | 8/9 |

## The Finding

**It's the FRAMEWORK, not the optimizer or rank.**

Swapping adamw_8bit for adamw_torch_fused (full precision) on Unsloth made 
no difference: 6/9 files=0 → 8/9 files=0. Same result. But the old script 
with standard HF/PEFT/TRL gets 0/9 files=0.

Unsloth's LoRA application, gradient checkpointing, or weight handling 
differs from standard PEFT in a way that prevents deep learning of 
non-alphabetical arg ordering.

## The NUMBER

- Old script: 0/9 files=0 across all L5 runs
- Unsloth: 5-8/9 files=0 across all L5 runs (4 experiments)
- The difference: 100% vs 0-33% file write success

## Implication

Cannot use Unsloth for Spark training. Must use the old HF/PEFT/TRL 
pipeline at 127GB VRAM. Spark has 128.5GB — fits but tight.

## Production Config (Final)

```
Framework: HuggingFace transformers + PEFT + TRL
Script: training/train_e4b_v3.py
Data: e4b_toolcall_train_v14.jsonl (512 examples, path-first)
LoRA: r=64, alpha=128, dropout=0
LR: 5e-5, cosine schedule, warmup 20
Optimizer: adamw_torch_fused
Batch: 1, grad_accum: 16
Epochs: 3
Max length: 16384
VRAM: 127GB (fits Spark at 128.5GB)
Eval timeout: 300s
```

Scores: L1=95%, L2=100%, L3=33%, L4=60%, L5=89%
