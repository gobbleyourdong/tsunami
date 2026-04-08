# Attempt 006: v14 Timeout Analysis

## The 3 FAIL builds — all compiled, all timed out

| Build | Iters | Time | Pattern |
|-------|-------|------|---------|
| IE03 picker | 32 | 180s | file_write x9 → shell_exec x2 → file_read loop |
| IM01 todo | 29 | 180s | file_write x2 → shell_exec → file_read/match_glob loop |
| IH01 kanban | 58 | 180s | file_write x4 → shell_exec x4 → shell_exec loop |

## What the 6 PASS builds did differently

The PASS builds (avg 52 iters, avg 146s) all eventually called message_result.
They went through the same loops (shell_exec, file_read) but broke out and delivered.

## Root Cause

The model doesn't know when to STOP fixing and START delivering. After compile
succeeds, it keeps trying to read files and rebuild instead of calling message_result.

**The NUMBER: 0/512 training examples show "build succeeds → immediate message_result".** 
In v5 training data, after a successful shell_exec build, the model usually goes to 
undertow (146 examples) or message_result (114 examples). But at L5 eval, the model 
gets a successful build result and then loops on file_read/shell_exec instead of 
recognizing it should deliver.

## Two Paths Forward

### Path A: Training data (increase build→deliver signal)
- Add more examples where shell_exec succeeds → message_result immediately
- Reduce file_read loops after successful builds

### Path B: Increase timeout
- 180s may not be enough for the 4B model's slower inference
- The 3 FAIL builds all compiled — they just needed more time
- 300s timeout could turn 3 FAILs into PASSes

### Path C: Both
- Better training for faster delivery + longer timeout for safety

## Recommendation

Try Path B first (increase timeout to 300s) — it's a config change, no retraining.
If all 3 FAILs pass with more time, the model is capable, just slow.
Then improve training data for Path A to make it faster.
