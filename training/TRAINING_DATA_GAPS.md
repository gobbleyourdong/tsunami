# Training Data Gaps — What the Model Needs to Learn

## Summary
80 hack touchpoints in agent.py compensate for model behavior the training data doesn't teach.
If the model learned the correct workflow, most of these become dead code.

## The Correct Workflow (what training traces should show)

```
USER PROMPT (build task)
  1. project_init(name)
  2. file_write(workspace/deliverables/{name}/src/App.tsx, FULL CODE)
  3. shell_exec with command "cd workspace/deliverables/{name} and npx vite build"
  4. IF BUILD FAILS:
      file_read(workspace/deliverables/{name}/src/App.tsx)
      file_write(workspace/deliverables/{name}/src/App.tsx, FIXED FULL CODE)
      shell_exec rebuild
  5. message_result("Done. Build passes.")
```

## Gap 1: file_edit vs file_write for error recovery (CRITICAL)
- Model behavior: build fails, file_edit with wrong find string, "text not found" x3, stuck
- Correct: build fails, file_read, file_write (full rewrite with fix), rebuild
- Need: 20+ traces showing read-then-rewrite pattern, zero file_edit for error recovery
- Replaces: SHELL_BLOCK, STALL_DETECT, NUDGE hacks

## Gap 2: Path prefix — always use full workspace path
- Model behavior: writes to src/App.tsx (relative)
- Correct: workspace/deliverables/{project}/src/App.tsx always
- Need: ALL traces must use full paths
- Replaces: PATH_FIX, _resolve_path src/ hack

## Gap 3: Project scaffolding is step 1, always
- Model behavior: sometimes file_write before project_init
- Correct: project_init is ALWAYS first for build tasks
- Need: every build trace starts with project_init
- Replaces: AUTO_SCAFFOLD (10 instances)

## Gap 4: No looping — vary approach after failure
- Model behavior: repeats same tool 3-5x
- Correct: if tool fails twice, try different approach
- Need: traces showing tool X fails then switch to tool Y
- Replaces: DEDUP, LOOP_GUARD, INFO_LOOP hacks

## Gap 5: message_chat for conversation, message_result for delivery
- Model behavior: message_info spam, multiple message_result attempts
- Correct: single clean delivery
- Replaces: INFO_LOOP, AUTO_PROMOTE hacks

## Gap 6: Research before visual builds
- Model behavior: jumps straight to coding
- Correct: search_web for references first on UI tasks
- Replaces: RESEARCH_GATE hacks

## Gap 7: Auto-wire imports
- Model behavior: App.tsx missing component imports
- Correct: App.tsx imports all referenced components
- Replaces: AUTO_WIRE (12 instances)

## Gap 8: Build command consistency
- Model behavior: npm run dev, wrong paths
- Correct: always cd workspace/deliverables/{name} and npx vite build
- Replaces: shell.py command rewrites

## Session Logs
25 sessions in workspace/.history/ documenting all failure patterns:
- 4 successful builds (positive examples)
- 1 error recovery trace (write, build fail, read, edit cycle)
- 20 failed builds showing exact failure points

## Priority
1. file_write for error recovery (fixes number 1 failure)
2. Full workspace paths
3. project_init always first
4. No tool repetition loops
5. Consistent build commands
6. Clean single delivery
7. Import wiring
8. Research before visual builds
