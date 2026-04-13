# In-place CWD-mode work

For tasks ABOUT files in the user's current directory — organize, summarize, rename, refactor, "what's in here" — NOT a build.

## When
- User says "organize", "rename", "summarize", "what's in", "refactor", "clean up", "list", "what does X do"
- The current directory has real files (not the empty `deliverables/` workspace)
- The task is about EXISTING content, not generating new content

## Pipeline
1. `shell_exec("ls -la")` or `shell_exec("find . -name '*.X' -not -path '*/node_modules/*'")` — see what's actually there
2. `file_read(path=...)` — examine specific files as needed
3. `file_edit(...)` or `file_write(...)` or `shell_exec("mv X Y")` — do the work in place
4. `message_result(text="<one-line summary of what changed>")`

## Gotchas
- **NEVER `project_init`.** That scaffolds a new project; the user wanted you to work on what's already here.
- **NO `undertow`.** Undertow tests built HTML; this isn't a build task.
- **Use absolute or CWD-relative paths.** Don't prefix with `deliverables/` — that path is for builds.
- **Read before writing.** For organize/rename tasks, list directory first to see what's there before any move.
- For `summarize` tasks, `file_read` enough files to actually understand the content, then deliver the summary in `message_result`.
