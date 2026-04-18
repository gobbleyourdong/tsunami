# Qwen-native alignment — progress log

> Track what we're porting from `QwenLM/qwen-code` (canonical qwen3-coder
> agent reference) into tsunami. Each round commits atomically; this doc
> is the running journal so /loop firings pick up where the last left off.

## Reference

- `github.com/QwenLM/qwen-code` — the agent Qwen ships with their training
  distribution. Our conventions should match theirs where it's
  load-bearing (the model was trained against these names / formats /
  sampling settings).

## Plan

- [x] **R1a — Mode-sampling auto-switch** (`tsunami/model.py`)
  - When `enable_thinking=True`, override client defaults to Qwen's
    "Thinking / general tasks" preset (temp=1.0, top_p=0.95,
    presence_penalty=1.5).
  - When `enable_thinking=False`, keep the "Precise coding" defaults
    (temp=0.6, top_p=0.95, presence_penalty=0.0) — these match the
    client's existing values.
  - Respects caller overrides (temp<0.5 or presence_penalty<0.05) —
    deterministic harnesses + unit tests don't get re-randomized.

- [x] **R1b — file_edit param rename** (`tsunami/tools/filesystem.py`)
  - `old_text` / `new_text` → `old_content` / `new_content` (matches
    qwen-code system-prompt example).
  - Backward-compat: execute() accepts both old/new_text and
    old/new_content kwargs, coalesces.

- [x] **R2 — Tool-name aliases** (two layers)
  - Proxy-side normalization in `tsunami/serving/serve_qwen36_fp8.py
    ::_normalize_tool_name` — `_parse_qwen_tool_calls` rewrites
    qwen-code names to tsunami names before the tool_call leaves the
    proxy. Downstream (agent, history, eval) sees tsunami spellings.
  - Registry-side fallback in `tsunami/tools/__init__.py
    ::ToolRegistry.get` — if a non-normalized name still arrives
    (direct call, test harness, future code), the registry resolves
    aliases on lookup. Belt-and-suspenders.
  - Mapping: `read_file→file_read`, `write_file→file_write`,
    `edit→file_edit`, `run_shell_command→shell_exec`,
    `web_search→search_web`, `ask_user_question→message_ask`.
  - Python class names unchanged — no call-site renames, no test
    breakage, no merge friction.

- [x] **R3 — Streaming tool-call repair**
  - Extended truncation recovery in
    `tsunami/serving/serve_qwen36_fp8.py::_parse_qwen_tool_calls`.
  - Old behavior: sealed only the outer `<tool_call>` close and
    opportunistically added single `</parameter>` / `</function>`
    if none were present — missed the case where an earlier param
    closed but the LAST param was truncated mid-value.
  - New behavior: balance-audit style. Count `<parameter=` opens
    vs `</parameter>` closes in the unclosed tail, add the delta
    of closers. Same for `<function=` vs `</function>`. Mirrors
    qwen-code `streamingToolCallParser.ts`'s per-index depth-counter
    pattern in one-shot form (we don't stream the response, so per-
    index buffering isn't needed; just end-of-response balance).
  - Smoke: 4 shapes — missing `</tool_call>`, last-param truncated
    with earlier-param closed, missing `</function>` + outer, clean
    complete emission — all parse correctly.

- [x] **R4 — Orchestration patterns** (study + targeted port)

  Read through (with notes):

  - **`packages/core/src/core/coreToolScheduler.ts`** — Tool-call state
    machine with 7 states: validating → scheduled → waiting → executing
    → {successful | errored | cancelled}. Plus batching via `ToolBatch`.
    Our agent.py is linear (extract → execute → record), which is fine
    for our one-at-a-time tool flow; the state machine is useful for UI
    streaming but overkill for headless eval runs. **Not ported.**

  - **`packages/core/src/core/turn.ts`** — Event stream taxonomy:
    Content, Thought, ToolCallRequest/Response/Confirmation, Retry,
    Cancelled, ChatCompressed, LoopDetected, SessionTokenLimitExceeded,
    Finished, Error. We cover most of these imperatively (Circulation
    = LoopDetected, compress_context = ChatCompressed, model.py retry
    = Retry, task_complete = Finished). Surfacing them as a stream
    is a UI/observability refactor. **Not ported; structure documented
    here for future ref.**

  - **`packages/core/src/utils/retry.ts::defaultShouldRetry`** — Retry
    on `429 OR 5xx`. Our `tsunami/model.py` top-level retry covers
    429/500/502/503/504 already. But the NESTED per-attempt halving
    of max_tokens only fired on 500 and 400 — missed 502/503/504.
    **Ported** — halve on any 5xx, same reasoning (oversized stream
    that will succeed under a smaller response budget).

  - **`packages/core/src/core/client.ts`** — Session/chat management.
    Largely their Gemini/OpenAI adapter layer; our equivalents
    already exist. **Not ported.**

  - **`packages/core/src/agents/runtime/agent-core.ts`** — Outer
    agent loop with cancellation tokens + hook system. Our `_step`
    loop handles the same cases via Circulation + force-undertow +
    deliver-gate but without first-class cancellation. Future
    refactor candidate if we need interruptible long-running agents.
    **Not ported.**

  Net from R4: one practical port (halving max_tokens on all 5xx
  retries) and a documented inventory of what we chose not to port,
  for future reference.

- [ ] **R5 — Rerun T2 pomodoro eval, compare ledger**
  - After R1–R4 land, launch `python3 -m tsunami.tests.eval_tiered
    --tier T2` and capture the token ledger.
  - Compare against the T2 pass from 2026-04-18 (commit 6889c43):
      iters=3, wall=897.5s, tokens=8963, waste=100% (oversize×2 +
      force_miss×1).
  - Expected improvement: lower oversize count (mode-switch helps
    thinking turns emit less filler), fewer force_miss fires
    (model honors deliver-gate more often when it sees its own
    trained tool names).
  - If T2 regresses (iters > 3, or quality_ok=False, or
    delivered=False), revert the last change and bisect.

## Notes

### Non-alignments we're keeping (intentional)

- Ours: `shell_exec` / `shell_view` / `shell_send` / `shell_wait` /
  `shell_kill` — we have session-based shell; qwen-code has
  `run_shell_command` only. Keep the ours-only ones; just alias
  `shell_exec` to also accept `run_shell_command`.
- Ours: `message_chat`, `message_result`, `undertow`, `riptide`,
  `generate_image`, `project_init`, `emit_design`, `plan_update`,
  `plan_advance` — tsunami-only tools that have no qwen-code analog.
  Keep the names.

### Sampling-preset decision

Qwen's model card has four presets:
- Thinking / general:        temp=1.0  top_p=0.95 presence=1.5
- Thinking / precise coding: temp=0.6  top_p=0.95 presence=0.0
- Instruct / general:        temp=0.7  top_p=0.8  presence=1.5
- Instruct / reasoning:      temp=1.0  top_p=1.0  presence=2.0

We pick "thinking / general" for thinking turns (not the coding
variant), because tsunami's planning iters are not pure code-gen —
they include mechanic selection, archetype layout, flow structure.
Coding iters (file_write, file_edit) run with the precise-coding
preset via the client's existing defaults (enable_thinking=False).
