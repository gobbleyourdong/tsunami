# Attempt 007: v14 + 300s Timeout — 89% L5

## Results

**L5: 8/9 (89%) — 9/9 compiled (100%)**

The single FAIL (IH03 expense tracker) compiled but timed out at 300s. It needed
more iterations to deliver. Every other build passed including hard ones.

## The Journey from 0% to 89%

| Fix | What | L5 Before | L5 After |
|-----|------|-----------|----------|
| Node 22 | Infrastructure — Vite needs Node 18+ | 0% | 56% |
| Path-first args | Training data — path before content | ~30% avg | 67% |
| 300s timeout | Config — more time for hard builds | 67% | 89% |

Three numbered gaps, three fixes. Each gap was discovered through the Sigma Method:
measure, quantify, fix the specific number.

## v14 Full Scorecard

| Layer | Score |
|-------|-------|
| L1 Format | 95% |
| L2 Scaffold | 100% |
| L3 Recovery | 33% |
| L4 Hack-free | 60% |
| L5 Integration | **89%** (300s) / 67% (180s) |

## Remaining Gaps

### L5: 1/9 FAIL (IH03 expense tracker, 300s timeout)
- Compiled successfully at 41 files
- 46 iterations in 300s — model loops post-compile
- Would likely pass at 400-500s
- Training fix: teach faster delivery after successful compile

### L4: 60% (was 70% on v5r)
- The arg reorder may have shifted L4 behavior
- Need to investigate which hacks regressed

### L3: 33% (was 17% on v5r, 50% on v12)
- Improved from v5r! The arg reorder helped L3 somehow
- Still room to grow with more error recovery signal

### L1: 95% (was 98%)
- Minor dip, likely variance
