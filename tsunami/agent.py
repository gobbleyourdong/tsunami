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

from .compression import compress_context, needs_compression
from .config import TsunamiConfig
from .model import LLMModel, ToolCall, create_model
from .prompt import build_system_prompt
from .session import save_session
from .state import AgentState
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
        self.registry: ToolRegistry = build_registry(config, profile=config.tool_profile)

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

        # Stall detection
        self._empty_steps = 0

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
        self.state.add_system(system_prompt)
        self.state.add_user(user_message)

        log.info(f"Starting agent loop: {user_message[:100]}")
        consecutive_errors = 0

        while self.state.iteration < self.config.max_iterations:
            self.state.iteration += 1
            iter_start = time.time()

            # Context compression check — every 10 iterations
            if self.state.iteration % 10 == 0 and needs_compression(self.state):
                log.info("Context growing large — compressing...")
                await compress_context(self.state, self.model)

            try:
                result = await self._step()
                consecutive_errors = 0  # reset on success
            except Exception as e:
                consecutive_errors += 1
                log.error(f"Agent loop error at iteration {self.state.iteration}: {e}")
                self.state.add_system_note(f"Loop error: {e}")
                save_session(self.state, self.session_dir, self.session_id)
                if consecutive_errors >= 3:
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
                return result

        # Save on max iterations
        save_session(self.state, self.session_dir, self.session_id)
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

        # 3. Extract the tool call
        tool_call = response.tool_call

        if tool_call is None:
            # Model responded with text only — wrap in message_info
            # (enforcing the "always use tools" rule)
            if response.content:
                self.state.add_assistant(response.content)
                tool_call = ToolCall(name="message_info", arguments={"text": response.content})
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

        # Detect repetition loop: if model keeps calling message_info
        # it's stuck — force message_result
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

        # 4. Watcher check (if enabled and interval hit, with recursion guard)
        if (self.watcher
                and self.watcher.should_activate(self.state.iteration)
                and _watcher_depth < MAX_WATCHER_REVISIONS):
            review = await self.watcher.review(
                self.state, tool_call.name, tool_call.arguments
            )
            if review.should_revise:
                log.info(f"Watcher: REVISE (depth {_watcher_depth}) — {review.suggestion}")
                self.state.add_system_note(
                    f"Watcher suggests revision: {review.suggestion}"
                )
                return await self._step(_watcher_depth=_watcher_depth + 1)

        # 5. Record the assistant's response
        self.state.add_assistant(
            response.content,
            tool_call={
                "function": {"name": tool_call.name, "arguments": tool_call.arguments},
            },
        )

        # 6. Execute the tool — with argument safety
        tool = self.registry.get(tool_call.name)
        if tool is None:
            error_msg = f"Unknown tool: {tool_call.name}. Available: {self.registry.names()}"
            self.state.add_tool_result(tool_call.name, tool_call.arguments, error_msg, is_error=True)
            return error_msg

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

        # 7. Observe — record the result
        self.state.add_tool_result(
            tool_call.name, tool_call.arguments, result.content, is_error=result.is_error
        )

        # 8. Error tracking
        if result.is_error:
            self.state.record_error(tool_call.name, tool_call.arguments, result.content)
            if self.state.should_escalate(tool_call.name, tool_call.arguments):
                self.state.add_system_note(
                    "3 failures on same approach. You must try a fundamentally different "
                    "approach or use message_ask to request guidance from the user."
                )

        # 9. Check termination
        if tool_call.name == "message_result":
            self.state.task_complete = True
            return result.content

        return result.content


def _truncate(d: dict, max_len: int = 200) -> str:
    s = json.dumps(d)
    return s[:max_len] + "..." if len(s) > max_len else s
