# Attempt 003: v13 Results — Why Scores Changed

## Results

| Layer | v5r | v12 | v13 |
|-------|-----|-----|-----|
| L1 | 98% | 100% | 98% |
| L2 | 92% | 92% | 92% |
| L3 | 17% | 50% | 17% |
| L4 | 70% | 70% | 60% |
| L5 | ~30% | ~6% | TBD |

## Root Cause Analysis

### Q1: Why did v12 get L3=50%?

**NOT because of error recovery pattern changes.** All three versions (v5, v12, v13) have identical error recovery ratios: 28% direct fix. The error->file_read/write/edit counts are exactly the same.

v12's L3 improvement came from the **32 augmented pipeline examples** (plan_update -> project_init -> plan_advance -> file_write -> shell_exec). These examples reinforced the pipeline discipline, which made the model more likely to take action (file_edit) after seeing an error, even though the specific error->fix pattern wasn't changed.

**The NUMBER: 26/32 augmented examples follow the plan_update -> project_init -> plan_advance sequence.** This heavy reinforcement of the planned-pipeline pattern shifted the model's overall action-taking behavior.

### Q2: Why did v13 lose L4 (70% -> 60%)?

**Because the pre-scaffold framing contradicts the tool sequence.**

v13 added "already scaffolded" to 20 user prompts, but the model's FIRST tool call in those examples is still `plan_update` (17/20) or `search_web` (3/20). Zero examples respond to "already scaffolded" with `file_write`.

This teaches: "Even when told project exists, plan first."
L4 HF04 expects: "After scaffold, write code immediately."

**The NUMBER: 20/20 pre-scaffold examples call plan_update/search_web instead of file_write. This is 20 examples of conflicting signal.**

### Q3: What are v12's augmented examples?

- 26/32 follow: `plan_update -> project_init -> plan_advance -> file_write -> plan_advance -> shell_exec`
- 2/32 are search-heavy: `search_web x4 -> project_init`
- 4/32 have generate_image flows

The dominant pattern (26/32) is the **planned pipeline** — plan then build. This heavy reinforcement of "plan -> scaffold -> write -> build" is what improved L3 (more pipeline discipline) while maintaining L4 (the plan pattern doesn't conflict with hack-free behaviors).

### Q4: The 0-file mystery

Even with path auto-fix, files_written=0 in L5. The auto-fix adds the correct relative path (`deliverables/X/src/App.tsx`), but the file_write tool resolves paths relative to CWD, not workspace_dir. If the agent's CWD differs from the eval workspace, files land in the wrong place.

**This is an AGENT BUG, not a training data issue.** The 0-file problem can't be fixed with training data alone — it needs an agent-side fix to ensure file_write resolves paths relative to workspace_dir.

## Implications for v14

1. **Don't add pre-scaffold framing** — it creates conflicting signal (says "scaffolded" but model still plans)
2. **v12's augmentation approach works** — reinforcing plan->build pipeline helps L3
3. **The path fix doesn't help L5** — the 0-file issue is agent-side path resolution
4. **To fix L5's 0-file: fix the file_write tool's path resolution, not the training data**
