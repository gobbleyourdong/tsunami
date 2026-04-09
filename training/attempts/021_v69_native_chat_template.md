# Attempt 021: v69 — Native Chat Template Breakthrough

## THE BOMBSHELL

Other instance discovered: **all of v14-v21 was wrong**. We were hand-rolling
the Gemma 4 tool-call format from scratch. Loss started at ~196 because the
model had to LEARN the format.

The fix: use `tokenizer.apply_chat_template(messages, tools=TOOLS)`. This
emits Gemma 4's NATIVE tool-call format that the model already knows from
pretraining. Loss starts at ~14 (8x lower) and the model leverages its
pretrained tool-calling prior instead of fighting it.

## Results

| Layer | v14r | v18 | **v69** | Δ vs v18 |
|-------|------|-----|---------|----------|
| L1 format | 95% | 98% | **98%** | tied |
| L2 Scaffold | 92% | 100% | **100%** | tied |
| L3 Recovery | 50% | 33% | **33%** | tied |
| L4 Hackfree | 70% | 60% | **60%** | tied |
| **L5 Integration** | **22%** | **22%** | **78%** | **+56** |
| **TOTAL** | 329 | 313 | **369** | **+56** |

## L5 Detail (the headline)

Previous best L5: 2/9 across all v14-v21 variants. v69:

| Case | Iters | Time | Result |
|------|-------|------|--------|
| IE01 Counter | 10 | 41s | **PASS** |
| IE02 Clock | 11 | 59s | **PASS** |
| IE03 Picker | 31 | 75s | **PASS** |
| IE04 Todo | 19 | 75s | **PASS** |
| IE05 Pomodoro | 33 | 180s | FAIL (timeout) |
| IE06 Quiz | 31 | 163s | **PASS** |
| IE07 Kanban (HARD) | 19 | 79s | **PASS** |
| IE08 Markdown (HARD) | 31 | 94s | **PASS** |
| IE09 Expense | 13 | 180s | FAIL (timeout) |
| **TOTAL** | | | **7/9 (78%)** |

Compare: v14r best run was 2/9, AND most builds hit the 61-iter cap.
v69 builds complete in **10-31 iterations** — 3-6x more efficient. The
model leverages its pretrained pipeline knowledge instead of stumbling.

## Training Stats

- **10 examples** in dataset (vs v14's 512, v16's 792)
- **3 training steps** (1 batch × 3 epochs)
- **18 seconds** total training (vs 30+ minutes for v14-v21)
- **Final train_loss: 14.33** (vs v14-v21 ~41-47)
- **Trainer: Unsloth** with LoRA r=8, LR 2e-4, adamw_torch_fused
- **Format**: native Gemma 4 chat template via `apply_chat_template`

## What Changed Format-Wise

| Aspect | v14-v21 (wrong) | v69 (correct) |
|--------|-----------------|---------------|
| Renderer | hand-rolled format strings | `tokenizer.apply_chat_template()` |
| BOS | none | `<bos>` token |
| Tool response role | `<|turn>user\n<|tool_response>...` | `<|turn>tool\n<raw>` |
| Commentary | none / message_info | brief natural language AFTER tool_call |
| Multi-tool-call | unsupported | native: multiple `<|tool_call>` per assistant turn |

The format was 95% similar but the small differences ((bos, tool role,
commentary) compounded to make v14's loss start at 196 because the model
saw it as a foreign format. v69's loss starts ~14 because the model
recognizes its own native tool-calling format.

## Why Each Variant's Lessons Still Matter

- **v18 path fixes** (commit d733c4e): still deployed, eliminate path errors
- **v19 L3 multi-turn discovery**: proves multi-turn format matters for L3
- **v69 native template**: proves the FORMAT itself was the bottleneck

## Next Steps (v70)

The trainer instance handed off these tasks:
1. **Expand example pool** (10 → 50+) for behavioral diversity
2. **Test multi-tool-call rendering** ✅ already verified — works natively
3. **Use Unsloth** ✅ already using
4. **Verify loss starts 2-8** — current is 14 average, need to log per-step

Priorities for v70:
1. Add 30-40 simple/medium app examples (single-file diversity)
2. Add 5 L3 multi-turn recovery examples in NEW format (`<|turn>tool` not `<|turn>user`)
3. Add 5 multi-tool-call examples (single response, multiple tool calls)
4. Add 3 plan-first examples (HF09)
5. Add 3 research-first examples (HF02)
6. Add 8 file_edit-style fix examples (L3 ER02/ER03/ER06)

Target: ~60 examples, sub-1 minute training, expect L3+L4 to recover to
v14r levels (50%/70%) while keeping L5 at 78%+.
