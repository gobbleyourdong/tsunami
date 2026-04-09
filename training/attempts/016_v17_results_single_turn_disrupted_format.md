# Attempt 016: v17 Results — Single-Turn Examples Disrupted Format

## Results vs v16

| Layer | v14r | v16 | v17 | v16→v17 |
|-------|------|-----|-----|---------|
| L1 correct | ~36/40 (90%) | 30/40 (75%) | **34/40 (85%)** | **+10** |
| L1 valid | 38/40 (95%) | 39/40 (98%) | 37/40 (92%) | -6 |
| L2 Scaffold | 11/12 (92%) | 12/12 (100%) | 10/12 (83%) | -17 |
| L3 Recovery | 3/6 (50%) | 1/6 (17%) | **0/6 (0%)** | -17 |
| L4 Hackfree | 7/10 (70%) | 6/10 (60%) | **7/10 (70%)** | **+10** |
| L5 Integration | 2/9 (22%) | 2/9 (22%) | 1/9 (11%) | -11 |

### L5 diagnostics
| Metric | v16 | v17 | Delta |
|--------|-----|-----|-------|
| path_errors | 2 | **6** | **+200%** |
| shell_loops | 187 | 176 | -6% |
| missing_qa | 5 | 4 | -20% |
| avg_iters | 48.2 | 46.8 | -3% |
| avg_time_s | 156.8 | 175.8 | +12% |

## What Went Wrong

### 1. Single-turn examples disrupted format learning

v17 added 90 single-turn examples (each with 1 tool call). These were:
- 30 error→file_edit
- 15 trivial chat→message_chat
- 20 extreme→project_init
- 10 research→search_web
- 10 dedup→project_init
- 5 info→message_chat

The v14 base had essentially no single-turn examples (min 1, but virtually
all have 3+ calls). The sudden introduction of 90 single-turn examples may
have taught the model that short responses are OK, weakening the careful
path-first arg structure.

**Sigma number:** path_errors 2→6 (+200%). This is a format regression.
L5 avg_time also jumped 12% (156→175s) — model producing longer/malformed
output per call, hitting timeouts more.

### 2. L3 error-edit training in wrong format

I discovered (after v17 trained) that L3 eval uses a **multi-turn context**:
```
system + user("The build just failed. Fix it.") +
assistant(shell_exec build) + tool(error text) +
[MODEL RESPONDS HERE with file_edit]
```

My v17 single-turn examples put the error text in the **user message**
directly. This is the wrong context format. The model trained on my examples
sees "error message as user input" and reaches for file_read (familiar v14
pattern). But the L3 eval puts the error as a tool_response after a prior
shell_exec — a completely different context that my training never touched.

**Sigma number:** v14 only has 2 examples matching the L3 "fix it" pattern,
and BOTH use file_read → file_write (not file_edit). The pattern the eval
wants isn't in training data at all.

### 3. Trivial chat examples targeted wrong tool

I added "Thanks, that's all" → message_chat. But v14 correctly uses
message_result for that (it's a completion signal, not chat). My addition
moved v14 from T05 PASS → v17 T05 FAIL.

**Sigma number:** T04, T05 regressed from PASS → FAIL because my training
overrode v14's correct message_result behavior.

## Wins That Worked

### L1 extreme→project_init (+10)
The 20 examples I added for "Build a 3D solar system" → project_init worked.
v16 had 5 extreme fails with plan_update. v17 has 1. Net +4 extreme PASSes.

### L4 HF08 dedup guard (+10)
The 10 existing-project→project_init examples taught the dedup behavior.
v16 FAILed HF08 with plan_update. v17 PASSes.

## v18 Strategy: MINIMAL Delta From v14

Drop everything that caused regression. Keep only what provably helps:
- v14 base (512, unchanged)
- **+15 extreme→project_init** (proved helpful, L1 +10)
- **+10 dedup→project_init** (proved helpful, L4 HF08)
- **REMOVE all single-turn error-edit** (caused L3 regression)
- **REMOVE all trivial chat fixes** (overrode v14's correct behavior)
- **REMOVE all research-gate and info-chat fixes** (didn't help)
- **REMOVE all L5 long-trajectory fixes** (didn't help either)

Total: 512 + 25 = **537 examples**. 5% growth over v14 (vs v16's 55%, v17's 23%).

Single hypothesis: **the minimum effective dose**. If this v18 approach yields
L1≈85%, L2≈92%, L3≈50%, L4≈80%, L5≈22%+, we've identified the surgical
fixes that don't disrupt v14's learned behaviors.

If this works, next step is to carefully design L5 fixes that match the
real L5 eval dynamics (timeout pressure, iter cap) — but that's a later
experiment after establishing the baseline.
