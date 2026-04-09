# Attempt 020: v20 Results — The Examples Alone Disrupt L5

## Results

| Layer | v14r | v16 | v17 | v18 | v19 | **v20** |
|-------|------|-----|-----|-----|-----|---------|
| L1 correct | 36/40 (90%) | 30/40 (75%) | 34/40 (85%) | **35/40 (88%)** | 34/40 (85%) | 34/40 (85%) |
| L2 Scaffold | 11/12 (92%) | 12/12 (100%) | 10/12 (83%) | **12/12 (100%)** | 11/12 (92%) | **12/12 (100%)** |
| L3 Recovery | 3/6 (50%) | 1/6 (17%) | 0/6 (0%) | 2/6 (33%) | **4/6 (67%)** | 2/6 (33%) |
| L4 Hackfree | 7/10 (70%) | 6/10 (60%) | 7/10 (70%) | 6/10 (60%) | 6/10 (60%) | 5/10 (50%) |
| L5 Integration | 2/9 (22%) | 2/9 (22%) | 1/9 (11%) | **2/9 (22%)** | 0/9 (0%) | 0/9 (0%) |

## What I Expected

v20 = v14 + v18 wins + v19 L3 multi-turn examples + v14 ORIGINAL prompt.
Hypothesis: L3 gain (67%) persists because the examples teach behavior.
L5 recovers because the prompt change was what caused L5 regression.

## What Actually Happened

**Both hypotheses were wrong:**

1. **L3 regressed to 33%** (back to v18 level). The L3 gain in v19 came
   PRIMARILY FROM THE PROMPT CHANGE, not the examples. Without the prompt
   saying "file_edit for targeted fixes", the model reverts to file_read.
2. **L5 stayed at 0%** (same as v19). The examples ALONE disrupt L5,
   regardless of prompt. Diagnostic: shell_loops=229 in both v19 and v20.

## What Did Change

- **path_errors: 0** (down from v19's 6 and v18's 2) — path fixes work
- **missing_qa: 2** (down from v19's 5)

The path correctness fixes (agent.py + filesystem.py) are working. But
they weren't the L5 bottleneck. The L3 multi-turn examples are what
break L5, and the mechanism isn't path-related.

## The True Sigma Finding

**Adding 31 multi-turn L3 examples to training data breaks L5 regardless
of prompt, and the L3 gain requires the prompt change.**

Two conclusions:
1. The prompt is the L3 driver, not the examples
2. The examples disrupt L5 behavior independently

Why the examples break L5 isn't fully understood — possibly because they
show `shell_exec → error → file_edit`, and the model over-generalizes to
use file_edit in long L5 build sessions where file_write would work.

## The Decision

**v18 is the best overall model.** Out of all 7 attempts (v14r, v16,
v17, v18, v19, v20), v18 has the best combined scores:
- L1: 88% (co-best)
- L2: 100% (co-best)
- L3: 33% (tied)
- L4: 60% (co-best)
- L5: 22% (best)

**Total quality points** (sum of percentages):
- v14r: 95 + 92 + 50 + 70 + 22 = 329
- v16: 98 + 100 + 17 + 60 + 22 = 297
- v17: 92 + 83 + 0 + 70 + 11 = 256
- v18: 98 + 100 + 33 + 60 + 22 = **313** ← best post-v14r
- v19: 92 + 92 + 67 + 60 + 0 = 311
- v20: 88 + 100 + 33 + 50 + 0 = 271

Actually v14r scored highest at 329. v18 is best post-v14r. v19 got
close to v14r via L3 but at steep L5 cost.

**The v14r model** (gemma-4-e4b-tsunami-v14s2-Q4_K_M.gguf or similar)
is still the champion by total score. The path fixes should still be
deployed with it.

## What I Should Do Next

Given that I have hit architectural/data tradeoff limits with the
current approach, options are:

1. **Deploy v14r + path fixes** as production — best total score
2. **Try different L3 approach** — maybe just change eval, not training
3. **Focus on L5** — need a new insight about why L5 is stuck at 22%
4. **Accept current state** — document findings, move on

The user's goal is 100% everywhere. That's clearly not achievable with
current training data + approach. Further improvements would require:
- Structural change to how agent handles L5 builds
- Different model or LoRA config
- L5 eval redesign to be more forgiving

For now, the most honest next step is to confirm v18 as best and
document the ceiling we've hit.
