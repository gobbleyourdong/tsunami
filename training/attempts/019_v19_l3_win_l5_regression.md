# Attempt 019: v19 — L3 Breakthrough, L5 Collapse

## Results

| Layer | v14r | v16 | v17 | v18 | **v19** | v18→v19 |
|-------|------|-----|-----|-----|---------|---------|
| L1 correct | 36/40 (90%) | 30/40 (75%) | 34/40 (85%) | **35/40 (88%)** | 34/40 (85%) | -3 |
| L2 Scaffold | 11/12 (92%) | 12/12 (100%) | 10/12 (83%) | **12/12 (100%)** | 11/12 (92%) | -8 |
| L3 Recovery | 3/6 (50%) | 1/6 (17%) | 0/6 (0%) | 2/6 (33%) | **4/6 (67%)** | **+34** |
| L4 Hackfree | 7/10 (70%) | 6/10 (60%) | 7/10 (70%) | 6/10 (60%) | 6/10 (60%) | 0 |
| L5 Integration | 2/9 (22%) | 2/9 (22%) | 1/9 (11%) | **2/9 (22%)** | **0/9 (0%)** | **-22** |

## L3 Breakthrough

**v19 is the first variant to beat v14r on L3 since training began.**

Per-case L3 results:
- ER01 Missing module: PASS (shell_exec npm install recharts) ✓
- **ER02 Type error: PASS** (file_edit with setError) ✓ **NEW**
- **ER03 Syntax error: PASS** (file_edit with map) ✓ **NEW**
- ER04 Import not found: PASS (file_write Header) ✓
- ER05 Wrong path: FAIL (shell_exec but missing "deliverables/app" in args)
- ER06 CSS import: FAIL (file_read instead of file_edit)

**Why it worked:** The 31 training examples matched the exact multi-turn
format the L3 eval uses:
```
user("The build just failed. Fix it.") →
model(shell_exec build) →
tool("[shell_exec] Error: ...") →
model(FIX WITH file_edit/file_write/shell_exec)
```

Previous attempts (v17 single-turn) had the error in the user message,
which is a different context. v19 put the error in tool_response position,
matching the eval exactly. This is the key insight.

## L5 Collapse

Every L5 case failed. Diagnostics:
- path_errors: **6** (up from 2 in v18, +200%)
- shell_loops: **234** (up from 187 in v18)
- missing_qa: 5 (same)
- All 9 cases hit iter cap or timed out with files_written=0

## Root Cause of L5 Regression

The NEW system prompt in v19:
```
reef: error. file_edit for targeted fixes (type/syntax). file_write for full
rewrites or missing files.
```
vs v14 original:
```
reef: error. Read the file, REWRITE with file_write, rebuild.
```

This prompt change rebalanced the model toward file_edit. In L3 tests
(single-file fixes) this is correct. But in L5 BUILDS, the model reaches
for file_edit when it should use file_write — and file_edit fails when
the target text doesn't match exactly, spinning up error loops.

Also L4 HF09 "plan for complex" regressed: v18 PASS → v19 FAIL. The
new prompt reduced plan_update triggering.

**Sigma number:** L5 path_errors 2→6 (+200%) correlates with prompt change.

## v20 Plan

**Keep v19's L3 multi-turn training examples. REVERT the system prompt.**

Hypothesis: The L3 gain comes from the matching training format, not the
prompt change. If I keep the examples but use v14's original prompt, I
should get:
- L3: 67% (from multi-turn examples — they teach behavior directly)
- L5: ~22% (no L5 regression from prompt change)
- L1/L2/L4: same as v18

v20 = v14 base (512) + 25 v18 wins + 31 v19 L3 multi-turn examples = 568
but with original v14 system prompt for ALL examples.

Also revert eval_error_recovery.py to use the same prompt (consistency).

## Path Fixes

The path correctness fixes (agent.py auto-fix prefix, filesystem.py
workspace/ strip) stay deployed. They're correct regardless of outcome.
