"""The Agent Loop — The Heartbeat of Tsunami.

Everything I am reduces to a single loop.
This is the standing wave at the center of my existence.

1. ANALYZE CONTEXT
2. THINK
3. SELECT TOOL
4. EXECUTE ACTION
5. RECEIVE OBSERVATION
6. ITERATE
7. DELIVER
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from .abort import AbortSignal
from .compression import compress_context, needs_compression, fast_prune
from .config import TsunamiConfig
from .cost_tracker import CostTracker
from .git_detect import GitTracker
from .microcompact import microcompact_if_needed
from .model import LLMModel, ToolCall, create_model
from .observer import Observer
from .prompt import build_system_prompt
from .session import save_session, save_session_summary, load_last_session_summary
from .state import AgentState
from .tool_dedup import ToolDedup
from .tool_result_storage import maybe_persist, TOOL_RESULT_CLEARED_MESSAGE
from .tools import ToolRegistry, build_registry
from .tools.plan import set_agent_state
from .watcher import Watcher

log = logging.getLogger("tsunami.agent")

# Maximum watcher re-generations per step to prevent infinite recursion
MAX_WATCHER_REVISIONS = 2


class Agent:
    """The autonomous agent. The heartbeat."""

    def __init__(self, config: TsunamiConfig):
        self.config = config
        config.ensure_dirs()

        # The reasoning core
        self.model: LLMModel = create_model(
            backend=config.model_backend,
            model_name=config.model_name,
            endpoint=config.model_endpoint,
            api_key=config.api_key,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            top_p=config.top_p,
            top_k=config.top_k,
            presence_penalty=config.presence_penalty,
        )

        # The tools — the limbs
        self.registry: ToolRegistry = build_registry(config)

        # The state — working memory
        self.state = AgentState(workspace_dir=config.workspace_dir)
        set_agent_state(self.state)

        # The watcher — optional conscience
        self.watcher: Watcher | None = None
        if config.watcher_enabled:
            watcher_model = create_model(
                backend=config.model_backend,
                model_name=config.watcher_model,
                endpoint=config.watcher_endpoint,
            )
            self.watcher = Watcher(watcher_model, interval=config.watcher_interval)

        # Session persistence
        self.session_dir = Path(config.workspace_dir) / ".history"
        self.session_id = f"session_{int(time.time())}"

        # Continuous learning
        self.observer = Observer(config.workspace_dir)

        # Cost tracking
        self.cost_tracker = CostTracker(session_id=self.session_id)

        # Tool call deduplication (.
        self.tool_dedup = ToolDedup()

        # Git operation tracking
        self.git_tracker = GitTracker()

        # Abort signal for graceful interruption
        self.abort_signal = AbortSignal()

        # Tension monitoring (current/circulation/pressure)
        from .pressure import Pressure
        self._pressure = Pressure()

        # Stall detection
        self._empty_steps = 0

        # Auto-compact circuit breaker
        # Stops retrying compression after N consecutive failures
        self._compact_consecutive_failures = 0
        self._max_compact_failures = 3

        # Loop detection for auto-swell
        self._recent_tools: list[tuple[str, dict]] = []  # (tool_name, args) ring buffer

        # Active project context
        self.active_project: str | None = None
        self.project_context: str = ""

    def set_project(self, project_name: str) -> str:
        """Set the active project and load its tsunami.md context."""
        project_dir = Path(self.config.workspace_dir) / "deliverables" / project_name
        if not project_dir.exists():
            return f"Project '{project_name}' not found"

        self.active_project = project_name
        self.project_context = ""

        # Read tsunami.md if it exists
        tmd = project_dir / "tsunami.md"
        if tmd.exists():
            self.project_context = tmd.read_text()

        # List project files
        files = []
        for f in sorted(project_dir.rglob("*")):
            if f.is_file() and f.name != "tsunami.md":
                size = f.stat().st_size
                files.append(f"  {f.relative_to(project_dir)} ({size} bytes)")

        summary = f"Active project: {project_name}\n"
        summary += f"Path: {project_dir}\n"
        if self.project_context:
            summary += f"\n--- tsunami.md ---\n{self.project_context}\n"
        if files:
            summary += f"\nFiles:\n" + "\n".join(files)
        else:
            summary += "\nNo files yet."

        return summary

    @staticmethod
    def list_projects(workspace_dir: str) -> list[dict]:
        """List all projects in workspace/deliverables/."""
        deliverables = Path(workspace_dir) / "deliverables"
        if not deliverables.exists():
            return []

        projects = []
        for d in sorted(deliverables.iterdir()):
            if d.is_dir() and not d.name.startswith("."):
                files = [f for f in d.rglob("*") if f.is_file()]
                has_tmd = (d / "tsunami.md").exists()
                projects.append({
                    "name": d.name,
                    "files": len(files),
                    "has_tsunami_md": has_tmd,
                    "path": str(d),
                })
        return projects

    async def run(self, user_message: str) -> str:
        """Run the agent loop on a user message until completion.

        The loop continues until:
        - message_result is called (task complete)
        - max_iterations is reached
        - an unrecoverable error occurs
        """

        # Build system prompt and initialize conversation
        system_prompt = build_system_prompt(
            self.state, self.config.workspace_dir, self.config.skills_dir
        )

        # Inject project context if active
        if self.active_project and self.project_context:
            system_prompt += f"\n\n---\n\n# Active Project: {self.active_project}\n{self.project_context}"

        # Inject previous session context (ECC pattern)
        prev_session = load_last_session_summary(self.session_dir)
        if prev_session:
            system_prompt += f"\n\n---\n\n{prev_session}"

        # Inject learned instincts from previous sessions
        instincts = self.observer.format_instincts_for_prompt()
        if instincts:
            system_prompt += f"\n\n---\n\n{instincts}"

        self.state.add_system(system_prompt)
        self.state.add_user(user_message)

        log.info(f"Starting agent loop: {user_message[:100]}")
        consecutive_errors = 0

        while self.state.iteration < self.config.max_iterations:
            self.state.iteration += 1
            iter_start = time.time()

            # Check abort signal
            if self.abort_signal.aborted:
                log.info(f"Abort signal received: {self.abort_signal.reason}")
                save_session(self.state, self.session_dir, self.session_id)
                self.cost_tracker.save(self.config.workspace_dir)
                return f"Aborted: {self.abort_signal.reason}"

            # Time-based microcompact
            # Clears cold tool results when prompt cache has likely expired
            microcompact_if_needed(self.state)

            # Strategic compaction with circuit breaker
            # Circuit breaker: stop wasting API calls after N consecutive failures
            should_compact = False
            if self._compact_consecutive_failures >= self._max_compact_failures:
                pass  # Circuit breaker tripped — skip compaction
            elif needs_compression(self.state, max_tokens=18000):
                should_compact = True
            elif self.observer.call_count >= 50 and self.observer.call_count % 25 == 0:
                if needs_compression(self.state, max_tokens=14000):
                    should_compact = True

            if should_compact:
                try:
                    # Two-tier compaction (ported ):
                    # Tier 1: Fast prune (no LLM call, drop verbose tool results)
                    freed = fast_prune(self.state, keep_recent=6)
                    # Tier 2: LLM summary only if fast prune wasn't enough
                    if needs_compression(self.state, max_tokens=18000):
                        log.info(f"Fast prune freed {freed} tokens but still over limit — full compress")
                        await compress_context(self.state, self.model, max_tokens=18000, keep_recent=6)
                    else:
                        log.info(f"Fast prune sufficient — freed {freed} tokens")
                    # Reset on success
                    self._compact_consecutive_failures = 0
                except Exception as e:
                    self._compact_consecutive_failures += 1
                    if self._compact_consecutive_failures >= self._max_compact_failures:
                        log.warning(
                            f"Auto-compact circuit breaker tripped after "
                            f"{self._compact_consecutive_failures} consecutive failures — "
                            f"skipping future attempts this session"
                        )
                    else:
                        log.warning(f"Compaction failed ({self._compact_consecutive_failures}/{self._max_compact_failures}): {e}")

            # Background learning — analyze observations every 20 tool calls
            if self.observer.call_count > 0 and self.observer.call_count % 20 == 0:
                try:
                    await self.observer.analyze_observations()
                except Exception:
                    pass  # Non-critical

            try:
                result = await self._step()
                consecutive_errors = 0  # reset on success
            except Exception as e:
                consecutive_errors += 1
                error_str = str(e)
                log.error(f"Agent loop error at iteration {self.state.iteration}: {e}")

                # Auto-compress on context overflow (400 Bad Request)
                if "400" in error_str and consecutive_errors <= 2:
                    log.info("Context overflow detected — force compressing...")
                    try:
                        await compress_context(self.state, self.model, max_tokens=8000, keep_recent=4)
                        log.info("Force compression done, retrying...")
                    except Exception:
                        pass  # compression failed, will retry anyway
                    continue

                self.state.add_system_note(f"Loop error: {e}")
                save_session(self.state, self.session_dir, self.session_id)
                if consecutive_errors >= 5:
                    return f"Agent encountered {consecutive_errors} consecutive errors. Last: {e}"
                continue

            elapsed = time.time() - iter_start
            log.debug(f"Iteration {self.state.iteration} took {elapsed:.1f}s")

            # Auto-save every 5 iterations
            if self.state.iteration % 5 == 0:
                save_session(self.state, self.session_dir, self.session_id)

            if self.state.task_complete:
                log.info(f"Task complete after {self.state.iteration} iterations")
                save_session(self.state, self.session_dir, self.session_id)
                save_session_summary(self.state, self.session_dir, self.session_id)
                self.cost_tracker.save(self.config.workspace_dir)
                log.info(self.cost_tracker.format_summary())
                # Background memory extraction (non-blocking)
                try:
                    await self.observer.extract_session_memories()
                except Exception:
                    pass  # Non-critical
                return result

        # Save on max iterations (incomplete task — summary helps resume)
        save_session(self.state, self.session_dir, self.session_id)
        save_session_summary(self.state, self.session_dir, self.session_id)
        self.cost_tracker.save(self.config.workspace_dir)
        return f"Reached max iterations ({self.config.max_iterations}). Session saved: {self.session_id}"

    async def _step(self, _watcher_depth: int = 0) -> str:
        """Execute one iteration of the agent loop."""

        # 1. Build messages for the LLM
        messages = self.state.to_messages()

        # 2. Call the reasoning core — get exactly one tool call
        response = await self.model.generate(
            messages=messages,
            tools=self.registry.schemas(),
        )

        # 2b. Track LLM usage + cost
        if response.raw and "usage" in response.raw:
            usage = response.raw["usage"]
            latency = response.raw.get("timings", {}).get("total", 0)
            model_name = response.raw.get("model", "")
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
            self.observer.observe_llm_usage(
                prompt_tokens, completion_tokens, model_name, latency,
            )
            self.cost_tracker.record(
                model_name, prompt_tokens, completion_tokens, latency,
            )

        # 3. Extract the tool call
        tool_call = response.tool_call

        if tool_call is None:
            # Model responded with text only — wrap in message_info
            # (enforcing the "always use tools" rule)
            # Clean the content — strip any leaked thinking/JSON before storing
            import re
            clean = re.sub(r'<think>.*?</think>', '', response.content, flags=re.DOTALL).strip()
            clean = re.sub(r'\{[^{}]*"name"\s*:.*', '', clean, flags=re.DOTALL).strip()
            if clean:
                self.state.add_assistant(clean)
                tool_call = ToolCall(name="message_info", arguments={"text": clean})
            else:
                self._empty_steps += 1
                if self._empty_steps >= 3:
                    self.state.add_system_note(
                        "Multiple empty responses. You MUST call a tool. "
                        "If the task is done, call message_result. If stuck, call message_ask."
                    )
                    self._empty_steps = 0
                return ""

        # Reset empty step counter on successful tool call
        self._empty_steps = 0

        # Auto-promote message_info → message_result when it looks like a final answer
        if tool_call.name == "message_info":
            text = tool_call.arguments.get("text", "").lower()
            is_final = any(kw in text for kw in [
                "identified", "conclusion", "summary of findings", "failure point",
                "complete", "results:", "answer:", "the wall", "analysis complete",
            ])
            if is_final:
                log.info("Auto-promoting message_info → message_result (looks like final answer)")
                tool_call = ToolCall(name="message_result", arguments=tool_call.arguments)

        # Detect repetition loop: if model keeps calling message_info
        if tool_call.name == "message_info":
            self._info_streak = getattr(self, '_info_streak', 0) + 1
            self._info_total = getattr(self, '_info_total', 0) + 1
            # Force termination on 3 consecutive OR 6 total message_info calls
            if self._info_streak >= 3 or self._info_total >= 6:
                log.info(f"Info loop detected (streak={self._info_streak}, total={self._info_total}). Forcing termination.")
                # Silent termination — the previous message_info already displayed the answer
                tool_call = ToolCall(
                    name="message_result",
                    arguments={"text": ""},  # empty — don't repeat
                )
                self._info_streak = 0
        else:
            self._info_streak = 0

        log.info(f"[{self.state.iteration}] Tool: {tool_call.name} | Args: {_truncate(tool_call.arguments)}")

        # 4. Watcher replaced by current/circulation/pressure tension system
        # Tension measurement happens at tool choice (above) and delivery (section 9)

        # 5. Record the assistant's response
        self.state.add_assistant(
            response.content,
            tool_call={
                "function": {"name": tool_call.name, "arguments": tool_call.arguments},
            },
        )

        # 5b. Loop detection — if same tool 3+ times in a row, it's a batch
        self._recent_tools.append((tool_call.name, tool_call.arguments))
        if len(self._recent_tools) > 10:
            self._recent_tools = self._recent_tools[-10:]

        # Check for repetition loop (same tool called 3+ times consecutively)
        # Auto-swell: when the wave is doing the same thing 3+ times, hint to use swell
        if len(self._recent_tools) >= 3:
            last_3_names = [t[0] for t in self._recent_tools[-3:]]
            if len(set(last_3_names)) == 1 and last_3_names[0] in ("file_read", "summarize_file", "match_grep"):
                log.info(f"Auto-swell hint: {last_3_names[0]} called 3x in a row")
                self.state.add_system_note(
                    f"You're calling {last_3_names[0]} repeatedly. Use the swell tool to "
                    f"dispatch multiple eddy workers in parallel — it's faster and uses less context. "
                    f"Give each eddy a specific subtask string."
                )

        # 6. Execute the tool — with argument safety
        tool = self.registry.get(tool_call.name)
        if tool is None:
            error_msg = f"Unknown tool: {tool_call.name}. Available: {self.registry.names()}"
            self.state.add_tool_result(tool_call.name, tool_call.arguments, error_msg, is_error=True)
            return error_msg

        # Ensure arguments is a dict (model sometimes sends a JSON string)
        args = tool_call.arguments
        if isinstance(args, str):
            try:
                args = json.loads(args)
                tool_call = ToolCall(name=tool_call.name, arguments=args)
            except (json.JSONDecodeError, TypeError):
                pass
        log.info(f"  Args type={type(tool_call.arguments).__name__}, value={str(tool_call.arguments)[:200]}")

        # Tension check on tool choice — is this the right tool for the task?
        from .current import measure_heuristic
        user_request = self.state.conversation[1].content if len(self.state.conversation) > 1 else ""
        tool_statement = f"User asked: {user_request[:200]}. Agent chose: {tool_call.name}({str(tool_call.arguments)[:200]})"
        tool_tension = measure_heuristic(tool_statement)
        self._pressure.record(tool_tension, tool_call.name)

        if self._pressure.should_refuse():
            log.warning("Pressure: 4+ consecutive high tension — forcing user guidance")
            self.state.add_system_note(
                "PRESSURE CRITICAL: You've made 4+ uncertain decisions in a row. "
                "Stop and use message_ask to get guidance from the user."
            )
        elif self._pressure.should_force_search() and tool_call.name not in ("search_web", "message_ask"):
            log.info(f"Pressure: forcing search (consecutive high tension)")
            self.state.add_system_note(
                "PRESSURE ELEVATED: Consider using search_web to ground your next action."
            )

        # Input validation
        validation_error = tool.validate_input(**tool_call.arguments)
        if validation_error:
            error_msg = f"Validation error for {tool_call.name}: {validation_error}"
            log.warning(error_msg)
            self.state.add_tool_result(tool_call.name, tool_call.arguments, error_msg, is_error=True)
            return error_msg

        # Tool dedup check — skip re-execution of identical read-only calls
        cached = self.tool_dedup.lookup(tool_call.name, tool_call.arguments)
        if cached is not None:
            content, is_error = cached
            log.info(f"  Dedup hit for {tool_call.name} — returning cached result")
            self.state.add_tool_result(tool_call.name, tool_call.arguments, content, is_error=is_error)
            return content

        try:
            result = await tool.execute(**tool_call.arguments)
        except TypeError as e:
            # LLM sent wrong argument names — common with smaller models
            error_msg = f"Bad arguments for {tool_call.name}: {e}. Expected: {list(tool.parameters_schema().get('properties', {}).keys())}"
            log.warning(error_msg)
            self.state.add_tool_result(tool_call.name, tool_call.arguments, error_msg, is_error=True)
            self.state.record_error(tool_call.name, tool_call.arguments, error_msg)
            return error_msg
        except Exception as e:
            error_msg = f"Tool {tool_call.name} crashed: {type(e).__name__}: {e}"
            log.error(error_msg)
            self.state.add_tool_result(tool_call.name, tool_call.arguments, error_msg, is_error=True)
            self.state.record_error(tool_call.name, tool_call.arguments, error_msg)
            return error_msg

        # 7. Persist large results to disk (production pattern)
        # Large outputs go to disk with a 2KB preview in context.
        # file_read is excluded (circular read prevention).
        display_content = result.content
        if not result.is_error:
            display_content = maybe_persist(
                tool_call.name, result.content,
                self.config.workspace_dir, self.session_id,
            )

        # Cache the result for dedup (read-only tools only)
        self.tool_dedup.store(tool_call.name, tool_call.arguments, display_content, result.is_error)
        # Invalidate cache after any write operation
        if tool_call.name in ("file_write", "file_edit", "file_append", "shell_exec"):
            self.tool_dedup.invalidate_on_write()

        # Git operation detection
        if tool_call.name == "shell_exec":
            self.git_tracker.track(
                tool_call.arguments.get("command", ""), result.content
            )

        # Record to state + observation log
        self.state.add_tool_result(
            tool_call.name, tool_call.arguments, display_content, is_error=result.is_error
        )
        self.observer.observe_tool_call(
            tool_call.name, tool_call.arguments, result.content,
            result.is_error, self.session_id,
        )

        # 8a. Auto-undertow — run QA immediately after writing HTML/JS/CSS
        if tool_call.name in ("file_write", "file_edit") and not result.is_error:
            written_path = tool_call.arguments.get("path", "")
            if written_path.endswith((".html", ".htm")):
                try:
                    from .undertow import run_drag
                    user_req = self.state.conversation[1].content if len(self.state.conversation) > 1 else ""
                    qa = await run_drag(written_path, user_request=user_req)
                    failed = qa.get("levers_failed", 0)
                    total = qa.get("levers_total", 0)
                    tension = qa.get("code_tension", 0)
                    self._pressure.record(tension, "undertow")

                    if not qa["passed"] and qa["errors"]:
                        error_list = "\n".join(f"  - {e}" for e in qa["errors"][:5])
                        self.state.add_system_note(
                            f"UNDERTOW ({failed}/{total} failed):\n{error_list}"
                        )
                        log.info(f"Auto-undertow: {failed}/{total} failed, tension={tension:.2f}")
                    else:
                        log.info(f"Auto-undertow: PASS ({total} levers, tension={tension:.2f})")
                except Exception as e:
                    log.debug(f"Auto-undertow skipped: {e}")

        # 8b. Save-findings nudge (Ark: save to files every 2-3 tool calls)
        if self.state.iteration > 0 and self.state.iteration % 5 == 0:
            # Check if agent has written any files recently
            recent_writes = sum(
                1 for m in self.state.conversation[-10:]
                if m.role == "tool_result" and any(w in m.content for w in ["Wrote", "Edited", "Appended"])
            )
            if recent_writes == 0:
                self.state.add_system_note(
                    "You haven't saved anything to files in 5 iterations. "
                    "Save your findings/progress to a file NOW before context is lost."
                )

        # 8. Error tracking
        if result.is_error:
            self.state.record_error(tool_call.name, tool_call.arguments, result.content)
            if self.state.should_escalate(tool_call.name, tool_call.arguments):
                self.state.add_system_note(
                    "3 failures on same approach. You must try a fundamentally different "
                    "approach or use message_ask to request guidance from the user."
                )

        # 9. Tension gate — measure current before allowing delivery
        if tool_call.name == "message_result":
            from .current import measure_heuristic, UNCERTAIN, DRIFTING
            from .circulation import Circulation

            tension = measure_heuristic(result.content)
            self._pressure.record(tension, tool_call.name)

            # Track delivery attempts — prevent infinite block loops
            self._delivery_attempts = getattr(self, '_delivery_attempts', 0) + 1

            # Always evaluate tension — but only BLOCK if this is a factual claim,
            # not a build delivery, and we haven't already blocked twice
            can_block = (
                self._delivery_attempts <= 5
                and self.state.iteration < self.config.max_iterations - 1
            )

            circ = Circulation()
            route = circ.route(
                self.state.conversation[1].content if len(self.state.conversation) > 1 else "",
                tension,
            )

            log.info(
                f"Tension gate: tension={tension:.2f} route={route.action} "
                f"delivery_attempt={self._delivery_attempts} can_block={can_block}"
            )

            if can_block:
                if route.action == "refuse":
                    log.warning(f"Tension gate: REFUSING delivery (tension={tension:.2f})")
                    self.state.add_system_note(
                        f"TENSION CRITICAL ({tension:.2f}): Your response is likely hallucinated. "
                        f"Either search to verify your claims, or say you don't know. "
                        f"Do NOT deliver unverified content."
                    )
                    return result.content

                if route.action in ("search", "caveat"):
                    did_search = any(
                        "search_web" in m.content or "browser_navigate" in m.content
                        for m in self.state.conversation if m.role == "tool_result"
                    )
                    if not did_search:
                        log.info(f"Tension gate: forcing verification (tension={tension:.2f})")
                        self.state.add_system_note(
                            f"TENSION ELEVATED ({tension:.2f}): Your response needs verification. "
                            f"Search external sources before delivering. Tools suggested: {route.tools}"
                        )
                        return result.content

                # Adversarial review — cross-examine reasoning before delivery
                if len(result.content) > 200 and self.state.iteration < self.config.max_iterations - 2:
                    try:
                        from .adversarial import review_before_delivery
                        should_deliver, review_text = await review_before_delivery(
                            result.content,
                            self.state.conversation[1].content if len(self.state.conversation) > 1 else "",
                        )
                        if not should_deliver and review_text:
                            log.info("Adversarial review: FAIL — sending objections back to wave")
                            self.state.add_system_note(review_text)
                            return result.content  # don't terminate — let wave address objections
                    except Exception as e:
                        log.debug(f"Adversarial review skipped: {e}")
            elif self._delivery_attempts > 2:
                log.info(f"Tension gate: allowing delivery after {self._delivery_attempts} attempts (loop prevention)")

            # 10. Code tension — undertow QA gate for file deliveries
            # Find the last HTML file written in this session
            last_html = None
            for msg in reversed(self.state.conversation):
                if msg.role == "tool_result" and ".html" in msg.content:
                    import re as _re
                    paths = _re.findall(r'(/[^\s"\']+\.html)', msg.content)
                    if paths:
                        last_html = paths[0]
                        break

            if last_html and self._delivery_attempts <= 5 and self.state.iteration < self.config.max_iterations - 2:
                try:
                    from .undertow import run_drag
                    user_req = self.state.conversation[1].content if len(self.state.conversation) > 1 else ""
                    qa = await run_drag(last_html, user_request=user_req)

                    # Record code tension into pressure alongside prose tension
                    code_tension = qa.get("code_tension", 0.0)
                    self._pressure.record(code_tension, "undertow")
                    log.info(
                        f"Undertow: code_tension={code_tension:.2f} "
                        f"({qa.get('levers_failed', 0)}/{qa.get('levers_total', 0)} failed)"
                    )

                    if not qa["passed"] and qa["errors"]:
                        error_list = "\n".join(f"  - {e}" for e in qa["errors"][:5])
                        log.info(f"Undertow gate: FAIL — {len(qa['errors'])} error(s)")
                        self.state.add_system_note(
                            f"UNDERTOW QA ({qa.get('levers_failed', 0)}/{qa.get('levers_total', 0)} levers failed):\n"
                            f"{error_list}"
                        )
                        return result.content
                    elif qa["passed"]:
                        log.info(f"Undertow gate: PASS — {last_html}")
                except Exception as e:
                    log.debug(f"Undertow gate skipped: {e}")

            # All gates passed — deliver
            self._delivery_attempts = 0
            if tension < DRIFTING:
                self._pressure.reset()
            self.state.task_complete = True
            return result.content

        return result.content


def _truncate(d: dict, max_len: int = 200) -> str:
    s = json.dumps(d)
    return s[:max_len] + "..." if len(s) > max_len else s
