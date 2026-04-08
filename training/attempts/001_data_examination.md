# Attempt 001: Deep Data Examination

> "The gap must be a NUMBER, not a concept."

## The Question

Why does L5 get 0 files written in 6/9 builds, when the model IS calling file_write?

## The Numbers

### Path Distribution in v5 Training Data (512 examples)

| Path Pattern | Count | % |
|-------------|-------|---|
| `deliverables/X/src/*.tsx` | 150 | 28% |
| `deliverables/X/*.html` | ~200 | 38% |
| `src/App.tsx` (relative, no deliverables/) | 18 | 3.4% |
| `./deliverables/X/*.html` | 52 | 10% |
| Other | ~92 | 18% |

**The gap: 18 examples (3.4%) teach the model to write to `src/App.tsx` without the `deliverables/` prefix.**

At L5 eval time, the workspace is `/tmp/tsunami_eval/`. Projects live at `/tmp/tsunami_eval/deliverables/X/`. When the model writes to `src/App.tsx` (relative), it creates `/tmp/tsunami_eval/src/App.tsx` — OUTSIDE the project directory. The eval counts `.tsx` files in `deliverables/X/src/` and finds 0.

### Transition Analysis: What Happens After file_write?

| Next Tool | v5 Count | % |
|-----------|---------|---|
| shell_exec (build) | 234 | 43.8% |
| file_write (another file) | 133 | 24.9% |
| plan_advance | 46 | 8.6% |
| message_chat | 38 | 7.1% |
| file_read | 26 | 4.9% |

**43.8% of the time, file_write is followed by shell_exec. This is the pipeline transition.**

But 24.9% of the time, it's followed by ANOTHER file_write. This teaches the model to chain file_writes — which is needed for multi-component builds, but also causes the file_write spam seen in L5 failures.

### Pre-scaffold Examples: ZERO

v5 has **zero** examples with pre-scaffolded projects (the `[Project 'X' already scaffolded...]` message). But L5 eval pre-scaffolds every project. The model has never seen this exact prompt format in training.

### Writes Before First Build

| Writes Before shell_exec | Count |
|--------------------------|-------|
| 0 writes | 46 |
| 1 write | 261 |
| 2 writes | 8 |
| 3 writes | 1 |

**82.6% of build examples have exactly 1 file_write before shell_exec.** This is the dominant pattern. But L5 builds often need 2-5 files (App.tsx + components). The model doesn't have enough multi-file-before-build examples.

## Root Causes (Quantified)

### Root Cause 1: Relative Path Confusion
- **18 examples** teach `src/App.tsx` (wrong for L5)
- **150 examples** teach `deliverables/X/src/App.tsx` (correct for L5)
- Ratio: 89% correct, 11% wrong
- **Fix: Remove or convert the 18 relative-path .tsx examples**

### Root Cause 2: No Pre-scaffold Training
- **0 examples** show the pre-scaffold prompt format
- L5 eval ALWAYS pre-scaffolds
- The model has never seen "Project 'X' already scaffolded" in training
- **Fix: Convert some examples to use pre-scaffold format**

### Root Cause 3: Single-file Dominance
- **261/316 (82.6%)** build examples do 1 write then build
- L5 medium/hard prompts need 2-5 files
- Model defaults to "write 1 file, deliver" pattern
- **Fix: This is deeper — need multi-file build examples, but adding them broke L5 before**

## Proposed v13 Changes (Surgical)

1. **Fix the 18 relative-path .tsx examples**: change `src/App.tsx` to `deliverables/{name}/src/App.tsx`
2. **Add pre-scaffold framing to 20 existing examples**: change the user prompt to include `[Project 'X' already scaffolded...]` without changing the tool sequence
3. **Do NOT add new examples** — v5's distribution is sacred
4. **Do NOT remove examples** — the loop patterns are needed

Total changes: modify ~38 existing examples. Net count stays at 512.
