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

        # Propagate eddy endpoint to all modules via env var
        # On lite mode, this points at the same port as the wave
        import os
        os.environ["TSUNAMI_EDDY_ENDPOINT"] = config.eddy_endpoint

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

        # Closed-loop feedback — track tool outcomes, steer decisions
        from .feedback import FeedbackTracker
        self._feedback = FeedbackTracker()

        # Stall detection — abort on no-progress loops
        self._empty_steps = 0
        self._tool_history: list[str] = []  # last N tool calls
        self._project_init_called = False  # block repeated scaffold
        self._has_researched = False  # research gate — must search before writing

        # Auto-compact circuit breaker
        # Stops retrying compression after N consecutive failures
        self._compact_consecutive_failures = 0
        self._max_compact_failures = 3

        # Loop detection for auto-swell
        self._recent_tools: list[tuple[str, dict]] = []  # (tool_name, args) ring buffer

        # Active project context
        self.active_project: str | None = None
        self.project_context: str = ""

    def _detect_existing_project(self, user_message: str) -> str:
        """Check if an existing project matches this prompt.

        If found, load the project context so the agent can iterate
        instead of building from scratch. This enables:
        - "make the buttons bigger" → edits the existing project
        - "add dark mode" → extends what's already built
        - "fix the calculator" → loads and fixes
        """
        msg = user_message.lower()

        # Explicit "start fresh" — skip iteration detection
        fresh_keywords = ["start fresh", "from scratch", "new project", "brand new", "start over"]
        if any(k in msg for k in fresh_keywords):
            return ""

        # Keywords that suggest iteration, not greenfield
        iteration_keywords = ["fix", "improve", "change", "update", "add", "modify",
                              "make it", "bigger", "smaller", "different", "better",
                              "the calculator", "the dashboard", "the game", "my app",
                              "broken", "not working", "white screen", "blank page"]
        is_iteration = any(k in msg for k in iteration_keywords)

        deliverables = Path(self.config.workspace_dir) / "deliverables"
        if not deliverables.exists():
            return ""

        # Find the best matching project
        projects = [d for d in deliverables.iterdir() if d.is_dir() and not d.name.startswith(".")]
        if not projects:
            return ""

        # Score each project by keyword overlap with the prompt
        import re
        skip_words = {"the", "this", "that", "and", "for", "with", "build", "make",
                      "create", "app", "fix", "change", "update", "improve", "add",
                      "want", "need", "something", "into", "instead", "please"}
        prompt_words = set(re.findall(r'[a-z]{3,}', msg)) - skip_words
        best_match = None
        best_score = 0

        for proj in projects:
            name_words = set(re.findall(r'[a-z]{3,}', proj.name.lower()))
            overlap = len(prompt_words & name_words)
            if overlap > best_score:
                best_score = overlap
                best_match = proj

        # Also check most recent project if it's an iteration request
        if is_iteration and not best_match:
            best_match = max(projects, key=lambda p: p.stat().st_mtime)
            best_score = 1  # low confidence but iteration intent is clear

        if not best_match or best_score < 1:
            return ""

        # Load the project context
        self.active_project = best_match.name
        app_path = best_match / "src" / "App.tsx"
        types_path = best_match / "src" / "types.ts"
        pkg_path = best_match / "package.json"

        # Check if it's a stub project (scaffolded but never built)
        if app_path.exists():
            app_content = app_path.read_text()
            is_stub = "TODO" in app_content or "Loading..." in app_content or len(app_content) < 100
            if is_stub and not is_iteration:
                # Stub project — don't load as "existing", let pre-scaffold handle it
                log.info(f"Iterative refinement: {best_match.name} is a stub — treating as new")
                return ""

        context_parts = [
            f"[EXISTING PROJECT: {best_match.name}]",
            f"Path: {best_match}",
        ]

        if app_path.exists():
            content = app_path.read_text()[:1500]
            context_parts.append(f"Current App.tsx:\n```\n{content}\n```")

        if types_path.exists():
            content = types_path.read_text()[:800]
            context_parts.append(f"Types:\n```\n{content}\n```")

        # List component files
        comp_dir = best_match / "src" / "components"
        if comp_dir.exists():
            comps = [f.stem for f in comp_dir.iterdir() if f.suffix in ('.tsx', '.ts') and f.stem != 'index']
            if comps:
                context_parts.append(f"Components: {', '.join(sorted(comps))}")

        # Regression check — does the existing project build?
        build_status = "unknown"
        build_errors = ""
        if (best_match / "package.json").exists() and (best_match / "node_modules").exists():
            try:
                import subprocess
                build = subprocess.run(
                    ["npx", "vite", "build"],
                    cwd=str(best_match), capture_output=True, text=True, timeout=30,
                )
                if build.returncode == 0:
                    build_status = "passes"
                else:
                    build_status = "BROKEN"
                    errors = [l.strip() for l in build.stderr.splitlines() if "Error" in l][:3]
                    if errors:
                        build_errors = "\nBuild errors:\n" + "\n".join(f"  {e}" for e in errors)
            except Exception:
                pass
        elif (best_match / "package.json").exists():
            build_status = "NEEDS npm install"

        if build_status == "BROKEN":
            context_parts.append(
                f"WARNING: This project exists but is BROKEN (won't compile).{build_errors}\n"
                "Fix the build errors first, then make the requested changes. "
                "Use file_edit to fix existing files. Use file_read to understand what's broken."
            )
        elif build_status == "NEEDS npm install":
            context_parts.append(
                "This project exists but needs dependencies installed. "
                "Run: shell_exec 'cd <project_dir> && npm install' first."
            )
        else:
            context_parts.append(
                f"This project already exists (build: {build_status}). "
                "Use file_edit to modify existing files instead of file_write (which overwrites). "
                "Read the current code first. After changes, verify the build still passes."
            )

        # Detect transformation intent — "change X to Y", "make it into", "convert"
        transform_keywords = ["change", "convert", "transform", "turn it into",
                              "make it", "switch to", "replace with", "instead"]
        is_transform = any(k in msg for k in transform_keywords)
        if is_transform:
            context_parts.append(
                "\nIMPORTANT: The user wants to TRANSFORM this project. "
                "You MUST rewrite the code to match the new request. "
                "Do NOT say 'no changes needed' — the current code is for the OLD purpose. "
                "Rewrite App.tsx and components to match what the user is asking for NOW."
            )

        log.info(f"Iterative refinement: matched '{best_match.name}' (score={best_score}, transform={is_transform})")
        return "\n".join(context_parts)

    async def _pre_scaffold(self, user_message: str) -> str:
        """Hidden pre-scaffold step — detect build tasks, provision automatically.

        Like the classifier layer: analyze the prompt, pick the right scaffold,
        provision the project BEFORE the model starts. The model wakes up
        inside a ready project with a README.
        """
        msg = user_message.lower()

        # Detect build tasks
        build_keywords = ["build", "create", "make", "develop", "design",
                          "app", "game", "website", "dashboard", "tool",
                          "tracker", "page", "editor", "viewer"]
        is_build = any(k in msg for k in build_keywords)
        if not is_build:
            return ""

        # Extract project name from the message
        import re
        # Try to find "save to workspace/deliverables/X" or infer from context
        save_match = re.search(r'deliverables/([a-z0-9_-]+)', msg)
        if save_match:
            project_name = save_match.group(1)
        else:
            # Generate a name from key words
            words = re.findall(r'[a-z]+', msg)
            skip = {"build", "create", "make", "a", "an", "the", "with", "and",
                    "for", "that", "app", "save", "to", "workspace"}
            name_words = [w for w in words if w not in skip and len(w) > 2][:3]
            project_name = "-".join(name_words) if name_words else ""

        if not project_name:
            return ""

        # Check if project already exists
        project_dir = Path(self.config.workspace_dir) / "deliverables" / project_name
        if (project_dir / "package.json").exists():
            return ""

        # Provision via project_init
        try:
            from .tools.project_init import ProjectInit
            init_tool = ProjectInit(self.config)
            result = await init_tool.execute(name=project_name)
            if not result.is_error:
                log.info(f"Pre-scaffold: provisioned '{project_name}'")
                return f"\n[Project '{project_name}' has been scaffolded at {project_dir}. " \
                       f"Dev server running. Write your components in src/.]\n\n{result.content}"
        except Exception as e:
            log.debug(f"Pre-scaffold failed: {e}")

        return ""

    def _auto_wire_on_exit(self):
        """Auto-wire any stub App.tsx in deliverables before exiting.

        Scans all projects the wave wrote to. If App.tsx is a stub
        but components exist, generate imports automatically.
        """
        deliverables = Path(self.config.workspace_dir) / "deliverables"
        if not deliverables.exists():
            return

        for project_dir in deliverables.iterdir():
            if not project_dir.is_dir():
                continue
            app_path = project_dir / "src" / "App.tsx"
            comp_dir = project_dir / "src" / "components"
            if not app_path.exists() or not comp_dir.exists():
                continue

            app_content = app_path.read_text()
            is_stub = "TODO" in app_content or "not built yet" in app_content or (
                len(app_content) < 200 and "import" not in app_content.lower()
            )
            components = [
                f.stem for f in comp_dir.iterdir()
                if f.suffix in ('.tsx', '.ts') and f.stem not in ('index', 'types')
            ]
            if is_stub and components:
                imports = "\n".join(f'import {c} from "./components/{c}"' for c in sorted(components))
                jsx = "\n        ".join(f'<{c} />' for c in sorted(components))
                auto_app = (
                    f'import "./index.css"\n{imports}\n\n'
                    f'export default function App() {{\n'
                    f'  return (\n'
                    f'    <div className="container">\n'
                    f'      {jsx}\n'
                    f'    </div>\n'
                    f'  )\n'
                    f'}}\n'
                )
                app_path.write_text(auto_app)
                log.info(f"Auto-wired {project_dir.name}/App.tsx with {len(components)} components")

    def _inject_todo(self):
        """Inject todo.md into context if it exists in any active deliverable.

        The checklist is the attention mechanism. The wave reads it every
        iteration to know what's done and what's next. Without this,
        the 9B forgets steps because the plan is in context, not on disk.
        """
        # Find todo.md in the most recently written deliverable
        deliverables = Path(self.config.workspace_dir) / "deliverables"
        if not deliverables.exists():
            return

        # Check recent tool results for which project we're working on
        for msg in reversed(self.state.conversation[-10:]):
            if msg.role == "tool_result" and "deliverables/" in msg.content:
                import re
                match = re.search(r'deliverables/([^/\s]+)', msg.content)
                if match:
                    todo_path = deliverables / match.group(1) / "todo.md"
                    if todo_path.exists():
                        try:
                            content = todo_path.read_text()
                            # Only inject if it has unchecked items
                            if "[ ]" in content:
                                self.state.add_system_note(
                                    f"CHECKLIST (todo.md):\n{content}"
                                )
                        except Exception:
                            pass
                    return

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
        - an unrecoverable error occurs
        - abort signal received

        There is no iteration cap. The agent iterates until it finishes.
        """

        # Build system prompt — lite mode gets a shorter, simpler prompt
        is_lite = self.config.eddy_endpoint == self.config.model_endpoint
        system_prompt = build_system_prompt(
            self.state, self.config.workspace_dir, self.config.skills_dir,
            lite=is_lite,
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

        # Iterative refinement — detect existing projects that match the prompt
        existing_context = self._detect_existing_project(user_message)

        # Hidden pre-scaffold step — detect build tasks and provision automatically
        # The model never chooses the scaffold. The platform does.
        scaffold_context = ""
        if not existing_context:
            scaffold_context = await self._pre_scaffold(user_message)

        context_parts = [user_message]
        if existing_context:
            context_parts.append(existing_context)
        if scaffold_context:
            context_parts.append(scaffold_context)
        self.state.add_user("\n\n".join(context_parts))

        log.info(f"Starting agent loop: {user_message[:100]}")
        consecutive_errors = 0

        while True:
            self.state.iteration += 1
            iter_start = time.time()

            # Safety valve — force deliver if truly lost
            if self.state.iteration > 30:
                # Check RECENT writes (last 20 tools), not all-time
                recent = self._tool_history[-20:] if len(self._tool_history) > 20 else self._tool_history
                recent_writes = sum(1 for t in recent if t in ("file_write", "file_edit", "project_init"))
                if recent_writes == 0 and self.state.iteration > 50:
                    log.warning(f"Safety valve: {self.state.iteration} iters, 0 writes in last 20 — forcing exit")
                    self.state.task_complete = True
                    return "Task ended — no progress detected."
                # Hard cap — nothing should ever run more than 200 iterations
                if self.state.iteration > 200:
                    log.warning(f"Hard cap: {self.state.iteration} iterations — forcing exit")
                    self.state.task_complete = True
                    return f"Task ended after {self.state.iteration} iterations."

            # Check abort signal
            if self.abort_signal.aborted:
                log.info(f"Abort signal received: {self.abort_signal.reason}")
                self._auto_wire_on_exit()
                save_session(self.state, self.session_dir, self.session_id)
                save_session_summary(self.state, self.session_dir, self.session_id)
                self.cost_tracker.save(self.config.workspace_dir)
                return f"Aborted: {self.abort_signal.reason}"

            # Time-based microcompact
            # Clears cold tool results when prompt cache has likely expired
            microcompact_if_needed(self.state)

            # Context management — only clear stale tool results, not architecture
            # 9B at 32K: barely needs compression. Let context grow.
            # 2B at 16K: prune stale reads every 3 iterations.
            # Never destroy plan, types, or user request.
            if is_lite and self.state.iteration > 0 and self.state.iteration % 3 == 0:
                freed = fast_prune(self.state, keep_recent=4)
                if freed > 0:
                    log.info(f"Lite prune: freed {freed} tokens")

            # Heavy compaction only at the actual limit (not premature)
            # 9B: 28K threshold (leaves 4K headroom in 32K)
            # 2B: 12K threshold (leaves 4K headroom in 16K)
            compact_threshold = 12000 if is_lite else 28000
            should_compact = False
            if self._compact_consecutive_failures >= self._max_compact_failures:
                pass
            elif needs_compression(self.state, max_tokens=compact_threshold):
                should_compact = True

            if should_compact:
                try:
                    keep = 4 if is_lite else 8
                    freed = fast_prune(self.state, keep_recent=keep)
                    if needs_compression(self.state, max_tokens=compact_threshold):
                        log.info(f"Prune freed {freed} tokens, still over — full compress")
                        await compress_context(self.state, self.model, max_tokens=compact_threshold, keep_recent=keep)
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

            # Auto-inject todo.md if it exists in the active project
            # This is the attention mechanism — the wave reads its checklist every iteration
            self._inject_todo()

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

        # Should never reach here — loop exits via task_complete, abort, or error
        self._auto_wire_on_exit()
        save_session(self.state, self.session_dir, self.session_id)
        save_session_summary(self.state, self.session_dir, self.session_id)
        self.cost_tracker.save(self.config.workspace_dir)
        return f"Agent loop exited unexpectedly after {self.state.iteration} iterations. Session saved: {self.session_id}"

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
                "built successfully", "all required elements", "ready to use",
                "ready to deliver", "build succeeded", "all components created",
                "compiled without errors", "compiled successfully",
                "hello", "hi!", "how can i help", "what would you like",
                "ready to help", "i can help", "let me know",
            ])
            if is_final:
                log.info("Auto-promoting message_info → message_result (looks like final answer)")
                tool_call = ToolCall(name="message_result", arguments=tool_call.arguments)

        # Detect repetition loop: if model keeps calling message_info
        if tool_call.name == "message_info":
            self._info_streak = getattr(self, '_info_streak', 0) + 1
            self._info_total = getattr(self, '_info_total', 0) + 1
            # Force termination on 2 consecutive OR 3 total message_info calls
            if self._info_streak >= 2 or self._info_total >= 3:
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

        # 3b. Stall detection — detect no-progress loops
        self._tool_history.append(tool_call.name)
        if len(self._tool_history) > 10:
            self._tool_history = self._tool_history[-10:]
        # If last 8 calls are all read-only tools → stalled
        if len(self._tool_history) >= 8:
            recent = self._tool_history[-8:]
            read_only = {"message_info", "search_web", "file_read", "match_glob",
                         "match_grep", "summarize_file", "shell_exec", "undertow"}
            no_writes = all(t in read_only for t in recent)
            if no_writes:
                # Check if build already passed — verification stall
                has_delivered = any(t == "message_info" for t in self._tool_history[-15:])
                if has_delivered and self.state.iteration > 20:
                    log.warning("Verification stall: build looks done, forcing delivery")
                    self.state.add_system_note(
                        "VERIFICATION STALL: You've been checking the build for 8+ calls "
                        "without making changes. The build compiled. Call message_result NOW."
                    )
                else:
                    log.warning("Stall detected: 8 consecutive read-only tools")
                    self.state.add_system_note(
                        "STALL: You've made 8 tool calls without writing any files. "
                        "Stop researching and start building. Write code now."
                    )

        # 3c0. Pre-execution validation — skip duplicate/wasteful tool calls
        if tool_call.name == "search_web":
            query = tool_call.arguments.get("query", "")
            prev_queries = getattr(self, '_search_queries', set())
            if query in prev_queries:
                self.state.add_system_note(
                    f"DUPLICATE SEARCH: You already searched for '{query[:60]}'. "
                    f"Use the results you got earlier or try a different query."
                )
            prev_queries.add(query)
            self._search_queries = prev_queries

        # 3c. Research gate — nudge research before writing code
        if tool_call.name in ("search_web", "browser_navigate"):
            self._has_researched = True
        if tool_call.name in ("file_write", "file_edit") and not self._has_researched:
            written_path = tool_call.arguments.get("path", "")
            if "deliverables/" in written_path and written_path.endswith((".tsx", ".ts", ".css")):
                # Check if this looks like a visual build task
                user_req = self.state.conversation[1].content if len(self.state.conversation) > 1 else ""
                visual_keywords = ["game", "ui", "design", "calculator", "gameboy", "interface",
                                   "dashboard", "visual", "replica", "clone", "pixel", "retro"]
                if any(k in user_req.lower() for k in visual_keywords):
                    self.state.add_system_note(
                        "RESEARCH FIRST: You're writing code for a visual project but haven't "
                        "searched for any reference images or code yet. Use search_web with "
                        'type="image" to find reference images of what you\'re building. '
                        "Study the reference BEFORE writing code. This is mandatory."
                    )
                    # Don't block the write — just nudge once
                    self._has_researched = True  # only nudge once

        # 3d. Block repeated project_init — only scaffold once per session
        if tool_call.name == "project_init":
            if self._project_init_called:
                log.info("Blocked repeated project_init call")
                self.state.add_tool_result(
                    tool_call.name, tool_call.arguments,
                    "Project already scaffolded this session. Write your components in src/.",
                    is_error=True,
                )
                return "Project already scaffolded."
            self._project_init_called = True

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

        # Write-swell: when wave writes 2+ component files sequentially,
        # check if App.tsx references more missing components and dispatch eddies
        _write_swelled = getattr(self, '_write_swelled', False)
        if not _write_swelled and len(self._recent_tools) >= 2:
            last_2 = self._recent_tools[-2:]
            both_writes = all(t[0] == "file_write" for t in last_2)
            both_components = both_writes and all(
                "components/" in str(t[1].get("path", "")) for t in last_2
            )
            if both_components:
                # The wave is writing components sequentially — check if more are needed
                try:
                    last_path = str(last_2[-1][1].get("path", ""))
                    parts = last_path.split("deliverables/")
                    if len(parts) > 1:
                        project_name = parts[1].split("/")[0]
                        project_dir = Path(self.config.workspace_dir) / "deliverables" / project_name
                        app_path = project_dir / "src" / "App.tsx"
                        comp_dir = project_dir / "src" / "components"
                        if app_path.exists() and comp_dir.exists():
                            import re as _ws_re
                            app_content = app_path.read_text()
                            imports = _ws_re.findall(r'from\s+["\']\.\/components\/(\w+)["\']', app_content)
                            missing = [c for c in imports if not (comp_dir / f"{c}.tsx").exists()]
                            if len(missing) >= 2:
                                self._write_swelled = True
                                user_req = self.state.conversation[1].content if len(self.state.conversation) > 1 else ""
                                types_ctx = ""
                                types_path = project_dir / "src" / "types.ts"
                                if types_path.exists():
                                    types_ctx = f"\n\nShared types:\n```\n{types_path.read_text()[:1500]}\n```"

                                tasks = []
                                targets = []
                                for comp in missing[:6]:
                                    target = str(comp_dir / f"{comp}.tsx")
                                    prompt = (
                                        f"Write React component {comp} for: {user_req[:200]}\n"
                                        f"Export default function {comp}. Under 80 lines.{types_ctx}"
                                    )
                                    tasks.append(prompt)
                                    targets.append(target)

                                log.info(f"Write-swell: {len(tasks)} missing components detected, dispatching eddies")
                                from .eddy import run_swarm
                                swell_results = await run_swarm(
                                    tasks=tasks, workdir=str(project_dir),
                                    max_concurrent=4,
                                    system_prompt="You are a React TypeScript expert. Call done() with ONLY the raw TSX code. Export default function ComponentName.",
                                    write_targets=targets,
                                )
                                written = sum(1 for r in swell_results if r.success)
                                self.state.add_system_note(
                                    f"WRITE-SWELL: {written}/{len(tasks)} remaining components written by eddies: "
                                    f"{', '.join(missing[:6])}. Continue with vite build to compile-check."
                                )
                except Exception as e:
                    log.debug(f"Write-swell skipped: {e}")

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
            self._dedup_hits = getattr(self, '_dedup_hits', 0) + 1
            log.info(f"  Dedup hit #{self._dedup_hits} for {tool_call.name} — returning cached result")
            self.state.add_tool_result(tool_call.name, tool_call.arguments, content, is_error=is_error)
            # After 3 consecutive dedup hits, the agent is stuck in a loop
            if self._dedup_hits >= 3:
                self.state.add_system_note(
                    f"LOOP DETECTED: You've called {tool_call.name} with the same arguments "
                    f"{self._dedup_hits} times and got the same result. Try a different approach. "
                    f"If the task is done, call message_result. If stuck, modify the code and retry."
                )
                # Invalidate this specific cache entry so the loop can't repeat
                self.tool_dedup.invalidate(tool_call.name)
                self._dedup_hits = 0
            return content
        else:
            self._dedup_hits = 0  # reset on non-cached call

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

        # Closed-loop feedback — record outcome and inject steering advice
        made_progress = tool_call.name in ("file_write", "file_edit", "project_init", "generate_image") and not result.is_error
        self._feedback.record(tool_call.name, not result.is_error, made_progress, str(result.content)[:100] if result.is_error else "")
        nudge = self._feedback.get_nudge(self.state.iteration)
        if nudge:
            self.state.add_system_note(nudge)
            log.info(f"Feedback nudge: {nudge[:60]}")

        # 8rs. Research swell — on first search, dispatch parallel research eddies
        _research_swelled = getattr(self, '_research_swelled', False)
        if tool_call.name == "search_web" and not result.is_error and not _research_swelled:
            self._research_swelled = True
            user_req = self.state.conversation[1].content if len(self.state.conversation) > 1 else ""
            if len(user_req) > 20:  # meaningful request, not just "hi"
                try:
                    query = tool_call.arguments.get("query", "")
                    from .eddy import run_swarm
                    # Fire 2 parallel research eddies with different search angles
                    research_tasks = [
                        f"Search for code examples of: {user_req[:200]}. Find GitHub repos or code snippets. Call done() with the best findings.",
                        f"Search for UI/design reference images of: {user_req[:200]}. Find visual examples. Call done() with image URLs and descriptions.",
                    ]
                    research_results = await run_swarm(
                        tasks=research_tasks,
                        workdir=str(Path(self.config.workspace_dir)),
                        max_concurrent=2,
                        system_prompt="You are a research assistant. Search the web, find useful results, call done() with your findings. Be concise.",
                    )
                    # Inject findings into context
                    findings = []
                    for r in research_results:
                        if r.success and r.output and len(r.output) > 20:
                            findings.append(r.output[:500])
                    if findings:
                        self.state.add_system_note(
                            f"PARALLEL RESEARCH ({len(findings)} eddies found results):\n" +
                            "\n---\n".join(findings)
                        )
                        log.info(f"Research swell: {len(findings)} eddies returned findings")
                except Exception as e:
                    log.debug(f"Research swell skipped: {e}")

        # 8ref. Auto-save reference — when search returns images, save URLs to project
        if tool_call.name == "search_web" and not result.is_error:
            search_type = tool_call.arguments.get("search_type", "")
            if search_type == "image" or "image" in result.content.lower()[:50]:
                # Find active project and save reference URLs
                try:
                    deliverables = Path(self.config.workspace_dir) / "deliverables"
                    if deliverables.exists():
                        # Find most recent project
                        projects = sorted(deliverables.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
                        for proj in projects:
                            if proj.is_dir() and not proj.name.startswith("."):
                                ref_file = proj / "reference.md"
                                # Append search results to reference file
                                import re as _ref_re
                                urls = _ref_re.findall(r'URL:\s*(https?://\S+)', result.content)
                                if urls:
                                    existing = ref_file.read_text() if ref_file.exists() else "# Reference\n"
                                    query = tool_call.arguments.get("query", "")
                                    existing += f"\n## {query}\n"
                                    for url in urls[:5]:
                                        existing += f"- {url}\n"
                                    ref_file.write_text(existing)
                                    log.info(f"Saved {len(urls)} reference URLs to {ref_file}")
                                break
                except Exception as e:
                    log.debug(f"Reference save skipped: {e}")

        # 8vg. Auto-ground — after generate_image, extract element positions
        # Only fires ONCE per session (first generate_image), only for UI replication tasks
        _grounded = getattr(self, '_has_grounded', False)
        if tool_call.name == "generate_image" and not result.is_error and not _grounded:
            save_path = tool_call.arguments.get("save_path", "")
            if save_path and Path(save_path).exists():
                try:
                    # Only ground for UI replication tasks (device/interface replicas)
                    user_req = self.state.conversation[1].content if len(self.state.conversation) > 1 else ""
                    ui_task = any(k in user_req.lower() for k in [
                        "replica", "clone", "gameboy", "game boy", "calculator",
                        "console", "device", "interface", "remote", "dmg",
                    ])
                    if not ui_task:
                        raise ValueError("Not a UI replication task — skip grounding")
                    self._has_grounded = True
                    # Extract likely UI elements from the request
                    element_keywords = {
                        "button": ["A button", "B button"],
                        "d-pad": ["D-pad"],
                        "dpad": ["D-pad"],
                        "screen": ["screen", "LCD screen"],
                        "speaker": ["speaker grille"],
                        "start": ["START button"],
                        "select": ["SELECT button"],
                        "keyboard": ["keyboard", "keypad"],
                        "display": ["display", "screen"],
                        "logo": ["logo", "brand text"],
                    }
                    elements = []
                    for keyword, names in element_keywords.items():
                        if keyword in user_req.lower():
                            elements.extend(names)
                    # Always look for the main body/casing
                    elements.append("main body/casing")

                    if elements:
                        from .tools.vision_ground import VisionGround, _parse_grounding_response
                        vg = VisionGround(self.config)
                        ground_result = await vg.execute(image_path=save_path, elements=elements)
                        if not ground_result.is_error:
                            log.info(f"Auto-ground: extracted positions for {len(elements)} elements")
                            # Write a layout.css file into the project with the grounded positions
                            # This is a FILE, not a note — the 9B imports it instead of guessing
                            try:
                                deliverables = Path(self.config.workspace_dir) / "deliverables"
                                if deliverables.exists():
                                    projects = sorted(deliverables.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
                                    for proj in projects:
                                        if proj.is_dir() and not proj.name.startswith("."):
                                            # Extract aspect ratio if present
                                            import re as _ar_re
                                            ar_match = _ar_re.search(r'ASPECT_RATIO:\s*(\d+):(\d+)', ground_result.content)
                                            ar_w, ar_h = (7, 12) if not ar_match else (int(ar_match.group(1)), int(ar_match.group(2)))
                                            # All positions are ratios — resolution independent
                                            css_lines = [
                                                "/* AUTO-GENERATED from vision grounding */",
                                                "/* All positions are RATIOS (%) — resolution independent */",
                                                "/* Import: import './layout.css' */",
                                                "",
                                                ".device-body {",
                                                "  position: relative;",
                                                f"  aspect-ratio: {ar_w} / {ar_h};",
                                                "  width: min(90vw, 320px);",
                                                "  margin: 0 auto;",
                                                "}",
                                                "",
                                            ]
                                            # Parse CSS positioning hints from the grounding output
                                            for line in ground_result.content.splitlines():
                                                if line.strip().startswith(".") and "{" in line:
                                                    css_lines.append(line.strip())

                                            layout_path = proj / "src" / "layout.css"
                                            layout_path.parent.mkdir(parents=True, exist_ok=True)
                                            layout_path.write_text("\n".join(css_lines) + "\n")
                                            log.info(f"Wrote grounded layout to {layout_path}")

                                            # Save to reference.md too
                                            ref_file = proj / "reference.md"
                                            existing = ref_file.read_text() if ref_file.exists() else "# Reference\n"
                                            existing += f"\n## Element Positions\n```\n{ground_result.content}\n```\n"
                                            ref_file.write_text(existing)

                                            # Tell the agent about the file
                                            self.state.add_system_note(
                                                f"LAYOUT FILE WRITTEN: src/layout.css\n"
                                                f"Import it: import './layout.css'\n"
                                                f"Use class .device-body as the container (position:relative, portrait 280x480).\n"
                                                f"Each element has a class with position:absolute and exact percentages.\n"
                                                f"DO NOT override these positions with inline styles. Use the classes.\n\n"
                                                f"Elements found:\n{ground_result.content}"
                                            )
                                            break
                            except Exception as e:
                                log.debug(f"Layout CSS write failed: {e}")
                                # Fallback: just inject as note
                                self.state.add_system_note(
                                    f"ELEMENT POSITIONS:\n{ground_result.content}\n\n"
                                    f"Use these exact positions. position:absolute inside position:relative."
                                )
                except Exception as e:
                    log.debug(f"Auto-ground skipped: {e}")

        # 8a0. Auto-scaffold — if .tsx written to deliverables without package.json, provision it
        if tool_call.name == "file_write" and not result.is_error:
            written_path = tool_call.arguments.get("path", "")
            if "deliverables/" in written_path and written_path.endswith((".tsx", ".ts")):
                try:
                    parts = written_path.split("deliverables/")
                    if len(parts) > 1:
                        project_name = parts[1].split("/")[0]
                        project_dir = Path(self.config.workspace_dir) / "deliverables" / project_name
                        if project_dir.exists() and not (project_dir / "package.json").exists():
                            log.info(f"Auto-scaffold: {project_name} missing package.json, provisioning")
                            from .tools.project_init import ProjectInit
                            init_tool = ProjectInit(self.config)
                            scaffold_result = await init_tool.execute(name=project_name)
                            log.info(f"Auto-scaffold: {scaffold_result.content[:100]}")
                except Exception as e:
                    log.debug(f"Auto-scaffold skipped: {e}")

        # 8td. Auto-generate todo.md from plan — the checklist drives iteration
        if tool_call.name == "plan_update" and not result.is_error:
            try:
                phases = tool_call.arguments.get("phases", [])
                goal = tool_call.arguments.get("goal", "")
                if phases:
                    # Find the active project
                    deliverables = Path(self.config.workspace_dir) / "deliverables"
                    if deliverables.exists():
                        projects = sorted(
                            [d for d in deliverables.iterdir() if d.is_dir() and not d.name.startswith(".")],
                            key=lambda p: p.stat().st_mtime, reverse=True
                        )
                        for proj in projects[:1]:
                            todo_path = proj / "todo.md"
                            lines = [f"# {goal}\n"]
                            for phase in phases:
                                title = phase.get("title", "")
                                if title:
                                    lines.append(f"- [ ] {title}")
                            todo_path.write_text("\n".join(lines) + "\n")
                            log.info(f"Auto-generated todo.md with {len(phases)} items")
                            break
            except Exception as e:
                log.debug(f"Auto-todo skipped: {e}")

        # 8a1p. Plan-based auto-swell — when plan has 3+ components, dispatch eddies
        _plan_swelled = getattr(self, '_plan_swelled', False)
        if tool_call.name == "plan_update" and not result.is_error and not _plan_swelled:
            try:
                phases = tool_call.arguments.get("phases", [])
                # Extract component names from write phases
                component_phases = []
                for phase in phases:
                    title = str(phase.get("title", ""))
                    caps = phase.get("capabilities", [])
                    if "file_write" in caps and any(w in title.lower() for w in
                        ["write", "create", "component", "build", "implement"]):
                        component_phases.append(title)

                # If 3+ component phases AND a project with types.ts exists, auto-dispatch
                if len(component_phases) >= 3:
                    deliverables = Path(self.config.workspace_dir) / "deliverables"
                    if deliverables.exists():
                        projects = sorted(
                            [d for d in deliverables.iterdir() if d.is_dir() and not d.name.startswith(".")],
                            key=lambda p: p.stat().st_mtime, reverse=True
                        )
                        for proj in projects[:1]:
                            if proj.is_dir() and (proj / "package.json").exists():
                                self._plan_swelled = True
                                user_req = self.state.conversation[1].content if len(self.state.conversation) > 1 else ""

                                # Read types.ts for shared context
                                types_ctx = ""
                                types_path = proj / "src" / "types.ts"
                                if types_path.exists():
                                    types_ctx = f"\n\nShared types:\n```\n{types_path.read_text()[:1500]}\n```"

                                # Build eddy tasks from plan phases
                                tasks = []
                                targets = []
                                for phase_title in component_phases[:6]:  # max 6 eddies
                                    # Extract component name from phase title
                                    import re as _swell_re
                                    name_match = _swell_re.search(r'(\w+)(?:\.tsx|component|page|view)', phase_title, _swell_re.I)
                                    comp_name = name_match.group(1) if name_match else phase_title.split()[-1]
                                    comp_name = comp_name.replace(" ", "")

                                    target = str(proj / "src" / "components" / f"{comp_name}.tsx")
                                    prompt = (
                                        f"Write a React TypeScript component for: {phase_title}\n"
                                        f"Context: {user_req[:300]}\n"
                                        f"Export default function {comp_name}. Under 80 lines.{types_ctx}"
                                    )
                                    tasks.append(prompt)
                                    targets.append(target)

                                if tasks:
                                    log.info(f"Plan-swell: auto-dispatching {len(tasks)} eddies from plan")
                                    from .eddy import run_swarm
                                    swell_results = await run_swarm(
                                        tasks=tasks,
                                        workdir=str(proj),
                                        max_concurrent=4,
                                        system_prompt=(
                                            "You are a React TypeScript expert. "
                                            "Write a single component. Call done() with ONLY the raw TSX code. "
                                            "No markdown. Export default function ComponentName."
                                        ),
                                        write_targets=targets,
                                    )
                                    written = sum(1 for r in swell_results if r.success)
                                    names = [Path(t).stem for t in targets]
                                    log.info(f"Plan-swell: {written}/{len(tasks)} components written")
                                    self.state.add_system_note(
                                        f"AUTO-SWELL: {written}/{len(tasks)} components written in parallel: "
                                        f"{', '.join(names[:6])}. "
                                        f"Now write App.tsx to import and compose them, then compile."
                                    )
                                break
            except Exception as e:
                log.debug(f"Plan-swell skipped: {e}")

        # 8a1. Auto-swell — when App.tsx is written with imports to missing files, fire eddies
        if tool_call.name == "file_write" and not result.is_error:
            written_path = tool_call.arguments.get("path", "")
            if written_path.endswith("App.tsx") and "deliverables/" in written_path:
                try:
                    content = tool_call.arguments.get("content", "")
                    if not content:
                        content = Path(written_path).read_text() if Path(written_path).exists() else ""

                    # Find imports to ./components/ that don't exist yet
                    import re as _re3
                    imports = _re3.findall(r'from\s+["\']\.\/components\/(\w+)["\']', content)
                    project_dir = Path(written_path).parent.parent if "/src/" in written_path else Path(written_path).parent

                    missing = []
                    for comp in imports:
                        comp_path = project_dir / "src" / "components" / f"{comp}.tsx"
                        if not comp_path.exists():
                            missing.append(comp)

                    if len(missing) >= 2:
                        # Fire eddies for missing components
                        user_req = self.state.conversation[1].content if len(self.state.conversation) > 1 else ""

                        # Read types.ts if it exists for context
                        types_content = ""
                        types_path = project_dir / "src" / "types.ts"
                        if types_path.exists():
                            types_content = f"\n\nTypes:\n```\n{types_path.read_text()[:500]}\n```"

                        tasks = []
                        targets = []
                        for comp in missing:
                            target = str(project_dir / "src" / "components" / f"{comp}.tsx")
                            prompt = (
                                f"Write a React TypeScript component called {comp} for: {user_req[:200]}\n"
                                f"Export default function {comp}. Under 80 lines.{types_content}"
                            )
                            tasks.append(prompt)
                            targets.append(target)

                        log.info(f"Auto-swell: firing {len(tasks)} eddies for missing components: {missing}")
                        from .eddy import run_swarm
                        import asyncio
                        swell_results = await run_swarm(
                            tasks=tasks,
                            workdir=str(project_dir),
                            max_concurrent=4,
                            system_prompt="You are a React TypeScript expert. Call done() with ONLY the raw TSX code. No markdown fences.",
                            write_targets=targets,
                        )
                        written = sum(1 for r in swell_results if r.success)
                        log.info(f"Auto-swell: {written}/{len(tasks)} components written")
                        if written > 0:
                            self.state.add_system_note(
                                f"Auto-generated {written} components via eddies: {', '.join(missing[:5])}"
                            )
                except Exception as e:
                    log.debug(f"Auto-swell skipped: {e}")

        # 8a. Auto-serve — start dev server ONCE, Vite HMR handles the rest
        if tool_call.name in ("file_write", "file_edit", "shell_exec") and not result.is_error:
            written_path = tool_call.arguments.get("path", "") or tool_call.arguments.get("command", "")
            if "deliverables/" in written_path or "npm install" in written_path:
                serving_project = getattr(self, '_serving_project', None)
                try:
                    from .serve import serve_project
                    parts = written_path.split("deliverables/")
                    if len(parts) > 1:
                        project_name = parts[1].split("/")[0]
                    elif "npm install" in written_path:
                        # Extract project from cd command
                        import re as _re
                        cd_match = _re.search(r'cd\s+\S*deliverables/(\S+)', written_path)
                        project_name = cd_match.group(1) if cd_match else None
                    else:
                        project_name = None

                    if project_name and project_name != serving_project:
                        project_dir = str(Path(self.config.workspace_dir) / "deliverables" / project_name)
                        if Path(project_dir).exists():
                            url = serve_project(project_dir)
                            if url.startswith("http"):
                                self._serving_project = project_name
                                log.info(f"Auto-serve: {url} (HMR active)")
                except Exception as e:
                    log.debug(f"Auto-serve skipped: {e}")

        # 8b. Auto compile check — run vite build after writing .tsx/.ts
        if tool_call.name in ("file_write", "file_edit") and not result.is_error:
            written_path = tool_call.arguments.get("path", "")
            if "deliverables/" in written_path and written_path.endswith((".tsx", ".ts")):
                try:
                    import re as _re
                    parts = written_path.split("deliverables/")
                    if len(parts) > 1:
                        project_name = parts[1].split("/")[0]
                        project_dir = Path(self.config.workspace_dir) / "deliverables" / project_name
                        if (project_dir / "package.json").exists() and (project_dir / "node_modules").exists():
                            import subprocess
                            build = subprocess.run(
                                ["npx", "vite", "build"],
                                cwd=str(project_dir),
                                capture_output=True, text=True, timeout=30,
                            )
                            if build.returncode != 0:
                                errors = [l.strip() for l in build.stderr.splitlines() if "Error" in l][:3]
                                if errors:
                                    # Try deterministic fix first — don't bother the LLM
                                    from .error_fixer import try_auto_fix
                                    fixed = try_auto_fix(project_dir, errors)
                                    if fixed:
                                        # Rebuild after auto-fix
                                        build2 = subprocess.run(
                                            ["npx", "vite", "build"],
                                            cwd=str(project_dir),
                                            capture_output=True, text=True, timeout=30,
                                        )
                                        if build2.returncode == 0:
                                            log.info("Auto-compile: FIXED (deterministic recovery)")
                                        else:
                                            errors2 = [l.strip() for l in build2.stderr.splitlines() if "Error" in l][:3]
                                            self.state.add_system_note(
                                                f"COMPILE ERROR (auto-fix tried, still failing):\n" +
                                                "\n".join(f"  {e}" for e in errors2)
                                            )
                                    else:
                                        self.state.add_system_note(
                                            f"COMPILE ERROR:\n" + "\n".join(f"  {e}" for e in errors)
                                        )
                                        log.info(f"Auto-compile: FAIL ({len(errors)} errors)")
                            else:
                                log.info("Auto-compile: PASS")
                                # Quick runtime check — load in headless browser, catch JS errors
                                # Check any port the dev server might be on
                                serving = getattr(self, '_serving_project', None)
                                if serving or (project_dir / "node_modules" / ".vite").exists():
                                    try:
                                        import asyncio as _aio
                                        from playwright.async_api import async_playwright
                                        async with async_playwright() as pw:
                                            browser = await pw.chromium.launch(headless=True)
                                            page = await browser.new_page()
                                            js_errors = []
                                            page.on("pageerror", lambda e: js_errors.append(str(e)[:200]))
                                            await page.goto("http://localhost:9876", timeout=8000)
                                            await _aio.sleep(2)

                                            # Check for JS errors
                                            if js_errors:
                                                await browser.close()
                                                self.state.add_system_note(
                                                    f"RUNTIME ERROR (page loaded but JS crashed):\n" +
                                                    "\n".join(f"  {e}" for e in js_errors[:3])
                                                )
                                                log.info(f"Runtime check: {len(js_errors)} JS error(s)")
                                            else:
                                                # Blank page detection — check visible content
                                                text = await page.evaluate("document.body?.innerText?.trim() || ''")
                                                screenshot = await page.screenshot()
                                                await browser.close()

                                                is_blank = len(text) < 5
                                                # Also check pixels — mostly white/black = likely blank
                                                if is_blank:
                                                    try:
                                                        from PIL import Image
                                                        import io
                                                        img = Image.open(io.BytesIO(screenshot)).convert("RGB")
                                                        pixels = list(img.getdata())[::50]
                                                        near_white = sum(1 for r,g,b in pixels if r>240 and g>240 and b>240) / len(pixels)
                                                        near_black = sum(1 for r,g,b in pixels if r<20 and g<20 and b<20) / len(pixels)
                                                        is_blank = near_white > 0.9 or near_black > 0.95
                                                    except Exception:
                                                        pass

                                                if is_blank:
                                                    self.state.add_system_note(
                                                        "BLANK PAGE: Build compiled but the page is empty. "
                                                        "Check that App.tsx renders visible content, "
                                                        "all imports resolve correctly, and any external "
                                                        "packages are installed. The page shows nothing."
                                                    )
                                                    log.info("Runtime check: BLANK PAGE")
                                                else:
                                                    # Content verification — does visible text relate to the request?
                                                    user_req = self.state.conversation[1].content if len(self.state.conversation) > 1 else ""
                                                    if user_req and len(text) > 10:
                                                        # Extract key words from user request
                                                        import re as _cv_re
                                                        req_words = set(_cv_re.findall(r'[a-z]{4,}', user_req.lower()))
                                                        page_words = set(_cv_re.findall(r'[a-z]{4,}', text.lower()))
                                                        skip = {"build", "make", "create", "with", "that", "this", "from",
                                                                "should", "want", "need", "like", "using", "react", "component"}
                                                        req_words -= skip
                                                        overlap = req_words & page_words
                                                        if req_words and len(overlap) == 0 and len(text) < 100:
                                                            self.state.add_system_note(
                                                                f"CONTENT MISMATCH: Page renders but shows '{text[:80]}' "
                                                                f"which doesn't match the request. Expected keywords: "
                                                                f"{', '.join(sorted(list(req_words)[:5]))}."
                                                            )
                                                            log.info(f"Runtime check: CONTENT MISMATCH")
                                                        else:
                                                            log.info(f"Runtime check: PASS ({len(text)} chars, {len(overlap)} keyword matches)")
                                                    else:
                                                        log.info(f"Runtime check: PASS ({len(text)} chars visible)")

                                                # Screenshot diff — detect no-op edits
                                                try:
                                                    import hashlib
                                                    shot_hash = hashlib.md5(screenshot).hexdigest()
                                                    prev_hash = getattr(self, '_last_screenshot_hash', None)
                                                    self._last_screenshot_hash = shot_hash
                                                    if prev_hash and shot_hash == prev_hash:
                                                        self._noop_edits = getattr(self, '_noop_edits', 0) + 1
                                                        if self._noop_edits >= 2:
                                                            self.state.add_system_note(
                                                                "NO VISUAL CHANGE: Your last 2 edits didn't change "
                                                                "what the page looks like. The edit may not be taking "
                                                                "effect — check imports and component wiring."
                                                            )
                                                            self._noop_edits = 0
                                                    else:
                                                        self._noop_edits = 0
                                                except Exception:
                                                    pass
                                    except Exception as e:
                                        log.debug(f"Runtime check skipped: {e}")
                except Exception as e:
                    log.debug(f"Auto-compile skipped: {e}")

        # 8c. Auto-undertow — run QA immediately after writing HTML
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

        # 8sc. Scaffold awareness — remind agent what components are available
        if self.state.iteration > 0 and self.state.iteration % 10 == 0:
            try:
                deliverables = Path(self.config.workspace_dir) / "deliverables"
                if deliverables.exists():
                    projects = sorted(
                        [d for d in deliverables.iterdir() if d.is_dir() and not d.name.startswith(".")],
                        key=lambda p: p.stat().st_mtime, reverse=True
                    )
                    for proj in projects[:1]:
                        readme = proj / "README.md"
                        ui_dir = proj / "src" / "components" / "ui"
                        comp_dir = proj / "src" / "components"
                        if readme.exists() and ui_dir.exists():
                            # List available UI components
                            ui_components = [f.stem for f in ui_dir.iterdir()
                                           if f.suffix in ('.tsx', '.ts') and f.stem != 'index']
                            if ui_components:
                                self.state.add_system_note(
                                    f"AVAILABLE COMPONENTS (import from './components/ui'):\n"
                                    f"{', '.join(sorted(ui_components))}\n"
                                    f"Don't rewrite these — import them."
                                )
                                log.info(f"Scaffold awareness: {len(ui_components)} UI components available")
                        break
            except Exception:
                pass

        # 8tc. Auto-check todo.md items when files are written
        if tool_call.name in ("file_write", "file_edit") and not result.is_error:
            try:
                written_path = tool_call.arguments.get("path", "")
                parts = written_path.split("deliverables/")
                if len(parts) > 1:
                    project_name = parts[1].split("/")[0]
                    todo_path = Path(self.config.workspace_dir) / "deliverables" / project_name / "todo.md"
                    if todo_path.exists():
                        content = todo_path.read_text()
                        file_name = Path(written_path).stem
                        # Check off any todo item that mentions this file
                        updated = content.replace(f"- [ ] ", "- [ ] ") # normalize
                        for line in content.splitlines():
                            if "[ ]" in line and file_name.lower() in line.lower():
                                updated = updated.replace(line, line.replace("[ ]", "[x]"))
                        if updated != content:
                            todo_path.write_text(updated)
            except Exception:
                pass

        # 8sd. Scaffold duplicate detection — don't rewrite existing components
        if tool_call.name == "file_write" and not result.is_error:
            written_path = tool_call.arguments.get("path", "")
            if "components/" in written_path and written_path.endswith(".tsx"):
                comp_name = Path(written_path).stem
                scaffold_names = {
                    "Modal", "Toast", "Badge", "Tabs", "Accordion", "Alert",
                    "Avatar", "Dialog", "Dropdown", "Progress", "Select",
                    "Skeleton", "Switch", "Tooltip", "GlowCard", "Timeline",
                }
                if comp_name in scaffold_names:
                    # Check if it exists in ui/
                    try:
                        parts = written_path.split("deliverables/")
                        if len(parts) > 1:
                            project_name = parts[1].split("/")[0]
                            ui_path = Path(self.config.workspace_dir) / "deliverables" / project_name / "src" / "components" / "ui" / f"{comp_name}.tsx"
                            if ui_path.exists():
                                self.state.add_system_note(
                                    f"DUPLICATE: {comp_name} already exists at components/ui/{comp_name}.tsx. "
                                    f"Import it instead: import {{ {comp_name} }} from './components/ui'"
                                )
                    except Exception:
                        pass

        # 8w. Mid-loop auto-wire — if components exist but App.tsx is a stub, wire it NOW
        # Don't wait until exit — the dev server shows "Loading..." until App.tsx has imports
        if tool_call.name in ("file_write", "file_edit") and not result.is_error:
            written_path = tool_call.arguments.get("path", "")
            if "components/" in written_path and written_path.endswith(".tsx"):
                try:
                    # Find the project dir from the written path
                    import re as _re_wire
                    parts = written_path.split("deliverables/")
                    if len(parts) > 1:
                        project_name = parts[1].split("/")[0]
                        project_dir = Path(self.config.workspace_dir) / "deliverables" / project_name
                        app_path = project_dir / "src" / "App.tsx"
                        comp_dir = project_dir / "src" / "components"
                        if app_path.exists() and comp_dir.exists():
                            app_content = app_path.read_text()
                            is_stub = "TODO" in app_content or len(app_content) < 150
                            components = [
                                f.stem for f in comp_dir.iterdir()
                                if f.suffix in ('.tsx', '.ts') and f.stem not in ('index', 'types')
                                and not f.stem.startswith('.')
                            ]
                            # Auto-wire when 2+ components exist and App.tsx is still a stub
                            if is_stub and len(components) >= 2:
                                imports = "\n".join(f'import {c} from "./components/{c}"' for c in sorted(components))
                                jsx = "\n        ".join(f'<{c} />' for c in sorted(components))
                                auto_app = (
                                    f'import "./index.css"\n{imports}\n\n'
                                    f'export default function App() {{\n'
                                    f'  return (\n'
                                    f'    <div className="container">\n'
                                    f'      {jsx}\n'
                                    f'    </div>\n'
                                    f'  )\n'
                                    f'}}\n'
                                )
                                app_path.write_text(auto_app)
                                log.info(f"Mid-loop auto-wire: {project_name}/App.tsx with {len(components)} components")
                                self.state.add_system_note(
                                    f"Auto-wired App.tsx with {len(components)} components: {', '.join(sorted(components))}. "
                                    f"Dev server now shows your work. Iterate on the components."
                                )
                except Exception as e:
                    log.debug(f"Mid-loop auto-wire skipped: {e}")

        # 8z. Generate nudge — visual projects should use SD-Turbo for assets
        if self.state.iteration > 0 and self.state.iteration % 12 == 0:
            has_generated = any(
                t == "generate_image" or t == "webdev_generate_assets"
                for t in self._tool_history
            )
            has_deliverable = any(
                "deliverables/" in m.content
                for m in self.state.conversation if m.role == "tool_result"
            )
            if has_deliverable and not has_generated:
                # Check if this looks like a visual project
                user_req = self.state.conversation[1].content if len(self.state.conversation) > 1 else ""
                visual_keywords = ["game", "ui", "design", "calculator", "gameboy", "interface",
                                   "dashboard", "visual", "replica", "clone", "app", "pixel"]
                if any(k in user_req.lower() for k in visual_keywords):
                    self.state.add_system_note(
                        "GENERATE REMINDER: Use generate_image to create textures, icons, "
                        "backgrounds, and visual assets. SD-Turbo generates in <1 second. "
                        "Don't use placeholder SVGs when you can generate real images."
                    )

        # 8. Error tracking
        if result.is_error:
            self.state.record_error(tool_call.name, tool_call.arguments, result.content)
            if self.state.should_escalate(tool_call.name, tool_call.arguments):
                self.state.add_system_note(
                    "3 failures on same approach. You must try a fundamentally different "
                    "approach or use message_ask to request guidance from the user."
                )

        # 8d. Stub detection — catch App.tsx not wired
        if tool_call.name == "message_result" and getattr(self, '_delivery_attempts', 0) <= 2:
            # Find the project dir from recent writes
            for msg in reversed(self.state.conversation[-20:]):
                if msg.role == "tool_result" and "deliverables/" in msg.content:
                    import re as _re2
                    match = _re2.search(r'deliverables/([^/\s]+)', msg.content)
                    if match:
                        app_path = Path(self.config.workspace_dir) / "deliverables" / match.group(1) / "src" / "App.tsx"
                        comp_dir = Path(self.config.workspace_dir) / "deliverables" / match.group(1) / "src" / "components"
                        if app_path.exists() and comp_dir.exists():
                            app_content = app_path.read_text()
                            has_components = any(comp_dir.iterdir())
                            is_stub = "TODO" in app_content or "not built yet" in app_content or (len(app_content) < 200 and "import" not in app_content.lower())
                            if is_stub and has_components:
                                # Auto-wire: generate App.tsx from discovered components
                                components = [
                                    f.stem for f in comp_dir.iterdir()
                                    if f.suffix in ('.tsx', '.ts') and f.stem not in ('index', 'types')
                                ]
                                if components:
                                    imports = "\n".join(
                                        f'import {c} from "./components/{c}"'
                                        for c in sorted(components)
                                    )
                                    jsx = "\n        ".join(f'<{c} />' for c in sorted(components))
                                    auto_app = (
                                        f'import "./index.css"\n{imports}\n\n'
                                        f'export default function App() {{\n'
                                        f'  return (\n'
                                        f'    <div className="container">\n'
                                        f'      <h1>App</h1>\n'
                                        f'      {jsx}\n'
                                        f'    </div>\n'
                                        f'  )\n'
                                        f'}}\n'
                                    )
                                    app_path.write_text(auto_app)
                                    log.info(f"Auto-wired App.tsx with {len(components)} components: {components}")
                    break

        # 9. Tension gate — measure current before allowing delivery
        if tool_call.name == "message_result":
            from .current import measure_heuristic, UNCERTAIN, DRIFTING
            from .circulation import Circulation

            tension = measure_heuristic(result.content)
            self._pressure.record(tension, tool_call.name)

            # Track delivery attempts — prevent infinite block loops
            self._delivery_attempts = getattr(self, '_delivery_attempts', 0) + 1

            # Short conversational responses (greetings, acknowledgments) skip all gates
            is_conversational = len(result.content) < 300 and tension < 0.3
            if is_conversational:
                self._delivery_attempts = 0
                self.state.task_complete = True
                return result.content

            # Only block factual claims that need verification, not build deliveries
            can_block = self._delivery_attempts <= 3

            # Detect task type for adaptive thresholds
            user_req = self.state.conversation[1].content if len(self.state.conversation) > 1 else ""
            build_keywords = ["build", "create", "make", "app", "game", "dashboard", "website"]
            task_type = "build" if any(k in user_req.lower() for k in build_keywords) else "general"
            circ = Circulation(task_type=task_type)
            route = circ.route(
                user_req,
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
                if len(result.content) > 200:
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

            # 10a. Swell compile gate — vite build must pass for React deliveries
            if self._delivery_attempts <= 5:
                try:
                    deliverables = Path(self.config.workspace_dir) / "deliverables"
                    if deliverables.exists():
                        # Find the most recently modified project
                        projects = sorted(
                            [d for d in deliverables.iterdir() if d.is_dir() and not d.name.startswith(".")],
                            key=lambda p: p.stat().st_mtime, reverse=True
                        )
                        for proj in projects[:1]:
                            if (proj / "package.json").exists() and (proj / "node_modules").exists():
                                import subprocess
                                build = subprocess.run(
                                    ["npx", "vite", "build"],
                                    cwd=str(proj), capture_output=True, text=True, timeout=30,
                                )
                                if build.returncode != 0:
                                    errors = [l.strip() for l in build.stderr.splitlines() if "Error" in l][:3]
                                    if errors:
                                        error_list = "\n".join(f"  - {e}" for e in errors)
                                        log.info(f"Swell compile gate: FAIL — {len(errors)} errors in {proj.name}")
                                        self.state.add_system_note(
                                            f"SWELL COMPILE CHECK FAILED for {proj.name}:\n{error_list}\n"
                                            f"Fix these build errors before delivering."
                                        )
                                        return result.content
                                    else:
                                        log.info(f"Swell compile gate: FAIL (no parsed errors) in {proj.name}")
                                else:
                                    log.info(f"Swell compile gate: PASS — {proj.name}")
                except Exception as e:
                    log.debug(f"Swell compile gate skipped: {e}")

            # 10a2. Runtime health gate at delivery — check page actually renders
            if self._delivery_attempts <= 2:
                serving = getattr(self, '_serving_project', None)
                if serving:
                    try:
                        from playwright.async_api import async_playwright
                        async with async_playwright() as pw:
                            browser = await pw.chromium.launch(headless=True)
                            page = await browser.new_page()
                            js_errors = []
                            page.on("pageerror", lambda e: js_errors.append(str(e)[:150]))
                            await page.goto("http://localhost:9876", timeout=6000)
                            await asyncio.sleep(1)
                            text = await page.evaluate("document.body?.innerText?.trim() || ''")
                            await browser.close()
                            if js_errors:
                                self.state.add_system_note(
                                    f"DELIVERY BLOCKED — runtime JS errors:\n" +
                                    "\n".join(f"  {e}" for e in js_errors[:2]) +
                                    "\nFix these before delivering."
                                )
                                log.info(f"Delivery runtime gate: FAIL ({len(js_errors)} errors)")
                                return result.content
                            if len(text) < 5:
                                self.state.add_system_note(
                                    "DELIVERY BLOCKED — page is blank. Fix App.tsx rendering."
                                )
                                log.info("Delivery runtime gate: BLANK")
                                return result.content
                            log.info(f"Delivery runtime gate: PASS ({len(text)} chars)")
                    except Exception as e:
                        log.debug(f"Delivery runtime gate skipped: {e}")

            # 10b. Code tension — undertow QA gate for file deliveries
            # For React projects with a dev server, skip static HTML testing
            # (dist/index.html is an empty shell — the compile gate above is sufficient)
            serving = getattr(self, '_serving_project', None)

            # Find the last HTML file written in this session (non-React projects only)
            last_html = None
            if not serving:
                for msg in reversed(self.state.conversation):
                    if msg.role == "tool_result" and ".html" in msg.content:
                        import re as _re
                        paths = _re.findall(r'(/[^\s"\']+\.html)', msg.content)
                        if paths:
                            last_html = paths[0]
                            break

            if last_html and self._delivery_attempts <= 5:
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

            # Learn from this build — extract patterns for future sessions
            try:
                deliverables = Path(self.config.workspace_dir) / "deliverables"
                if deliverables.exists():
                    projects = sorted(
                        [d for d in deliverables.iterdir() if d.is_dir() and not d.name.startswith(".")],
                        key=lambda p: p.stat().st_mtime, reverse=True
                    )
                    if projects:
                        self.observer.learn_from_build(
                            str(projects[0]), self.state.iteration, True, self._tool_history
                        )
            except Exception:
                pass

            # Project history — record what prompt built this project
            try:
                deliverables = Path(self.config.workspace_dir) / "deliverables"
                if deliverables.exists():
                    projects = sorted(
                        [d for d in deliverables.iterdir() if d.is_dir() and not d.name.startswith(".")],
                        key=lambda p: p.stat().st_mtime, reverse=True
                    )
                    for proj in projects[:1]:
                        history_path = proj / ".history.md"
                        user_req = self.state.conversation[1].content if len(self.state.conversation) > 1 else ""
                        import datetime
                        entry = f"- {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} | {self.state.iteration} iters | {user_req[:100]}\n"
                        existing = history_path.read_text() if history_path.exists() else "# Build History\n"
                        history_path.write_text(existing + entry)
                        break
            except Exception:
                pass

            return result.content

        return result.content


def _truncate(d: dict, max_len: int = 200) -> str:
    s = json.dumps(d)
    return s[:max_len] + "..." if len(s) > max_len else s
