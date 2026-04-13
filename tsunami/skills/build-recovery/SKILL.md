# Recover from a build failure

When `shell_exec` build returns an error, diagnose it and act with the right corrective tool. NEVER fall back to `message_chat` saying "I'll look into it."

## When
- Last `shell_exec` (build/install/test) returned non-zero with an error message in stdout/stderr
- Error message mentions a specific cause (missing module, syntax error, type error, missing file)

## Pattern → Action

| Error pattern | Tool | Args |
|---|---|---|
| `Cannot find module 'X'` / `error: Could not resolve "X"` | `shell_exec` | `cd workspace/deliverables/<project> && npm install X` |
| `vite: command not found` | `shell_exec` | re-run with `npx vite build` |
| `cd: <path>: No such file or directory` | `shell_exec` | re-run with corrected path (verify with `ls workspace/deliverables/`) |
| `error TS<N>: ...` (type error) | `file_edit` | targeted fix at the line:col in the error |
| `Unterminated JSX contents` / `Expected '</X>'` | `file_edit` | add the missing closing tag |
| `Unexpected token` at a specific line | `file_read` first to see the line, then `file_edit` |
| `[Errno 28] No space left on device` | `shell_exec` | `rm -rf node_modules/.cache` then retry |

## After the fix
- ALWAYS re-run `shell_exec` build to verify the fix worked
- If the rebuild still fails with a different error → repeat: pattern-match, fix, rebuild
- After 3 failed fix attempts on the same file → stop and `message_chat(done=false)` describing the impasse to the user

## Gotchas
- **Read the error message literally.** If it says `Cannot find module 'react-beautiful-dnd'`, the fix is `npm install react-beautiful-dnd`, not `npm install react-dnd-kit`.
- **Don't blame React or Vite** when the error names a specific cause. The error is true.
- **One fix per turn.** Don't combine `file_edit` + `shell_exec` in one tool call — split.
