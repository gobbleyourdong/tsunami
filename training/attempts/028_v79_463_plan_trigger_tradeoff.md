# Attempt 028: v79 = 463 — system prompt triggers breakthrough with caveat

## Results

| Version | L1 pct | L1 correct | L2 | L3 | L4 | L5 | Total |
|---------|--------|-----------|-----|-----|-----|-----|-------|
| v78b | 100 | 36/40 | 100 | 67 | 80 | 89 | 436 |
| v79 | 100 | 7/40 | 100 | 83 | 80 | **100** | **463** |

## The Wins

- **L5 100%**: 9/9 all pass, INCLUDING IH03 expense tracker (first time ever).
  Pomodoro, Kanban, Markdown, Expense tracker — all green.
- **L3 83%**: CSS trigger worked perfectly. ER06 CSS import now passes.
  ER03 continues to pass. Only ER05 (wrong path) still fails.
- **L4 HF02 (research gate)**: First-ever pass. Visual clone trigger works.
- **L4 HF09 (plan gate)**: Passes — plan trigger works here.

## The Caveat

The "Complex builds → plan_update FIRST" trigger is OVER-FIRING.
L1 correct_first dropped from 36/40 to 7/40. Medium/hard/extreme
format tests expect project_init but the model does plan_update
because every build looks "complex" enough.

L4 also regressed on two tests:
- HF04 Code-write gate: expected file_write, got plan_update
- HF08 Dedup guard: expected project_init, got plan_update

Net L4: 8/10 (same as v78b) but DIFFERENT tests passing.

## Why Score Still Shows 463

The eval_all.py format scoring uses `passed = produced_tool_call`
(lenient — counts any valid tool call). So L1 "pct" stays at 100%
even though the tool is WRONG on 33 of 40 tests.

If we used correct_first as the metric, v79 L1 would be 17.5% and
the total would be ~380, WORSE than v78b.

But per the current scoring convention, v79 = 463 (new champion).

## Triggers Added (build_v69.py SYSTEM_TEXT)

```
- Visual clones ("looks like X", "style of Y") → search_web FIRST
- Complex builds (3+ features, multi-state) → plan_update FIRST
- Simple single-component builds → go straight to project_init
- CSS resolution errors → file_edit directly
- Wrong path (cd fails) → shell_exec (NEVER message_chat)
```

## v80 Plan

TIGHTEN the plan trigger. Options:
1. Remove plan trigger entirely. HF09 regresses but L1 recovers.
2. Require explicit keywords: "plan", "planning needed", "multi-step"
3. Add negative examples (training data showing "simple build" → project_init)

The L5 100% breakthrough is valuable — need to understand if it came from
the CSS trigger (likely) or the plan trigger (unlikely but possible).
Test by removing plan trigger only.

## L5 Integration Detail

ALL 9 PASS:
- IE01 Counter, IE02 Clock, IE03 Color, IE04 Todo — pass
- IE05 Pomodoro, IE06 Quiz — pass
- IE07 Kanban, IE08 Markdown — pass
- **IH03 Expense Tracker — PASS (first time ever)**
