# Tsunami Eval 2026-04-13 — 9-prompt tiered run

**Overall delivered: 3/9 (2/9 actual — crypto was REFUSED but eval counted the message_result).**

Tier breakdown:
- T1 (single-page): 1/4 (only watchlist's T2-sibling counts, T1 lost all 4 real)
- T2 (multi-view): 1/3 (watchlist ✓)
- T3 (complex auth): 1/2 (event ✓, course ran out of iter budget at 19/20)

## Failure categorization (resistor mapping)

Of 7 failures, 5 have landed fixes AFTER the run started (so the running process couldn't use them):

| Prompt | Fail mode | Fixed in | Status |
|---|---|---|---|
| crypto | undefined `<Alert>` ship | - | open — JSX-import validator needed |
| lunchvote | undertow nth=2 after click mutation | `20a6fad` | ready for rerun |
| pomodoro | `message_chat.text` used as file_write | `98314eb` | ready for rerun |
| chiptune | same as pomodoro | `98314eb` | ready for rerun |
| leads | `file_edit` without path (3x) | `98314eb` | ready for rerun |
| writer | same as leads | `98314eb` | ready for rerun |
| course | multi-file build iter cap | - | open — budget or skill routing |

## Projected on rerun (same prompts, current main)

~7/9 or 8/9. Lunchvote + pomodoro + chiptune + leads + writer all flip with the fixes landed during the run.

## Canonical successes

- watchlist (T2, 9i/555s) — validates auto-deliver saving a stuck post-build loop
- event (T3, 5i/576s) — first multi-page auth flow delivered clean, no intervention
