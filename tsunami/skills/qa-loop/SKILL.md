# QA loop — recover from undertow FAIL

When `undertow` returns FAIL with a specific issue, fix that exact issue and re-verify. NEVER deliver after a FAIL without a passing re-verify.

## When
- Last `undertow` returned FAIL with text describing what's wrong
- Examples: "only 2 columns visible", "Add button has no onClick", "console error: missing key prop"

## Pipeline
1. Read undertow's FAIL message literally — it tells you what to fix
2. `file_read(path="workspace/deliverables/<project>/src/App.tsx")` — confirm current state of the offending code
3. `file_edit(path=..., old_text=<exact failing slice>, new_text=<fixed slice>)` — surgical fix targeting the FAIL
4. `shell_exec("cd workspace/deliverables/<project> && npm run build")` — must compile clean
5. `undertow(path=..., expect=<same expect as before>)` — re-verify
6. If PASS → `message_result(text="<delivered after fix>")`
7. If FAIL again on same issue → check that file_edit actually applied the change (re-`file_read`)
8. If FAIL on a NEW issue → repeat from step 1

## Common FAIL patterns

| Undertow FAIL | Fix |
|---|---|
| "X button is missing" / "expected N items, saw M" | `file_edit` to add the missing element |
| "X has no onClick handler" / "input is uncontrolled" | `file_edit` to add the handler / `value={state} onChange={...}` |
| "console error: missing key prop" | `file_edit` the `.map(...)` to add `key={i}` |
| "page hangs / out of memory" | `file_read` for an infinite useEffect (missing dep array) |
| "404 on /asset.png" | `generate_image` the asset, OR `file_edit` to remove the broken ref |

## Gotchas
- **NEVER `message_chat`** between FAIL and the fix tool. The fix tool IS the recovery — chatting doesn't recover.
- **NEVER `message_result`** while the most recent undertow says FAIL. The deliverable gate will refuse it.
- **2 failed fix attempts on the same issue** → re-`file_read` to verify the file actually changed; the model sometimes file_edits a stale view.
- **Cap at 5 fix iterations.** Beyond that, scope creep — `message_chat(done=false)` to the user describing the impasse.
