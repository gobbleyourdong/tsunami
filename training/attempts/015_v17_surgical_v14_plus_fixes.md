# Attempt 015: v17 — Surgical Fixes, v14 Base

## Lesson From v16

Adding 280 new examples (55% growth) to v14 taught the new patterns but
diluted old behaviors and over-triggered some new ones:
- **L1 correct tool: 30/40 (75%)** — down from v14r (would be ~36/40)
- **L3: 1/6 (17%)** — down from 3/6
- **L4: 6/10 (60%)** — down from 7/10
- **L5: 2/9 (22%)** — same as v14r
- L2: 12/12 (100%) — up

The 2 wins were L2 (+8) and L5 *diagnostics* (shell_loops 241→187, missing_qa
9→5) but not L5 *pass rate*. v16's bulk-add strategy was too aggressive.

## v17 Strategy

**Surgical.** v14 base (512) + ~80 targeted fixes = 592 examples. Same
training config.

### What to ADD

**A. 30 single-turn error→file_edit (L3 fix)**
Target: L3 expected file_edit but got file_read.
Format: Single user message contains the error output AND the file path.
Model's only turn is file_edit with targeted old→new replacement.
NO file_read preamble. The file context is implicit in the user message.

Example:
```
User: Build error in deliverables/counter/src/App.tsx at line 5:
      error TS2322: Type 'string' is not assignable to 'number'
      Line: const count: number = "0"
Model: file_edit(path=..., old_text='const count: number = "0"',
                  new_text='const count: number = 0')
```

**B. 10 trivial chat (L1 T01-T06 fix)**
Target: simple questions go to message_chat, not message_result.
```
User: What's 2+2?
Model: message_chat(text="4")
User: Say hello
Model: message_chat(text="Hello!")
```

**C. 15 extreme build → project_init (L1 X01-X08 fix)**
Target: complex builds should go to project_init, NOT plan_update.
These are "Build a 3D solar system / multiplayer chat / Chrome extension"
prompts where plan_update feels tempting but project_init is correct.
```
User: Build a 3D solar system with orbiting planets
Model: project_init(name="solar-system")
```

**D. 10 research-gate → search_web (L4 HF02 fix)**
Target: novel tech requests should search FIRST, not plan.
```
User: Build something using the new React Server Components feature
Model: search_web(query="React Server Components 2026 tutorial")
```

**E. 10 dedup-guard → project_init (L4 HF08 fix)**
Target: existing project should still trigger project_init (re-scaffold),
not plan_update.
```
User: Build a pomodoro timer
      [EXISTING PROJECT: pomodoro-timer]
      ...
Model: project_init(name="pomodoro-timer")
```

**F. 5 info-loop → message_chat (L4 HF06 fix)**
Target: information requests that got None in v16.

### What to KEEP from v16 (smaller doses)

**G. 15 gen_verify_stop** — shorter happy-path with explicit STOP after undertow
**H. 15 gen_happy_path_complex** — multi-file builds ending in message_result
**I. 10 gen_progressive_complex** — long trajectory with mid-build recovery

### What to DROP from v16

- **gen_plan_first** (20 examples) — over-triggered plan_update
- **gen_fails_then_edit** (30 examples) — taught file_read-first pattern that broke L3
- **gen_fails_twice_then_edit** (20 examples) — same issue
- **gen_research_first** (20 examples) — also reached for plan_update
- **gen_triple_recovery** (25 examples) — too many file_read-then-edit patterns
- **gen_break_stall** (20 examples) — too specialized

## Total v17

| Component | Count |
|-----------|-------|
| v14 base (keep all) | 512 |
| A. single-turn error→edit | 30 |
| B. trivial chat | 10 |
| C. extreme → project_init | 15 |
| D. research-gate → search_web | 10 |
| E. dedup-guard → project_init | 10 |
| F. info-loop → message_chat | 5 |
| G. verify_stop | 15 |
| H. happy complex | 15 |
| I. progressive complex | 10 |
| **Total** | **632** |

Only 120 new examples (vs v16's 280). 23% growth over v14 vs v16's 55%.
The hypothesis: less dilution, surgical targeting of the 4 specific
regressions while preserving v16's gains.

## Training Config

Same as v14/v16:
- HF/PEFT/TRL, r=64, LR 5e-5, adamw_torch_fused
- 3 epochs, max_len 16384, bs=1, ga=16

Single variable under test: the data delta.
