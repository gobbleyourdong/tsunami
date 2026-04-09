# Attempt 013: The Post-Write Trajectory Gap

## The Setup

v14 rebuild seed 1 (attempt 012) produced the best-ever L1-L4 (L3=50%, L4=70%)
but L5 collapsed to 22%. The variance across rebuilds (22%-89%) hid a deeper
issue. Rather than roll dice on seed 3, I interrogated the L5 failure traces.

## The Numbers

### v14 training data structure
| Metric | Value |
|--------|-------|
| Total examples | 512 |
| Max tool calls per example | **24** |
| Avg tool calls per example | **5.8** |
| Examples with 2+ file_writes | 83 (16.2%) |
| Examples with 10+ tools | 74 |
| Examples with 20+ tools | **10** |
| Uses undertow | 30.1% |
| Uses plan_update | 14.5% |

### L5 eval behavior (v14r)
| Metric | Value |
|--------|-------|
| Avg iterations | **54.6** |
| Shell loops | **241** |
| Stalls (3x repeat) | **375** |
| Missing QA | 9/9 |
| Build attempts | **0** (!!) |
| Path errors | 1 (path-first WORKED) |

### After file_write next-tool distribution
| Next tool | % |
|-----------|---|
| shell_exec | 43.8% |
| file_write | 24.9% |
| plan_advance | 8.6% |
| undertow | **0.7%** |
| message_result | **1.1%** |

## The Finding

**Training max length is 24 tools. L5 eval runs 54.6 iters on average.
Model runs 2.3x longer than anything it saw in training.**

When iteration 25+ hits, it has no template. Falls back to base-model: spam
file_write (counter: 40 identical writes rejected by dedup), or spam
shell_exec (clock: 45 consecutive after successful build).

Root cause is NOT path-first arg ordering (1 path error total — learned
cleanly). It's that training never taught the closing sequence:

> ...write -> shell_exec(build) -> undertow -> message_result. STOP.

Only 30% use undertow. Only 1.1% of post-write transitions go to
message_result. Model has no strong signal for "now deliver and stop."

### L3 sub-finding

L3 failures (ER02/03/06) all show "Expected file_edit, got file_read."
v14 has 534 file_write vs 45 file_edit — 12:1 ratio. System prompt even
says "reef: error -> file_read -> file_write (full rewrite)" — reinforcing
full-rewrite bias. Model doesn't reach for file_edit because training
barely features it.

### L4 sub-findings

- HF02 research gate: jumps to project_init. v14 has search_web calls but
  rarely as the first action.
- HF09 plan-first: jumps to project_init. Only 14.5% use plan_update.
- HF05 shell loop break: keeps calling shell_exec after failures. ZERO v14
  examples with 3+ consecutive same-tool spam.

## The Fix: v16

v16 = v14 (all 512) + 280 new targeted examples = **792 total**.

### New generators
| Generator | Count | Target gap |
|-----------|-------|------------|
| gen_happy_simple | 25 | Simple happy path + STOP |
| gen_happy_medium | 25 | 8-file happy path |
| gen_happy_complex | 25 | 18-file happy path |
| gen_fails_then_edit | 30 | L3 file_edit-on-error |
| gen_fails_twice_then_edit | 20 | Multi-round recovery |
| gen_research_first | 20 | L4 HF02 |
| gen_plan_first | 20 | L4 HF09 |
| gen_break_stall | 20 | L4 HF05 |
| gen_verify_stop | 15 | L5 STOP after undertow |
| gen_progressive_complex | 30 | Long trajectory + mid-build recovery |
| gen_triple_recovery | 25 | 3 rounds read->edit->build |
| gen_long_complex_plain | 25 | Plain 20+ tool complex build |

### Length distribution
| Metric | v14 | v16 new | v16 combined |
|--------|-----|---------|--------------|
| Max | 24 | **27** | **27** |
| Avg | 5.8 | 15.9 | 9.4 |
| 15+ tools | 30 | 128 | **158** |
| 20+ tools | 10 | 100 | **110** (11x) |
| 25+ tools | 0 | 30 | **30** (new) |

### Invariants verified
- All 2624 file_write calls path-first
- All 195 file_edit calls path-first
- All 280 new examples end with message_result
- Same canonical system prompt as v14

## Hypothesis

If v16 closes the post-write trajectory gap, L5 should improve at the mean
(not just best-seed): model learns write->build->verify->deliver->STOP.
L3 should improve because file_edit-on-error now has 195+ examples. L4
HF02/HF05/HF09 should improve via dedicated generators.

Keep config identical to v14:
- HF/PEFT/TRL (not Unsloth - attempt 011)
- r=64, LR 5e-5, adamw_torch_fused (attempts 009-010)
- 3 epochs, max_len 16384

The single variable under test is the training data.
