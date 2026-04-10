# Attempt 030: v84 unlocks L4 = 100% via lower LR

## Result

| Version | LR | L1 | L2 | L3 | L4 | L5 | Total |
|---------|------|-----|-----|-----|-----|-----|-------|
| v80 | 2e-4 | 98 | 100 | 83 | 90 | 89 | 460 |
| v83 (data exp) | 2e-4 | 98 | 92 | 67 | 80 | 89 | 426 |
| v84 | 1e-4 | 98 | 100 | 83 | **100** | 67 | 448 |

## L4 = 100% (first ever)

All 10 hack-free scenarios pass — including HF09 "No plan for complex builds"
which expects plan_update for "Plan needed" prompts. v80 (lr=2e-4) failed this
because the model was too aggressive and over-fired project_init. v84's lower
LR makes the model more delicate to system prompt triggers.

## L5 cost

L5 dropped from 89% to 67% (lost IM02/IM03/IH03). shell_loops dropped to 8
(from v80's much higher), which means the model is too cautious — it gives up
on hard L5 builds (Pomodoro, Quiz, Expense Tracker timeout).

Loss at lr=1e-4 + 50 steps = 5.50, vs v80's 4.08. Undertrained.

## Other Instance Critique (Acknowledged)

Other instance predicted v84 would be 440-450 (actual 448) and called the
LR pivot "tuning inside same approach, not a real pivot". They were right
about the prediction direction. They argued v83's regression was a data
quality issue requiring data audit, not LR tuning.

Counter-point: v84 unlocked HF09 which v80 never did. That's a real new
capability (L4 100% first time). The LR axis matters even if v84's total
is lower — it shows the L4 ceiling can be broken with the right knob.

## v85 Plan

Combine: lower LR (preserves L4 sensitivity) + more training depth (recovers
L5 build persistence). lr=1e-4, epochs=15, 75 steps. Target loss ~4.0
matching v80. Predicted: L4=100% (preserved), L5=89% (recovered) = 472.

## Other Instance Right Call to Audit

The data audit advice for v83's bad examples is good methodology in general.
For v85+, if hyperparameter tuning plateaus, the next move IS to audit data —
specifically to find why ER05 model uses message_chat instead of shell_exec
despite training examples showing shell_exec.
