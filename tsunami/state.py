"""Agent state — conversation history, plan, error tracking."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Phase:
    id: int
    title: str
    status: str = "pending"  # pending, active, complete
    capabilities: list[str] = field(default_factory=list)


@dataclass
class Plan:
    goal: str
    phases: list[Phase] = field(default_factory=list)
    current_phase: int = 0

    def active_phase(self) -> Phase | None:
        for p in self.phases:
            if p.status == "active":
                return p
        return None

    def advance(self) -> Phase | None:
        for p in self.phases:
            if p.status == "active":
                p.status = "complete"
            elif p.status == "pending":
                p.status = "active"
                self.current_phase = p.id
                return p
        return None

    def to_dict(self) -> dict:
        return {
            "goal": self.goal,
            "current_phase": self.current_phase,
            "phases": [
                {"id": p.id, "title": p.title, "status": p.status, "capabilities": p.capabilities}
                for p in self.phases
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> Plan:
        phases = [Phase(**p) for p in data.get("phases", [])]
        return cls(goal=data["goal"], phases=phases, current_phase=data.get("current_phase", 0))

    def summary(self) -> str:
        lines = [f"Goal: {self.goal}"]
        for p in self.phases:
            marker = {"pending": "[ ]", "active": "[>]", "complete": "[x]"}[p.status]
            lines.append(f"  {marker} Phase {p.id}: {p.title}")
        return "\n".join(lines)


@dataclass
class Message:
    role: str  # system, user, assistant, tool_result
    content: str
    tool_call: dict[str, Any] | None = None
    timestamp: float = field(default_factory=time.time)


class AgentState:
    def __init__(self, workspace_dir: str | Path = "./workspace"):
        self.workspace = Path(workspace_dir)
        self.conversation: list[Message] = []
        self.plan: Plan | None = None
        self.error_counts: dict[str, int] = {}  # approach_key -> failure count
        self.iteration: int = 0
        self.task_complete: bool = False

    def add_system(self, content: str):
        self.conversation.append(Message(role="system", content=content))

    def add_user(self, content: str):
        self.conversation.append(Message(role="user", content=content))

    def add_assistant(self, content: str, tool_call: dict | None = None):
        self.conversation.append(Message(role="assistant", content=content, tool_call=tool_call))

    def add_tool_result(self, tool_name: str, args: dict, result: str, is_error: bool = False):
        prefix = f"[{tool_name}] "
        if is_error:
            prefix += "ERROR: "
        self.conversation.append(Message(role="tool_result", content=prefix + result))

    def add_system_note(self, note: str):
        self.conversation.append(Message(role="system", content=f"[WATCHER] {note}"))

    def record_error(self, tool_name: str, args: dict, error: str):
        key = f"{tool_name}:{json.dumps(args, sort_keys=True)[:200]}"
        self.error_counts[key] = self.error_counts.get(key, 0) + 1

    def should_escalate(self, tool_name: str, args: dict | None = None) -> bool:
        if args:
            key = f"{tool_name}:{json.dumps(args, sort_keys=True)[:200]}"
            return self.error_counts.get(key, 0) >= 3
        return any(v >= 3 for k, v in self.error_counts.items() if k.startswith(tool_name))

    def save_plan(self, plans_dir: Path):
        if self.plan:
            plans_dir.mkdir(parents=True, exist_ok=True)
            path = plans_dir / "current_plan.json"
            with open(path, "w") as f:
                json.dump(self.plan.to_dict(), f, indent=2)

    def load_plan(self, plans_dir: Path) -> Plan | None:
        path = plans_dir / "current_plan.json"
        if path.exists():
            with open(path) as f:
                self.plan = Plan.from_dict(json.load(f))
        return self.plan

    def to_messages(self) -> list[dict[str, str]]:
        """Convert conversation to the format expected by LLM APIs.

        Uses a simple, universally compatible format: tool calls and results
        are inlined as text in assistant/user messages. This avoids the
        strict OpenAI tool_call format that breaks across backends
        (llama-server, Ollama, vLLM all parse it differently).

        The model sees the full history of what it did and what happened.
        """
        msgs = []
        first_system_done = False
        for m in self.conversation:
            if m.role == "system":
                if not first_system_done:
                    msgs.append({"role": "system", "content": m.content})
                    first_system_done = True
                else:
                    # Drop mid-conversation system notes entirely — they cause
                    # Qwen3.5 Jinja "system must be first" template errors.
                    # The info is not critical enough to risk crashing the call.
                    pass
                continue
            if m.role == "tool_result":
                msgs.append({"role": "user", "content": m.content})
            elif m.role == "assistant" and m.tool_call:
                # Minimal assistant response — just "ok" to acknowledge
                # Any descriptive text here gets mimicked by the model on next turn
                msgs.append({"role": "assistant", "content": "ok"})
            else:
                msgs.append({"role": m.role, "content": m.content})

        # Enforce strict user/assistant alternation — merge consecutive same-role
        merged = []
        for msg in msgs:
            if merged and msg["role"] == merged[-1]["role"] and msg["role"] != "system":
                merged[-1]["content"] += "\n" + msg["content"]
            else:
                merged.append(msg)

        return merged
