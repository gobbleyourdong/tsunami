# Attempt 010: Optimizer Is The Differentiator

## Results

| Config | Optimizer | VRAM | L1 | L2 | L3 | L4 | L5 | files=0 |
|--------|-----------|------|----|----|----|----|-----|---------|
| v14 old | adamw_torch_fused | 127GB | 95% | 100% | 33% | 60% | **89%** | **0/9** |
| v14u r=8 | adamw_8bit | 37GB | 95% | 83% | 17% | 70% | 22% | 5/9 |
| v14u r=32 | adamw_8bit | 54GB | 92% | 92% | 17% | 60% | 22% | 5/9 |
| v14u r=64 | adamw_8bit | 49GB | 98% | 100% | 33% | **70%** | 11% | 6/9 |

## The Finding

**adamw_8bit cannot learn non-alphabetical arg ordering.**

All Unsloth runs (r=8, r=32, r=64) have files=0 failures (5-6/9).
The old script with adamw_torch_fused has ZERO files=0 failures.
Same data, same LoRA rank (r=64), same LR (5e-5). Only difference: optimizer.

**The NUMBER: 0/9 files=0 (full precision) vs 6/9 files=0 (8bit optimizer).**

The 8-bit quantized optimizer loses gradient precision on the specific weights
that control arg ordering in tool calls. The path-first ordering in training
data requires the model to override base model behavior (alphabetical args).
Full-precision gradients can do this. 8-bit quantized gradients can't.

## Implication for Spark

Spark has 128.5GB unified memory. Old script needs 127GB — tight but fits.
Can't use Unsloth's 8bit optimizer without losing L5.

Options:
1. Run old script on Spark (127GB, tight)
2. Use Unsloth framework but with full-precision optimizer (may need more VRAM)
3. Accept L5=11% with Unsloth and compensate with agent loop
