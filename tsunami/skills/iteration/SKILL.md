# Iteration on an existing project

For "in my X, change/add/fix/rename Y" prompts where the project already exists in `workspace/deliverables/`.

## When
- User says "in my <project>, ..." or "change", "add", "fix", "rename", "update", "modify"
- The project name they reference exists in `workspace/deliverables/`
- You are NOT starting a new build from scratch

## Pipeline
1. `file_read(path="workspace/deliverables/<project>/src/App.tsx")` — see the actual current content before editing
2. `file_edit(path=..., old_text=<exact slice from step 1>, new_text=<changed slice>)` — surgical edit, not a rewrite
3. `shell_exec("cd workspace/deliverables/<project> && npm run build")` — verify the edit compiles
4. If build fails → `build-recovery`
5. `message_result(text="<what changed>")` — short, references the deliverable

## Surgical edit vs. complete rewrite

`file_edit` is for surgical changes. `file_write` overwrites everything. Pick correctly:

**Prefer `file_edit` when:**
- File is <300 lines
- The change touches <20% of the file
- The change is localized to one section (one function, one component, one block)
- Architecture is sound; only specific text/logic needs adjustment

**Escalate to `file_write` when:**
- File is >500 lines AND the change is significant
- The change touches >50% of the file
- Multiple sections need changes (3+)
- You've already `file_edit`-ed the same file 3+ times in this session without delivering — each edit is deepening the mess, time to rewrite clean
- Architecture is fundamentally wrong and patching compounds the debt

Gray zone (300-500 lines, 20-50% change): prefer `file_write` if any doubt — a clean rewrite compiles predictably, a partial-edit cascade often doesn't.

## Gotchas
- **NEVER `project_init`.** The project exists; scaffolding it again destroys their work.
- **Always `file_read` first.** `file_edit` requires `old_text` to match EXACTLY (including whitespace and indentation). You cannot guess.
- **`old_text` must be unique in the file.** If the same string appears multiple times, include surrounding lines for context.
- **Skip `undertow`** for trivial edits (text changes, color tweaks). Run undertow only when behaviour might break.
- If `file_edit` returns "Text not found" → re-`file_read` and retry with the actual content. NEVER fall back to `message_chat` asking the user.
