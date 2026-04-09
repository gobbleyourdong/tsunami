# Attempt 014: v16 Results — Overfitting on New Patterns

## Results (L1-L4 only, L5 TBD)

| Layer | v14r | v16 | Delta |
|-------|------|-----|-------|
| L1 Format | 38/40 (95%) | ~32/40 (80%) | **-15** |
| L2 Scaffold | 11/12 (92%) | 12/12 (**100%**) | **+8** |
| L3 Recovery | 3/6 (50%) | 1/6 (17%) | **-33** |
| L4 Hack-free | 7/10 (70%) | 6/10 (60%) | **-10** |

## The Sigma Numbers — What Broke

### L1 regression: 8 new failures
- **5x trivial (T01-T06):** message_result expected, model returned NONE or message_chat
- **5x extreme (X01,X02,X05,X06,X08):** project_init expected, model returned **plan_update**

### L3 regression: all file_edit failures
- ER02 Type error → file_read (expected file_edit) — same as v14r
- ER03 Syntax error → file_read (expected file_edit) — same as v14r
- ER04 Import not found → shell_exec (expected file_write) — NEW FAIL (v14r PASSED)
- ER05 Wrong path → message_chat (expected shell_exec) — NEW FAIL (v14r PASSED)
- ER06 CSS import → file_read (expected file_edit) — same as v14r

### L4 regression
- HF02 Research gate: plan_update (expected search_web) — v14r: project_init
- HF05 Shell loop: match_glob (same as v14r)
- HF06 Info loop: None (no tool) — NEW FAIL
- HF08 Dedup guard: plan_update (expected project_init) — NEW FAIL
- HF09 Plan for complex: **PASS** — v14r FAILED this (v16 won this one)

## Root Cause

v16 added 280 new examples targeting specific gaps. Three kinds of bleed-through:

### 1. plan_update over-training (+20 gen_plan_first examples)
My training pattern was "complex task → plan_update FIRST". Model generalized:
- Any hard/extreme task → plan_update (breaks L1 X01-X08)
- Research-gate task → plan_update instead of search_web (breaks HF02)
- Existing project task → plan_update instead of project_init (breaks HF08)
- But: correctly uses plan_update for explicitly-complex builds (HF09 PASS)

**Sigma number:** 5/8 extreme tasks in L1 went to plan_update = 62% over-trigger rate.

### 2. file_read→file_edit taught as TWO-STEP pattern (+50 recovery examples)
My gen_fails_then_edit and gen_triple_recovery had the pattern:
```
shell_exec(build fails) → file_read(diagnose) → file_edit(fix) → shell_exec(retry)
```
Model learned this. BUT L3 eval is **single-turn**: "here's an error message,
what tool?". Model outputs file_read (first step of learned pattern) and the
eval never sees file_edit (second step). Result: **all 3 file_edit-expected
tests fail with file_read**.

**Sigma number:** 3/3 "expected file_edit" tests failed with file_read (100% miss).

### 3. Dilution of clean v14 patterns
- T01-T06 trivial chat responses: v14r got these right. v16 has many more
  "build" examples that taught message_result as terminal, and the model
  now conflates trivial chat messages with build completions.
- ER04/ER05: v14r patterns (shell_exec for path error, file_write for import)
  got weakened by v16 favoring file_edit.

## The Lesson

**Adding N new examples to teach a new pattern can REMOVE behaviors taught in
the original data — even when the original data is still in the set.** With
792 examples and 3 epochs, the new patterns carry disproportionate weight
when they're highly consistent (all 30 gen_triple_recovery examples use the
exact same file_read-before-file_edit sequence).

Solutions:
1. **Balance positive/negative examples**: For every "use plan_update here"
   example, add "DO NOT use plan_update here" examples (simple build → project_init).
2. **Teach single-turn L3 correctly**: Add examples where the context already
   has the file content, and the error message arrives → direct file_edit
   with no file_read preamble.
3. **Preserve v14 behaviors**: When adding new patterns, validate the OLD
   patterns still generate correctly. Could use a "retention set" of v14-style
   tests during data generation.

## Next: v17

Will design after L5 result. If L5 improved significantly from v14r's 22%,
v16 is still a net improvement and v17 is a refinement. If L5 flat or worse,
v16's approach needs deeper revision.
