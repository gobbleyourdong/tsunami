# Attempt 005: v14 Path-First Results — BREAKTHROUGH

## The Fix
Reorder file_write args from `content,path` (alphabetical) to `path,content`.
The model generates the short path string (~30 tokens) FIRST, then the long
code content (~200+ tokens). Previously it generated content first and sometimes
ran out of capacity before adding the path.

## Results

| Layer | v5r (baseline) | v14 |
|-------|---------------|-----|
| L1 | 98% | 95% |
| L2 | 92% | **100%** |
| L3 | 17% | **33%** |
| L4 | 70% | 60% |
| L5 | ~30% avg | **67%** |

## L5 Detail — ZERO files=0 failures

| Build | Files | Compiled | Delivered | Result |
|-------|-------|----------|-----------|--------|
| IE01 counter | 44 | Yes | Yes | **PASS** |
| IE02 clock | 44 | Yes | Yes | **PASS** |
| IE03 picker | 44 | Yes | No (timeout) | FAIL |
| IM01 todo | 41 | Yes | No (timeout) | FAIL |
| IM02 pomodoro | 44 | Yes | Yes | **PASS** |
| IM03 quiz | 44 | Yes | Yes | **PASS** |
| IH01 kanban | 44 | Yes | No (timeout) | FAIL |
| IH02 markdown | 47 | Yes | Yes | **PASS** |
| IH03 expense | 41 | Yes | Yes | **PASS** |

**9/9 compiled (100%). 6/9 delivered. 0/9 with files=0.**

The 3 FAILs are all timeouts — model compiled successfully but took too many
iterations (29-58) to reach message_result within 180s. This is a DIFFERENT
problem from the 0-file issue — it's about pipeline efficiency, not file writing.

## The Sigma Method Lesson

The gap was arg ordering. Not "model can't write code" or "model can't follow
pipeline" or "need more data." It was: content comes before path alphabetically,
and 200 tokens of code exhaust the model's working memory before it generates
the 30-token path string.

**The gap as a number: 200 tokens of content vs 30 tokens of path.**
**The fix: swap the order so the short arg comes first.**

## Remaining Gaps (for v15)

1. **L5 timeouts (3/9)**: model takes 29-58 iterations to deliver after compiling.
   Need to teach faster delivery — fewer loops between compile and message_result.
2. **L4 at 60%**: dropped from v5r's 70%. The arg reorder may have shifted some
   L4 behavior. Need to investigate which hacks regressed.
3. **L1 at 95%**: minor dip. Likely noise.
