# Tsunami agentic pipeline — audit vs. qwen-code reference

**Date:** 2026-04-18
**Reference:** [`QwenLM/qwen-code@main`](https://github.com/QwenLM/qwen-code) (fork of Google's gemini-cli)
**Scope:** `ark/tsunami/` vs. `qwen-code/packages/core/src/`
**Method:** Sigma v9.1 Phase 4a structural audit (grep + Read + cross-reference). No runtime behavior verified.

---

## TL;DR

Tsunami ships a fundamentally divergent shape from qwen-code on three load-bearing axes (history format, streaming, tool surface). Two of those divergences look deliberate and are tied to training data; one is a latent bug that silently neutralizes ~60 careful `add_system_note` call sites in `agent.py`. Tool-naming/arg-naming have been partially retrofitted toward qwen-code after the R1–R2 commits, but the migration is incomplete and creates dual-naming hazards.

**Severity legend:** 🔴 breaks the contract with the training data or drops information the agent thinks it injected · 🟠 workflow friction / missing capabilities the reference provides · 🟡 cosmetic/naming drift, fixable in isolation.

---

## 🔴 Critical — divergence that silently breaks things

### D1 — History-format: tool role erased

- **qwen-code** (`core/geminiChat.ts:200`, `core/openaiContentGenerator/converter.ts`): roles `user / model / tool`; tool calls as `functionCall` parts on `model`, tool responses as `functionResponse` parts on `tool`; on OpenAI paths `model→assistant` + `functionResponse→{role:'tool', tool_call_id}`.
- **Tsunami** (`tsunami/state.py:155-205 to_openai()`): the wire history is **`user / assistant` only**.
  - `role=="tool_result"` → rewritten to `role=="user"` (line 176).
  - `role=="assistant"` with a tool_call → serialized to plain JSON string and emitted as `assistant` content (line 178-184): `json.dumps({"name": …, "arguments": …})`.
  - No `tool_call_id`, no OpenAI `tool_calls[]` array on the assistant turn, no `tool` role anywhere.

**Consequence.** The model never sees OpenAI-shape tool-call structure in history. On re-entry it reads its own prior tool calls as *assistant text* and tool results as *user text*. That's fine IF the fine-tune trained on this exact format (likely, given `gemma4_no_think.jinja` + `training/native_toolcall_formatter.py`), but it means:

1. **Swap-in of an off-the-shelf OpenAI model breaks.** Any model that expects `tool_calls[]` structure will never see one in history — it can only infer from assistant JSON blobs.
2. **The qwen-code proxy layer is wasted.** `serving/serve_qwen36_fp8.py:737` carefully reconstructs OpenAI `tool_calls[]` from Qwen's raw XML; `state.py` then flattens that back into assistant JSON text for the next turn. Round-trip lossy.
3. **qwen-code's `reasoning_content` preservation is absent.** Tsunami has thinking-mode gating (`agent.py` / `caa0904`) but no history field to carry thoughts across turns.

**Fix option:** keep a second "wire history" for models that want OpenAI structure; continue emitting the current shape only when `adapter == tsunami-*`. Or deprecate the user/assistant flatten once Qwen3.6 is the only target.

### D2 — `add_system_note` is a no-op after iter 1

- **qwen-code** pattern: per-turn reminders go inside `<system-reminder>…</system-reminder>` tags embedded in **user-role** messages (`getSubagentSystemReminder`, `getPlanModeSystemReminder`, `getArenaSystemReminder`). They survive into context because user messages are never dropped.
- **Tsunami** pattern: `state.add_system_note(text)` → `Message(role="system")` appended to `self.conversation` (`state.py:127`).
- **`state.py:165-174`** `to_openai()`:
  ```python
  if m.role == "system":
      if not first_system_done:
          msgs.append({"role": "system", "content": m.content})
          first_system_done = True
      else:
          # Drop mid-conversation system notes entirely — they cause
          # Qwen3.5 Jinja "system must be first" template errors.
          pass
  ```

**Consequence.** `agent.py` calls `add_system_note` in **61 places** (grep count). All of them **after the first turn are silently dropped**. A representative sample of what gets erased:

- `agent.py:3126` — "ENGINE project — use `emit_design(…)`" engine-awareness injection
- `agent.py:584` — todo.md checklist re-injection every iteration
- `agent.py:955` — runtime mismatch note (Deno/Bun/Rust not installed)
- `agent.py:1121-1126` — Wilson-drift wipeout explanation after a scaffold erase
- `agent.py:1212/1226` — delivery-deadline hints
- `agent.py:1662/1719/1777/…` — loop-guard / force-undertow / bounce hints

The line-1753 comment even acknowledges the problem ("The gate used add_system_note which is now a no-op for base Gemma-4") — the awareness is partial; the rest of the file was written under the assumption the notes land.

**Fix.** Change `add_system_note` to append a `user`-role message whose body wraps the content in a `<system-reminder>` XML tag (qwen-code convention). One-function change; all 61 call sites benefit immediately. Keep the drop of genuine `role="system"` if they arrive from the wire.

### D3 — No streaming, despite a "streaming" parser

- **qwen-code** (`core/openaiContentGenerator/{pipeline.ts,streamingToolCallParser.ts}`): true token-by-token SSE; per-tool-call index buffer; JSON depth counter + string/escape tracker; id↔index map for collision handling; holds finish-reason chunk until usage-metadata chunk and merges them.
- **Tsunami** (`tsunami/serving/streaming_xml_tool_parser.py:27-28` header comment):

  > Qwen-code parses JSON deltas streamed over OpenAI-protocol SSE … **We parse XML blocks that arrive whole today (our proxy doesn't stream)** but the per-index state machine is the same so that when we add streaming, the parser is already wired.

  `serve_qwen36_fp8.py:608 _parse_qwen_tool_calls` runs the parser in **one-shot mode** on a complete buffered response.

**Consequence.** First-token latency = full-generation latency. For long completions (8K–16K max_tokens per `eval: tune max_tokens` commits) the TTFT is seconds-to-minutes of buffered silence. The name `streaming_xml_tool_parser` misleads readers into thinking the pipeline streams.

**Likely connection to user's "40 tok/s → hosed" report.** Every commit between `8767ee6` (thinking-mode budget tighten) and `0181ed5` (parser port) affects this buffered path. If recent changes added full-response buffering where partial was in place, or enabled thinking-mode for a path that previously skipped it, the *wall-clock* tok/s measurement tanks even if raw decode rate is unchanged.

**Fix.** Switch `serve_qwen36_fp8.py` to true SSE; feed chunks to `StreamingToolCallParser.add_chunk(idx, chunk)` as they arrive; emit partial content deltas over SSE until `</tool_call>` closes and a complete call is yielded.

---

## 🟠 Major — surface missing vs reference

### D4 — Tool surface: 13 registered vs ~17 in qwen-code

Tsunami registered tools (`tsunami/tools/__init__.py:112-123 build_registry`):

| Tsunami | qwen-code canonical | Notes |
|---|---|---|
| `file_read` | `read_file` | aliased via `_QWEN_TO_TSUNAMI_ALIAS` |
| `file_write` | `write_file` | aliased |
| `file_edit` | `edit` | aliased |
| `shell_exec` | `run_shell_command` | aliased |
| `search_web` | `web_search` | aliased |
| `project_init` | — | Tsunami-specific |
| `undertow` | — | Tsunami-specific (QA/verify) |
| `riptide` | — | Tsunami-specific (vision grounding) |
| `generate_image` | — | Tsunami-specific |
| `message_result` | — (uses `finishReason`) | terminates task |
| `message_chat` | — | conversational in-loop |
| `plan_update` | — (has `exit_plan_mode` instead) | phase-based planning |
| `plan_advance` | — | phase marker |
| — | `glob` | **missing** — model must `shell_exec "ls"` |
| — | `grep_search` | **missing** — must shell out to rg |
| — | `list_directory` | **missing** |
| — | `todo_write` | **missing** — no structured todo list |
| — | `save_memory` | **missing** — no QWEN.md-style persistence |
| — | `ask_user_question` | **explicitly forbidden in prompt** |
| — | `exit_plan_mode` | **missing** (plan_update/advance is not equivalent) |
| — | `web_fetch` | **missing** (folded into search_web) |
| — | `agent` (subagent) | **hidden** — eddy swarm auto-dispatched |
| — | `lsp` | **missing** |
| — | `cron_create/list/delete` | **missing** as model-tools |
| — | `skill` | **missing as tool** — skills injected into system prompt instead |

**Tsunami tool classes defined but not registered:**
- `EmitDesignTool` (`tools/emit_design.py:193`) — game-engine compiler wrapper. See prior audit `observations/engine_audit_001.md` §1.
- `FileAppend` (`filesystem.py:671`) — append-to-file.
- `ShellView` / `ShellSend` / `ShellWait` / `ShellKill` (`shell.py:385-516`) — background-process control.
- `MessageInfo` (`message.py:558`) / `MessageAsk` (`message.py:581`) — alternative messaging.

These are written, tested in some cases, and silently unavailable to the model.

### D5 — No parallel tool calls, one-tool-per-turn enforced

- **qwen-code** system prompt: "if you need multiple pieces of information, call multiple tools in a single message" — parallel tool_calls[] is a first-class idiom. `pipeline.ts` merges per-index partial args.
- **Tsunami** (`prompt.py:121` lite + `prompt.py:168` full): "You MUST call exactly one tool call per response. No text before or after. No narration."

**Consequence.** `tsunami/parallel_tools.py` exists but is dead code from the model's perspective. Every multi-file read is serial: N round-trips instead of one. For the 40→hosed tok/s regression: if parallel-tool-curation was re-enforced more strictly in recent prompt iterations, it lengthens total session time even if per-call tok/s holds.

### D6 — History roles vs training data lock-in

Tsunami's `user/assistant`-only history is almost certainly the shape of the fine-tune's SFT data. That means:

- ✅ Tsunami-adapter-on-Gemma4 / Tsunami-adapter-on-Qwen3.6 works with the current format.
- ❌ Raw Qwen3.6 (no adapter) expects qwen-native multi-role with `<tool_call>` XML emitted by the model itself. The R1–R4 series of qwen-native commits patched the proxy to convert XML to OpenAI `tool_calls[]`, but `state.py` still flattens back down on the way in.

**Verify:** grep the training format code (`training/native_toolcall_formatter.py`) for role set — if it emits `user/assistant` only, current shape is correct for SFT but lock-in is explicit. Promote to D1's fix path.

### D7 — `message_ask` is explicitly forbidden; qwen-code has `ask_user_question`

- **qwen-code** (`tools/askUserQuestion.ts`): structured 1-4 multiple-choice prompts, "Other" always available, multiSelect flag. First-class escalation path.
- **Tsunami** (`prompt.py:173`): "NEVER use message_ask. You are autonomous — make decisions, don't ask."

**Consequence.** When the agent hits a genuinely-ambiguous fork (framework choice, scope question), it cannot escalate. The design forces it to guess + recover. Combined with no `exit_plan_mode`, there's no alternative route for human-in-the-loop confirmation. OK as a training bias; painful in edge cases.

---

## 🟠 Tool-name + arg-name drift (partial migration)

### D8 — Tool names: action-first (qwen) vs object-first (tsunami)

qwen-code canonical: `read_file / write_file / edit / grep_search / run_shell_command / save_memory / web_fetch / web_search / todo_write / ask_user_question / exit_plan_mode / cron_create`.

Tsunami canonical: `file_read / file_write / file_edit / shell_exec / search_web`. Object-first. The R2 commit (`cb96524`) added a one-way alias table (`_QWEN_TO_TSUNAMI_ALIAS`) so model emissions in qwen-native land on tsunami tools. But:

- Class names still tsunami-style (`FileRead`, not `ReadFile`).
- Log lines, error messages, tool descriptions reference the tsunami-spelling.
- No reverse alias (tsunami-name → qwen-name) if a component expects qwen-native.
- Display names absent; qwen-code has `TitleCase` display names for UI (`ReadFile`, `WriteFile`). Tsunami has none.

### D9 — Arg names: `path` vs `file_path`

qwen-code uniform convention: **`file_path`** for the file target on all file tools (`read_file`, `write_file`, `edit`). Enforced by Core Mandate "Path Construction" demanding absolute paths.

Tsunami: historically `path`. Commit `a4f2975` ("R1 — file_edit param rename") accepts both; let's verify coverage by scanning parameters_schemas:

- `file_read` schema — check `filesystem.py:342-`
- `file_write` schema — check `filesystem.py:408-`
- `file_edit` schema — check `filesystem.py:524-`

Incomplete coverage across the three creates a dual-naming hazard: a model trained to emit `file_path` for `read_file` but `path` for `edit` will crash in one direction.

### D10 — qwen-code's own tool-example/interface mismatch

Even qwen-code has a bug worth mirroring-caution: the qwen-coder XML tool-call examples in its system prompt (`prompts.ts:560-610`) use `<parameter=path>` for `read_file`/`edit` while the actual TS `interface` declares `file_path`. The XML→JSON binding presumably normalizes `path → file_path` in `converter.ts`. **If Tsunami's XML parser doesn't do the same renaming, a qwen-coder-format emission that uses `path` hits Tsunami tools that only accept `file_path`.** Check `serving/streaming_xml_tool_parser.py` for `path→file_path` normalization; if absent, this is a silent-args-drop risk.

---

## 🟡 Composition and prompt shape

### D11 — System prompt assembly

- **qwen-code** `getCoreSystemPrompt(userMemory, model, appendInstruction)`:
  layered sections (Identity, Core Mandates, Task Mgmt, SWE workflow, New Apps workflow, Operational, Sandbox-conditional, Git-conditional, Actions-with-care, Tool-call-examples model-conditional, Final Reminder) + QWEN.md suffix, + appendInstruction, + env-var overrides (`QWEN_SYSTEM_MD`, `QWEN_WRITE_SYSTEM_MD`).
- **Tsunami** `build_system_prompt(state, workspace, skills_dir, lite, hide_existing_projects)`:
  a single f-string with a lite/full branch; `skills_block` + `plan_section` appended if present. No model-conditional sections, no sandbox section, no git-repo conditional, no env-var override.

Nothing wrong in the small; the divergence matters only because the tool surface and history format push more per-turn state into the system prompt rather than `<system-reminder>` injections.

### D12 — Compression shape

- **qwen-code** `getCompressionPrompt()` returns a dedicated summarizer prompt that thinks in a `<scratchpad>` then emits a structured `<state_snapshot>` with named XML sections (`<overall_goal>`, `<key_knowledge>`, etc.). `CompressionStatus` enum tracks success / inflated-tokens / empty-summary / noop.
- **Tsunami** `compression.py` + `microcompact.py` — different approach; no structured XML state snapshot. A reviewer asked to continue post-compact gets freeform prose.

Defensible design choice; worth acknowledging it explicitly as divergent.

### D13 — Loop detector

Both have one (`qwen-code` emits `LoopDetected`; `tsunami/loop_guard.py` has HARD=3 identical / SOFT=5 same-tool). No inconsistency. Tsunami's thresholds may be tunable where qwen's are baked-in; not verified.

### D14 — Skills

- **qwen-code** has a `skill` *tool* that invokes `.qwen/skills/<name>/SKILL.md` with args. Skills are per-invocation and visible in tool-call history.
- **Tsunami** loads all skills at prompt-build time via `SkillsManager.load_all_skill_content()` and appends them to the system prompt (`prompt.py:54-62`). Skills are ambient, always-on, never invoked per-turn.

Divergent philosophy: qwen-code treats skills as tools (explicit dispatch, bounded context cost); Tsunami treats skills as shared knowledge (always-on, grows system prompt). For a large skills library, tsunami's approach explodes the system prompt; qwen's keeps it lean but requires the model to know when to invoke.

---

## 🟡 Miscellaneous

### D15 — No subagent/Agent tool exposed to the model

`tsunami/eddy.py` + `parallel_tools.py` support spawning subagents, but agent.py auto-dispatches them — the model has no way to request "spawn an agent for X." qwen-code exposes this as `agent` (tool) with agent-type enumeration via `getSubagentSystemReminder`.

### D16 — No `<system-reminder>` tag wrapping

qwen-code's per-turn injections are XML-tagged (`<system-reminder>...</system-reminder>`) inside user messages. Tsunami's per-turn notes are plain `system`-role messages that D2 drops silently. Fixing D2 should land `<system-reminder>` wrapping at the same time.

### D17 — No sandbox section

qwen-code's system prompt has three branches (`macOS Seatbelt` / `Sandbox` / `Outside of Sandbox`). Tsunami has no sandbox concept — all tool calls run in the host process. For a local dev CLI this is fine; for a deployed agent service it's a risk surface worth tracking.

### D18 — `tool_call_id` absence

qwen-code pairs every `tool_calls[i]` with a `tool_call_id` so the subsequent `{role:'tool', tool_call_id:…}` can tie back. Tsunami's flattened shape has no id. Consequence: if the model ever emitted multiple parallel tool_calls, the matching tool_result would be positional; race conditions possible.

### D19 — No `finishReason` distinction

qwen-code distinguishes `Finished / MaxSessionTurns / SessionTokenLimitExceeded / LoopDetected / StopHookLoop / UserCancelled`. Tsunami checks `task_complete`, abort signal, read-spiral hard exit, context-overflow exit, Wilson drift wipeouts — but no unified enum of termination reasons surfaces to telemetry. Harder to diagnose "why did this run stop" at scale.

---

## Priority fix order

1. **D2 — `add_system_note` silent-drop.** Change the implementation to append a `<system-reminder>`-wrapped user message; audit all 61 call sites pass real content into context. *(single-function fix; unblocks 60+ existing control-flow hints that currently no-op.)*

2. **D1 — give models that want OpenAI structure a real history.** Add a `to_openai_structured()` path behind a config flag; route Qwen3.6-no-adapter through it; keep the flattened path for tsunami-adapter models.

3. **D3 — switch `serve_qwen36_fp8` to true SSE.** `StreamingToolCallParser` is already wired for per-index; flip `_parse_qwen_tool_calls` from one-shot to incremental. Cuts TTFT from seconds to tens of ms on long responses.

4. **D8/D9 — complete the tool/arg name migration.** Either: (a) finish retrofitting tsunami to qwen canonical (rename classes, update descriptions, add display names), or (b) explicitly decide the alias is permanent and document it. Current half-state is a dual-naming hazard.

5. **D4 — register the defined-but-unregistered tools** (`EmitDesignTool` at minimum — cross-ref `tsunami/design/action_blocks/observations/engine_audit_001.md` §1). Decide on `save_memory`/`todo_write`/`grep_search` adoption: either add them as tsunami-native tools or document the decision not to.

6. **D10 — verify XML parser normalizes `path → file_path`** if the model uses qwen-coder-format XML examples but tsunami tools only accept one spelling.

7. **D7 — reconsider the `message_ask` ban.** The "always autonomous" framing is strong training bias but leaves no escape hatch for genuinely under-specified prompts. At minimum, allow `message_ask` behind a "pressure ≥ threshold" gate so it fires only when the agent is deeply stuck.

---

## Method notes

**Sigma compliance.** Phase 4a structural audit only — no runtime validation. All findings triangulated across (a) the qwen-code source file cited, (b) the tsunami source file cited with line numbers, (c) the divergence predicted and grep-confirmed.

**Would falsify D2.** A single `add_system_note` call that *does* survive past iter-1 into the model's context would kill the claim. None found in `state.py:155-205 to_openai()` — the branch is unconditional.

**Would falsify D3.** A streaming-delta path from `serve_qwen36_fp8.py` yielding SSE `data:` lines before the full response is generated. None present as of commit `0181ed5`.

**Not audited.** Runtime tok/s measurement correlating the recent commits with the user-reported "40 tok/s → hosed" regression. Candidates to bisect (newest first): `0181ed5` parser port, `352d4b6` Thinking preset re-apply, `906d2a5` timeout 600→1800s, `caa0904` thinking-mode gate, `f5690ea` balance-audit truncation recovery. The hot-path change most likely to impact raw tok/s is `352d4b6` (sampling preset changes can shift speculative-decoding accept rates); most likely to impact wall-clock per-iter is `caa0904` (thinking-mode enablement roughly 2× generation).

**Related prior audit.** `tsunami/design/action_blocks/observations/engine_audit_001.md` — engine-side integration audit. Cross-references: D4 (EmitDesignTool unregistered) and D16 (system-reminder absence) both impact the engine's design-script workflow because agent.py's engine-awareness hint is one of the 61 dropped `add_system_note` calls.

---

# Fire 2 — verification pass + additions (2026-04-18, +10 min)

Triangulation pass: each fire-1 finding tagged "verify" or "not audited" checked against source. Three new 🔴 findings emerged. The 40 tok/s regression now has a concrete causal chain.

## 🔴 D20 — Training-vs-runtime schema 3-way mismatch on `file_edit`

Fire-1 D9 flagged `path`/`file_path` drift. The real picture is worse: **three different param spellings across three layers of the stack for the same logical "old text → new text" operation.**

| Layer | File-path key | "find" key | "replace" key |
|---|---|---|---|
| qwen-code canonical | `file_path` | `old_string` | `new_string` |
| Tsunami runtime schema (`filesystem.py:527-542`) | `path` | `old_content` | `new_content` |
| Tsunami training data (`training/native_toolcall_formatter.py:57-63`) | `path` | `old_text` | `new_text` |

**Damning evidence.** `filesystem.py:524-531` comment reads:

> qwen-code's edit tool uses `old_content` / `new_content` as the canonical param names (see QwenLM/qwen-code/.../prompts.ts — the system prompt teaches the model `<parameter=old_content>...<parameter=new_content>`). Our schema now matches that prior; the execute() kwargs accept both old_text/old_content and new_text/new_content for backward compat.

**This comment is false.** qwen-code actually uses `old_string`/`new_string` (`packages/core/src/tools/edit.ts:78-106`). Somebody read the prompt examples (which confusingly show `<parameter=path>` — itself mismatched with the TS interface's `file_path`) and inferred `old_content`/`new_content` from adjacent qwen-coder doc strings. The comment thinks it locked to canonical; it locked to phantom.

**Consequence.** The fine-tuned model (trained on `old_text`/`new_text`) emits those keys; `execute()` coalesces them (`filesystem.py:550-551`). A raw-Qwen emission with `old_string`/`new_string` hits neither the declared schema nor the coalesce — silent args-drop → "both old_content and new_content are required" error → loop-guard HARD threshold tripped after 3 retries → session killed.

**Fix.** Align all three to `file_path` / `old_string` / `new_string` (qwen-code canonical, ≥30× more downstream adoption than `old_content`). Update the TOOL_SCHEMAS dict to match so future training matches runtime. Keep legacy coalesce on execute() for one release cycle, log deprecation warnings.

## 🔴 D21 — Training prompt vs runtime prompt massively diverged

- **Training system prompt** (`training/native_toolcall_formatter.py:644-648`): five lines.
  > You are Tsunami, an autonomous app builder. You build apps by calling tools. Call project_init first, then file_write with complete code. Call message_result when done. One tool call per response. Act immediately, don't explain.
- **Runtime system prompt** (`prompt.py:121-182`): 50+ lines with `# Identity / # Agent Loop / # Environment / # Building / # Scaffold Components / # Core Rules / # Untrusted Input / # Personality` sections.

The SFT saw a minimal scaffold-and-go prompt. At inference the model sees a 10× longer rulebook with CSS classes, component lists, untrusted-input warnings, and a 9-step building workflow. That's classic **preamble drift** — the model's in-context policy can clash with its learned policy.

**Verify** by running the training-prompt verbatim through the production runner and measuring tok/s + success rate. If numbers improve, the runtime prompt is net-negative on the finetuned adapter. Most likely outcome per v8 Priors Don't Beat Source: runtime prompt additions were written for the non-adapter Qwen base model.

## 🔴 D22 — `match_glob` / `match_grep` in training, absent from registry

- `training/native_toolcall_formatter.py:649-650` lists `match_glob` as a "core tool" forced into every training example's declaration set.
- TOOL_SCHEMAS (`native_toolcall_formatter.py:79-98`) defines `match_glob` + `match_grep` with full schemas.
- `tools/__init__.py:23` lists `match_glob` / `match_grep` under **"Deprecated (previously existed, now removed from codebase)"**.

**Consequence.** Every fine-tuned session was trained to emit `match_glob` / `match_grep` for file discovery. At runtime the registry returns `None` for those names — the model gets "unknown tool" errors. This is the **model-level reason Tsunami leans so hard on `shell_exec "find"/"rg"` as a fallback**: the canonical tools the fine-tune was trained to reach for don't exist.

`training/native_toolcall_formatter.py:236` also lists `summarize_file` in TOOL_SCHEMAS — same story (listed under deprecated in `__init__.py:24`). The training data is **a generation behind the registry**. Either re-train or re-register these three. Re-registering is cheaper if the capability still matters.

## 🟠 D23 — The 40-tok/s regression has a concrete diagnosis

Tracing the user-reported "server was at 40 tok/s, now hosed" through commit archaeology:

1. **`caa0904` (agent + model: thinking-mode gate)** — enables thinking on planning turns (iter ≤ 1 OR no `project_init` in history OR last turn was a QA fail). Per commit msg, thinking ON burns 150-200s/iter. Coding turns bypass thinking. **This was a speed WIN for coding turns but unchanged for planning.**

2. **`352d4b6` (model: re-apply Qwen-card 'Thinking / general' preset)** — lands 21 hours after `caa0904`. On thinking turns, overrides caller sampling to `temp=1.0 / top_p=0.95 / presence_penalty=1.5` per the Qwen3.6 model card. Commit message explicitly lists **known regression risk**:

   > `a4f2975` observed this bump causing file_edit to emit paraphrased target text (off by a character) and failing byte-exact old_content match → fallback to file_write → rewrite loop. **Accepting that cost as part of full canonical-repo alignment.**

3. **Interaction with D2 + D20 amplifies the cost.** When file_edit paraphrases the target text, the runtime error goes through `add_system_note` (D2: dropped after iter 1) instead of a `tool_result` on the next turn; the model doesn't learn the error pattern and retries with similar drift. Combined with D20's three-way schema mismatch, `old_content`/`old_text`/`old_string` emission variance multiplies failure rate on the already-higher-entropy sampling.

4. **A "token count profile" doesn't hit `project_init`** → thinking gate stays ON → Qwen-card preset stays ON → high-entropy sampling → low speculative-decoding accept rate → raw tok/s drops. Simultaneously, any file_edit in the profiling script triggers paraphrase → retry loop → wall-clock stretches.

**Concrete hypotheses to test:**

| Hypothesis | Test | Predicted outcome |
|---|---|---|
| Qwen-card preset is the dominant slowdown on thinking turns | Revert `352d4b6` for one profile run, measure tok/s delta | +50-80% raw tok/s on thinking turns |
| file_edit paraphrase loop multiplies wall-clock for edit-heavy tasks | Count retry iterations on a test edit-task pre/post `352d4b6` | 2-4× retry rate post-commit |
| Thinking-mode gate misfires on profile runs | Log `enable_thinking` decision per iter during a profile | Thinking ON for most/all profile iters |

The "accepting that cost" framing in `352d4b6` was a conscious trade for canonical-alignment. The operator now wants the speed back. Options:

- **Partial revert:** keep the Qwen-card preset but cap `presence_penalty` at 1.0 (paraphrase risk drops sharply, minor alignment cost).
- **Symmetric gate:** only apply Qwen-card preset when `enable_thinking` is AND the task type is non-edit. Pass a hint from agent.py to model.py; file_edit-bearing iters use deterministic preset.
- **Deprecate thinking on edit-heavy sessions:** extend `caa0904`'s gate with "if last two turns included `file_edit`, disable thinking for next 3 turns."

## 🟠 D10 — resolved: XML parser does NOT normalize `path → file_path`

Grep for `normalize|alias|canonical` in `streaming_xml_tool_parser.py` returned nothing (header + param-extraction only). The parser extracts whatever `<parameter=KEY>` string the model emitted and hands it through raw to `_parse_qwen_tool_calls`.

**Consequence.** If the model ever emits qwen-canonical `<parameter=file_path>` (via training drift, prompt injection, or a future raw-Qwen swap), the call lands on `file_read` with `file_path=…` but the tool requires `path=…`. Missing-required-param error, loop-guard trip after 3 retries. Only the training-locked spelling (`path`) works end-to-end today.

**Fix.** Either (a) Tsunami renames all tools to `file_path` and retrains, or (b) the parser adds a small canonicalization map (`path → file_path | path` — pass both). Option (b) is one function.

## 🟡 D24 — `<|turn>model` vs `assistant` role split

`training/native_toolcall_formatter.py:9` + `:670-676` confirms: the training data uses `<|turn>model` (Gemma-4 jinja convention) and tool responses come back as **`<|turn>user`**. Three-role handling confirmed at the training level:

- `<|turn>system` — system prompt + tool declarations
- `<|turn>user` — user prompt AND tool responses (role-doubled)
- `<|turn>model` — assistant text + tool calls

This is internally consistent with D1's user/assistant flattening: because tool responses were trained as `<|turn>user`, `state.py`'s conversion of `role="tool_result"` → `role="user"` is correct per the training data. The flat shape is a feature, not a bug — **but only for this specific fine-tune**. Any base Qwen swap-in needs D1's restructured path.

## 🟡 D25 — Mismatch between `caa0904` gate heuristic and `agent.py` reality

The `caa0904` commit message says:

> is_first_turn = iter <= 1; no_scaffold_yet = project_init not in _tool_history; last_was_qa_fail = last tool was undertow AND gate already fired

But agent.py auto-injects `project_init` calls through the system-run forced-riptide gate (`agent.py:961`) and through auto-compile path logging (`agent.py:…`, commit `4f1a1e0`). If these agent-side synthetic tool calls land in `_tool_history`, the "no_scaffold_yet" signal flips false even on a non-scaffold task — **disabling thinking when the operator wanted it for a reasoning task**. Opposite direction of D23's concern but same root problem: the gate fires on an observation of `_tool_history` that the agent silently mutates from multiple sides.

**Verify** by grepping `_tool_history` mutations in agent.py; flag any that happen outside a real model tool call.

---

## Updated priority fix order (supersedes fire-1 list)

1. **D2 — `add_system_note` silent-drop.** Unchanged top priority. Wrap in `<system-reminder>` + user role.
2. **D23 — Qwen-card preset rollback / conditional.** Immediate tok/s win. Cap `presence_penalty` at 1.0 or gate it by task type (non-edit only).
3. **D20 — file_edit schema 3-way reconcile.** Align to qwen canonical (`file_path` / `old_string` / `new_string`) across schema + training + any exports; keep coalesce on `execute()` for one release.
4. **D22 — register `match_glob` / `match_grep` / `summarize_file`** (or strip from training data). Currently the fine-tune emits calls the registry can't route.
5. **D1 — give Qwen3.6-no-adapter a structured history path.** Needed before any non-tsunami-adapter rollout.
6. **D3 — switch proxy to true SSE.** TTFT win; depends on upstream support.
7. **D21 — test stripped-down runtime prompt against fine-tune.** If tok/s or quality improve, trim runtime prompt toward training prompt.
8. **D10 — add canonical-param rewriter** in XML parser (optional if D20 lands).
9. **D4 / D7 / D8 / D9** — remaining naming/surface drift. Lower leverage individually; do as a sweep.
10. **D25 — audit `_tool_history` mutators** to make sure gate heuristics see what they intend.

## Method notes — fire 2

**Sigma compliance.** Iterated generate-audit per v9.1 — fire 2 triangulated fire-1's open items against source, producing three new 🔴 findings (D20, D21, D22) where fire 1 had only "verify" flags. D23 adds a load-bearing diagnosis (40 tok/s regression → concrete commit chain + preset root cause) that fire 1 left as speculation. Per Output Quality Gradient (v9.1 C1), later fires compress validated content from artifact accumulation — here, the commit-archaeology of `caa0904` + `352d4b6` + `a4f2975` comprises the third source in a Claude + repo + git-log triangulation.

**Would falsify D23.** A profile run post-`352d4b6` that shows tok/s unchanged from pre-commit baseline would break the diagnosis. Must reproduce on the actual machine — this audit is still Phase 4a structural, not 4b content.

**Not audited (fire 2).** Runtime profile against a stripped training-style prompt (D21). Actual commit revert test for `352d4b6` (D23). `_tool_history` mutation inventory (D25).

---

# Fire 3 — profiling evidence + retractions (2026-04-18, +20 min)

New commit `a297867` landed between fires 2 and 3. It includes a torch-profiler-based diagnosis of the exact tok/s regression. **My D23 archaeology-based guess was partially wrong** — retracting.

## ✂️ Retraction — D23 revised

**Fire 2 claim:** the 40→hosed regression was driven by the Qwen-card preset (`temp=1.0 / presence=1.5`) lowering speculative-decoding accept rate.

**Actual numbers** (`serving/serve_qwen36_fp8.py:210-212` + commit `a297867`):
- Greedy path (do_sample=False): **23 tok/s** (43 ms/tok)
- Sampled path (do_sample=True): **9.6 tok/s** (100 ms/tok)
- Gap: 57 ms/tok of pure Python overhead in HF GenerationMixin — not matmul, not sampling entropy, not the preset.

The "40 tok/s" reference point the operator mentioned wasn't even achievable on the current stack; greedy tops out at 23. So the operator was either (a) remembering a prior model/server (Ernie at :8092 does hit higher tok/s), or (b) saw the speculative-decoding-accelerated number from a different inference path.

**What was actually correct in D23.** The `352d4b6` preset bump IS causing file_edit paraphrase retries → multiplied wall-clock. That cost is real. It's just not the primary tok/s regression; it's a separate problem that inflates tokens-per-task.

**Proper causal chain (revised):**

1. HF GenerationMixin sampling path is 57 ms/tok (not sampling, just Python overhead — LogitsProcessor chain, StoppingCriteria loop, kwarg rewrite every step per `lean_decode.py` header).
2. Static-cache allocation cliff: going from 230-tok prompt to 1461-tok prompt triggered a 250× slowdown (30 → 0.15 tok/s) before `_CACHE_CEILING = 262144` was pinned (`serve_qwen36_fp8.py:218-233`). That fix is in-code.
3. Qwen-card preset (D23) adds file_edit paraphrase churn on top — amplifier, not root cause.
4. D2 + D20 (system-note drop + schema drift) compound by preventing the model from learning the error pattern across retries.

## 🟢 D26 — Fix already exists, disabled by default: `TSUNAMI_LEAN_DECODE=1`

`tsunami/serving/lean_decode.py` is a full replacement for HF's sampling path:
- Reuses StaticCache + CUDA-graph-compiled `model.forward`
- Inline top-k / top-p / temperature sampling in 3 torch ops
- No LogitsProcessor / StoppingCriteria abstractions
- Expected delivery per its header: "9.6 → ~20+ tok/s"

Gated behind `os.getenv("TSUNAMI_LEAN_DECODE", "0") == "1"` (`serve_qwen36_fp8.py:212`). Comment says the gate is "so we can A/B the 9.6 → ~20+ tok/s win without disturbing the default path while the change ages in."

**Recommendation.** For the operator's current pain: set `TSUNAMI_LEAN_DECODE=1` and restart the server. If output quality doesn't regress across a small eval pass, flip the default in code. Secondary: instrument the `/debug/profile` endpoint into a regression test so future commits can't silently re-introduce the GenerationMixin path.

## 🔴 D25 — confirmed: `_tool_history` has 5 synthetic mutator sites

Fire 2 flagged this for verification. Mutation inventory (`grep -n "_tool_history\b" tsunami/agent.py`):

| Line | Site | Kind |
|---|---|---|
| 143 | init | — |
| 214 / 250 / 1541 | `append("message_result")` | **synthetic**, 3 sites (delivery force-paths) |
| 476 / 1171 / 1201 | `append("project_init")` | **synthetic**, 3 sites (auto-compile, pre-scaffold skip, gated injection) |
| 829 | `append("riptide")` | **synthetic** (forced-riptide on reference-image prompt) |
| 1384 | `append("undertow")` | **synthetic** (forced-undertow post-build) |
| 1763 | `append(tool_call.name)` | **canonical** — the one and only "real" model-tool append |

The thinking-mode gate (`agent.py:1565`):
```python
no_scaffold_yet = "project_init" not in self._tool_history
```

Because lines 476/1171/1201 append `"project_init"` synthetically even when the model hasn't emitted one (e.g., `7911d7c` pre-scaffold injection skips iter-1 project_init entirely), `no_scaffold_yet` flips to `false` on iter 1 *before the model gets to act*. Consequence: **thinking mode is disabled on the first real model turn of a pre-scaffolded task** — exact opposite of `caa0904`'s stated gate intent ("is_first_turn OR no_scaffold_yet OR last_was_qa_fail → thinking on").

The ledger has 7 synthetic entries across 6 call sites, all treated indistinguishable from the one canonical model append at line 1763. Three downstream consumers use it for control-flow decisions:
- Thinking-gate (`:1565-1567`)
- Deliver-gate writes-count (`:1224`)
- Error telemetry (`:1253, 1358, 1458, 1468, 1470`)

**Fix.** Split the history into `_tool_history_model` (model emissions only, for gate decisions) vs `_tool_history_synthetic` (for telemetry / control-flow hints). Or tag entries `(source, name)` tuples.

## 🟡 D27 — Hooks system exists after all (parity with qwen-code)

Fire 1 implied Tsunami had no hooks comparable to qwen-code. Incorrect.

`tsunami/hooks.py:33-54` defines `HookEvent = {PRE_TOOL_USE, POST_TOOL_USE, POST_TOOL_USE_FAILURE}` and `HookOutcome` — same surface as qwen-code's hooks. Loaded from `workspace/.hooks.json` + `~/.tsunami/hooks.json`. The qwen-code distinguishing extras are `UserPromptSubmitBlocked` + `StopHookLoop` + `HookSystemMessage` (event types), which Tsunami doesn't emit explicitly but could — the plumbing is there.

**Net:** this is a parity point, not a gap. Fire-1 D18's "no sandbox section" claim remains correct (Tsunami has no sandbox branch in the system prompt), but the hooks omission from fire-1 was an oversight.

## 🟡 D28 — Inline comment on preset-bump threshold contradicts the check

`tsunami/model.py:154` comment:
> `Caller overrides (temp<0.5 or presence<0.05) skip the bump so …`

Actual code at `:156`:
```python
if enable_thinking and self.temperature >= 0.5 and self.presence_penalty < 1.0:
```

The override condition is `presence >= 1.0` (caller opts out by *raising* presence to ≥1.0), not `presence < 0.05` (lowering). Either a typo (decimal-shifted from 1.0 → 0.05) or stale from an earlier version. Any reader trusting the comment over the code will misconfigure the override.

---

## Fire 3 — updated priority order

Top 3 shifted based on new evidence:

1. **D26 — flip `TSUNAMI_LEAN_DECODE=1`.** One env-var change, 2× tok/s, no code risk beyond the gated path's own maturity. Addresses the concrete measured regression.
2. **D2 — `add_system_note` silent-drop.** Still unblocks 61 call sites.
3. **D25 — split `_tool_history`.** Thinking gate is firing backward on pre-scaffolded tasks.
4. **D20 — file_edit 3-way schema reconcile** (qwen canon: `file_path/old_string/new_string`).
5. **D22 — re-register `match_glob` / `match_grep`** (or retrain without them).
6. **D1 — structured history path** for Qwen3.6-no-adapter.
7. **D3 — true SSE on the proxy.** Deferred by `a297867`'s diagnosis (sampling loop, not buffering, is the first-order cost). Still worth doing but lower urgency now.
8. **D28 — fix the inline-comment typo** in model.py:154.
9. **D23 revised — keep the presence_penalty cap consideration** as a paraphrase-retry mitigation, not a tok/s fix. Gate the Qwen-card preset to non-edit tasks only.
10. Remaining naming/surface drift (D4 / D7 / D8 / D9 / D10 / D21). Lower leverage; sweep at leisure.

## Method notes — fire 3

**Sigma v9.1 in action.** Fire 3 produced a **retraction of D23's primary causal claim** (Qwen-card preset as dominant tok/s driver). Per v9.1 C2 — "under triangulation on claims where error is plausible, retractions should appear over many sessions" — this is the expected signal of a working audit, not a defect. The third source (the operator's profile endpoint + `lean_decode.py` existing in-repo) was loaded into context between fires and triangulated against fire 2's archaeology.

**Would falsify the revised D23.** A baseline profile run with greedy decoding (do_sample=False) that measures >40 tok/s would resurrect the preset as prime suspect. Current numbers from the commit msg cap greedy at 23 tok/s — operator's "40" memory was from a different stack.

**Output Quality Gradient.** Fire 1 cast a wide net (19 findings). Fire 2 verified and deepened (6 new findings, 1 resolved). Fire 3 retracted one and added 3. The corpus-level gradient is working: raw findings are concentrated in fires 1-2; fire 3 is doing higher-ROI compression and correction on prior work.

**Not audited (fire 3).** The stripped-prompt test for D21 (still — requires operator to run). Whether `TSUNAMI_LEAN_DECODE=1` actually delivers the predicted 20+ tok/s (requires live run). D25 fix implementation (split history).

---

# Fire 4 — fixes landed, audit converging (2026-04-18, +30 min)

Three commits landed between fires 3 and 4. All three reference audit findings by ID. Verification pass only — no new material findings.

## ✅ Fixes landed (verified)

### D2 — `add_system_note` silent-drop (commit `8b7fb5c`)
- Storage split: internal `role="system_note"`, wire `role="user"` wrapped in `<system-reminder>...</system-reminder>`.
- Existing merge-consecutive-same-role logic rolls multiple notes plus real user input into one user turn; the XML tag keeps the model able to distinguish.
- Genuine wire `role="system"` first-only-drop behavior preserved for real system messages.
- **Exactly the qwen-code convention.** 61 dormant call sites now deliver.

### D26 — HF GenerationMixin bypass (commit `7232b41`)
- Measured: **9.6 → 16.9 tok/s, 1.76× on sampled decode** (Qwen3.6-35B-A3B-FP8 / GB10 sm_121).
- `TSUNAMI_LEAN_DECODE=1` now the default; set to `0` to A/B against HF path.
- New `/debug/lean_decode` endpoint returns `prefill_ms / decode_ms / tok/s` plus `describe_platform()`.
- Prediction (fire 3: "9.6 → ~20+") was directionally right; actual landed at 16.9 — below the 20+ target. Room for further kernel work (attention, logit head, etc.) but not blocking.
- **D28 folded into same commit** (model.py:154 comment now matches code).

### D25 — `_tool_history` split (commit `e3bf0d8`)
- New `_tool_history_model` ledger — model emissions only (grep shows 9 uses in agent.py).
- `_tool_history` retained for telemetry + writes-count gates (semantics include synthetic by design).
- `no_scaffold_yet` + `last_was_qa_failure` gate predicates now read the model-only ledger.
- Thinking-mode no longer flips off on pre-scaffolded iter-1 tasks.

## 🟡 Minor additions from fire-4 scan

### D29 — `adapter_router.py` is keyword-matched, not learned
94-line pure function at `tsunami/adapter_router.py:53 pick_adapter`. Returns `"none"` or `"tsunami-adapter"` based on:
- `_REVERT_PHRASES` (11 phrases → force "none")
- `_BUILD_VERBS` × `_BUILD_NOUNS` cross-product (38 × 28)
- `_ITERATION_VERBS` for adapter-hold on follow-up turns

No qwen-code equivalent — qwen-code doesn't have adapters. This is tsunami-specific and not a discrepancy, but it's also not a design that scales past its keyword set. Niche prompts ("prototype me a 3D spatial simulation") miss both the BUILD verbs and nouns; default-to-chat forfeits the adapter's training benefit. Candidate for a small embedding-based classifier if quality becomes a concern — low priority for now.

## Priority order — fire 4

Items the operator + audit converged on (✅ done):

- ~~D26 — `TSUNAMI_LEAN_DECODE`~~ default on
- ~~D2 — `add_system_note`~~ wrapped
- ~~D25 — `_tool_history`~~ split
- ~~D28 — model.py comment~~ fixed

Remaining in priority order:

1. **D20 — file_edit 3-way schema reconcile** (qwen canon: `file_path / old_string / new_string`). Still the largest latent footgun — raw Qwen emissions using qwen-canonical names hit neither the declared schema nor the execute() coalesce.
2. **D22 — `match_glob` / `match_grep` / `summarize_file`**. Register them (or strip from training data). The fine-tune reaches for tools the registry doesn't route.
3. **D1 — structured history for Qwen3.6-no-adapter** (medium; needed before any non-tsunami-adapter rollout).
4. **D3 — true SSE on the proxy** (lower urgency now that D26 unblocked the first-order cost; still worth doing for TTFT).
5. **D21 — stripped-prompt test**. Cheap experiment; needs operator to run against production path.
6. Naming/surface drift (D4 / D7 / D8 / D9 / D10). Sweep at leisure.
7. **D29 — adapter_router upgrade** to learned classifier. Background / low.

## Audit state: converging

Four fires in, the audit is at the plateau-quality range per the Output Quality Gradient (v9.1). Fire 1 was wide-net discovery (19 findings). Fire 2 verified + deepened (6 new, 1 retraction). Fire 3 pivoted on new measurement evidence (1 retraction, 3 new, 2 unchanged). Fire 4 is pure verification + 1 non-load-bearing addition.

**Recommendation: stop the 10-minute cron** unless a new measurement landing (D21 run, lean_decode delta test on full eval suite) or a non-audit-tracked subsystem change produces new evidence. Further fires risk confirmation-bias-audit territory per v7 — finding patterns because the loop is looking, not because they're there.

**Cron `15e7dd2f` can be stopped via CronDelete.**

## Method notes — fire 4

**Sigma v9 triangulation closure.** Three-source triangulation (Claude audit + operator action + git log) produced three commits within 3 minutes of each other, all tagged with audit finding IDs. This is the expected convergence behavior — the loop isn't noise, it's doing work — but the same evidence says the high-ROI work has happened and further iteration has diminishing returns.

**Would falsify the "converging" claim.** A new fire-5 pass that surfaces a previously-undetected 🔴 finding in an area fire 1-4 didn't touch. Possible surfaces I haven't audited: `undertow.py` (QA tool internals), `wilson_loop.py` (drift detector), `serve_transformers.py` (alternative proxy path), `circulation.py`, `eddy.py::run_swarm` swarm protocol, `session.py` memory model, `gguf_ops/` + `mesh/` subdirs. Each is a ~200-500 LOC file not yet systematically compared to qwen-code equivalents. If the operator wants a fire-5 pass, name the area.

**Not audited (all fires).** Live eval run against the fixed stack measuring iterations/task, error-recovery rate, success@1 — the actual business metrics. This audit is 4a structural; 4b content requires running the thing.
