# Attempt 002: v13 Surgical Fixes

> Applied the fixes from Attempt 001 findings.

## Changes from v5 (zero additions, zero removals)

1. **18 .tsx relative paths fixed**: `src/App.tsx` → `deliverables/{name}/src/App.tsx`
   - These were teaching the model to write files outside the project directory
   - At L5 eval, this causes files_written=0 because the eval counts files in deliverables/X/src/

2. **20 examples gained pre-scaffold framing**: added `[Project 'X' already scaffolded...]` to user prompt
   - v5 had zero pre-scaffold examples
   - L5 eval always pre-scaffolds
   - Model should now recognize the pre-scaffold prompt format

## What was NOT changed
- Example count: still 512
- Tool sequences: untouched
- Code content: untouched
- Ocean terms: untouched
- All loop-teaching examples preserved

## Hypothesis
- FIX 1 should reduce 0-file failures by eliminating wrong-path writes
- FIX 2 should help the model recognize pre-scaffold builds
- Neither change introduces new patterns — they correct existing ones

## Expected Outcome
- L1-L4: should hold at v5r levels (98/92/17/70)
- L5: should improve from ~30% avg by reducing 0-file failures
- If L5 doesn't improve: the 0-file issue is NOT path-related

## Verification
- 0 remaining relative .tsx paths (was 18)
- 20 pre-scaffold examples (was 0)
- 512 total examples (unchanged)
- Syntactic: CLEAN
