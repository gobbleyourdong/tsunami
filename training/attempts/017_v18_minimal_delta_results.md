# Attempt 017: v18 Minimal-Delta Results

## Final Results

| Layer | v14r | v16 | v17 | **v18** |
|-------|------|-----|-----|---------|
| L1 format (valid) | 38/40 (95%) | 39/40 (98%) | 37/40 (92%) | 37/40 (92%) |
| **L1 correct** | ~36/40 | 30/40 (75%) | 34/40 (85%) | **35/40 (88%)** |
| L2 Scaffold | 11/12 (92%) | 12/12 (100%) | 10/12 (83%) | **12/12 (100%)** |
| L3 Recovery | 3/6 (50%) | 1/6 (17%) | 0/6 (0%) | **2/6 (33%)** |
| L4 Hackfree | 7/10 (70%) | 6/10 (60%) | 7/10 (70%) | **6/10 (60%)** |
| L5 Integration | 2/9 (22%) | 2/9 (22%) | 1/9 (11%) | **2/9 (22%)** |

## The Story

v18 = v14 (512) + 25 surgical examples (15 extreme→project_init + 10 dedup→project_init) = 537.

### Wins
- **L1 correct 88%** (best of any v14-derivative — extreme examples cleanly
  taught the pattern without collateral damage)
- **L2 Scaffold 100%** (matched v16's best, recovered from v17's 83%)
- **L3 Recovery 33%** (recovered from v17's 0%, gained 2 passes back)

### L4 regression (vs v17's 70%)
v17 had 7/10 because:
- HF08 dedup PASSed (my 10 examples)
- HF06 info loop FAILed
- HF10 missing QA PASSed

v18 has 6/10 because:
- HF08 dedup **FAILed** (model chose message_chat instead)
- HF06 info loop **PASSed** (no info examples now)
- HF10 missing QA **FAILed** (model chose file_edit)

**Sigma oddity**: Same 10 dedup examples in v17 → HF08 PASS.
Same 10 dedup examples in v18 → HF08 FAIL. The difference is the rest
of v17's training data (research/trivial/long-trajectory examples)
apparently **reinforced** the dedup pattern indirectly. Removing them
weakened it. This is non-obvious training data interaction.

### L5 stuck at 2/9 (22%)

This is the crucial bottleneck. All 5 variants (v14r, v16, v17, v18)
score 1/9 or 2/9. Variance is on which test passes:
- v14r: IE02 Clock + 1 other
- v16: IE02 Clock + IH01 Kanban
- v17: IH01 Kanban only (1/9)
- v18: IE02 Clock + IM01 Quiz (new!)

**L5 failure modes (v18):**
1. **Iter cap hit (iter=61)** — IE03 Picker, IE05 Pomodoro, IE08 Markdown.
   Model makes 61 tool calls but never compiles + delivers.
2. **Timeout hit (time=180s)** — IE01 Counter, IE04 Todo, IE07 Kanban,
   IE09 Expense. Model is slow per call or got stuck.

Both modes point to the same underlying issue: **model is too chatty/verbose
during builds**.

## Discovery: 180s vs 300s Timeout

The L5 eval defaults to 180s per case. The original v14 champion (L5=89%)
was run with **300s** per the historical notes. I'm comparing oranges to
apples when I compare v18's 22% to the champion's 89%.

Re-running v18's L5 with `--timeout 300` to get a fair comparison. This
is NOT changing the model — it's measuring it with the same yardstick
v14 used.

## Hypothesis for v19

If v18 @ 300s gets significantly better L5, then the model IS capable,
just needs more time. Next experiments:
1. Train with "short build" patterns — 5-10 tools max, explicit brevity
2. Reduce file_write content length in training (shorter content)
3. Accept 300s as the target eval timeout

If v18 @ 300s still stuck at ~22%, the model fundamentally can't
complete multi-file builds in any reasonable time. Different approach
needed (maybe a bigger model, or different architecture).
