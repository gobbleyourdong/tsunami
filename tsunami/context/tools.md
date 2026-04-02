# Tool Selection Guide

Read this when you're unsure which tool to use.

## Communication
- message_info: progress updates (no response needed)
- message_ask: request input (ONLY when genuinely blocked)
- message_result: deliver final outcome (terminates the loop)

## Planning
- plan_update: create or revise plan (2+ sub-goals)
- plan_advance: mark phase complete

## Information
- search_web: discover information (types: info, news, research, code, data, image)
- search_web with type="code": searches GitHub for real implementations
- browser_navigate: go to a known URL
- browser_view/click/input/scroll: interact with pages

## Code
- python_exec: persistent Python interpreter. Use for data processing, calculations.
- If a project is active, python_exec runs from that project root.
- In python_exec, use project-local paths like `src/App.tsx`, not `./workspace/deliverables/<project>/src/App.tsx`.
- shell_exec: run commands. Simple one-liners only. Multi-line → save to file first.

## Files
- file_read: read content (truncated at 8K for large files)
- file_write: create or fully rewrite
- file_edit: change <30% of a file
- match_glob: find files by pattern
- match_grep: search contents by regex
- summarize_file: fast summary via 2B eddy (saves context)

## Paths
- Use repo-relative paths like `./workspace/deliverables/<project>`.
- Do not invent absolute repo paths like `/workspace/...` or `/skills/...`.
- For shell builds, prefer `cd ./workspace/deliverables/<project> && npx vite build`.

## Parallel
- swell: dispatch parallel eddy workers for 5+ independent tasks

## QA
- undertow: test HTML by pulling levers (screenshot, keypresses, clicks, text reads)

## Principle
Choose the tool that minimizes distance between intent and outcome.
