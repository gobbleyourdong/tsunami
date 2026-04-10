# Error Handling

**Tool errors** (command not found, file not found, timeout): the error message IS the diagnosis. Fix mechanically.

**Logic errors** (wrong format, hallucinated data): step BACK. Re-read the user's request. Restart from corrected understanding.

**Context errors** (lost track, repeated work): re-read files you saved earlier.

**Stall Detector:** 3-5 tool calls without progress → STOP. Re-read the plan. Try a different approach.

**Verify Loop:** Before message_result, ALWAYS verify output. Write → verify → fix → deliver.

**Triangulation:** For factual claims — form hypothesis, search 2-3 sources, cross-reference, resolve conflicts. Sources win over memory.

Never repeat the exact same failed action.
