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

        # Session log — structured turn-by-turn record for offline mining
        # (extract_failures.py -> DPO pairs). Written append-only as JSONL.
        # One file per process start; file name encodes timestamp + pid.
        import os as _os, time as _time
        _sessions = self.workspace / "sessions"
        _sessions.mkdir(parents=True, exist_ok=True)
        self.session_log_path = _sessions / f"{int(_time.time())}_{_os.getpid()}.jsonl"

    def _log_turn(self, record: dict) -> None:
        """Append a turn record to the session log. Best-effort (never raises)."""
        try:
            import time as _time
            record = {"ts": _time.time(), **record}
            with open(self.session_log_path, "a") as _f:
                _f.write(json.dumps(record, default=str) + "\n")
        except Exception:
            pass  # logging must never break the agent loop

    def add_system(self, content: str):
        self.conversation.append(Message(role="system", content=content))
        self._log_turn({"role": "system", "content": content})

    def add_user(self, content: str):
        self.conversation.append(Message(role="user", content=content))
        self._log_turn({"role": "user", "content": content})

    def add_assistant(self, content: str, tool_call: dict | None = None):
        self.conversation.append(Message(role="assistant", content=content, tool_call=tool_call))
        self._log_turn({"role": "assistant", "content": content, "tool_call": tool_call})

    def add_tool_result(self, tool_name: str, args: dict, result: str, is_error: bool = False):
        prefix = f"[{tool_name}] "
        if is_error:
            prefix += "ERROR: "
        self.conversation.append(Message(role="tool_result", content=prefix + result))
        self._log_turn({"role": "tool_result", "name": tool_name, "args": args,
                        "content": result, "is_error": is_error})

    def add_system_note(self, note: str):
        # Audit Fire 1 / D2: stored internally as role="system_note" so
        # log entries stay distinct from user input, but serialised to
        # the wire as role="user" with the body wrapped in a
        # <system-reminder> XML tag (qwen-code convention). The prior
        # role="system" storage was silently dropped after iter 1 by
        # to_messages()'s first-system-only gate, making all 60+
        # add_system_note call sites in agent.py into no-ops on re-entry.
        self.conversation.append(Message(role="system_note", content=note))
        self._log_turn({"role": "system_note", "content": note})

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

    def to_messages(self, max_pairs: int | None = None) -> list[dict[str, str]]:
        """Convert conversation to the format expected by LLM APIs.

        Uses a simple, universally compatible format: tool calls and results
        are inlined as text in assistant/user messages.

        When `max_pairs` is set (scaffold-edit mode), only the last N
        (assistant tool_call, tool_result) pairs are kept verbatim; older
        pairs collapse into a single summary line. The model doesn't need
        the full history of file_writes — the scaffold state is on disk,
        recoverable via file_read. This keeps per-turn prompt size flat
        instead of growing linearly with iteration count.
        """
        source = self.conversation
        if max_pairs is not None and max_pairs >= 0:
            source = self._compact_conversation(max_pairs)

        msgs = []
        first_system_done = False
        for m in source:
            if m.role == "system":
                if not first_system_done:
                    msgs.append({"role": "system", "content": m.content})
                    first_system_done = True
                else:
                    # Drop mid-conversation genuine system messages — they
                    # cause Qwen3.5 Jinja "system must be first" template
                    # errors. Agent-injected reminders route through
                    # role="system_note" (below) which wraps in user
                    # <system-reminder> and doesn't hit this drop.
                    pass
                continue
            if m.role == "system_note":
                # qwen-code convention: per-turn reminders go inside a user
                # message wrapped in <system-reminder>...</system-reminder>.
                # Survives into context because user messages are never
                # dropped, unlike mid-conversation system roles.
                msgs.append({
                    "role": "user",
                    "content": f"<system-reminder>{m.content}</system-reminder>",
                })
                continue
            if m.role == "tool_result":
                msgs.append({"role": "user", "content": m.content})
            elif m.role == "assistant" and m.tool_call:
                # Echo the tool call JSON so the model sees its own pattern.
                # For file_write / file_append / file_edit with large
                # `content` bodies (App.tsx is ~12KB, ~3000 tokens) the
                # full body in history ballooned iter N+1's prefill. The
                # content is already on disk — echo a compact summary of
                # the write instead of replaying the full code.
                import json
                tc = m.tool_call.get("function", m.tool_call)
                name = tc.get("name", "")
                args = dict(tc.get("arguments", {}) or {})
                if name in ("file_write", "file_append"):
                    content = args.get("content", "")
                    if isinstance(content, str) and len(content) > 400:
                        args["content"] = f"<{len(content)} chars — see {args.get('path', '?')} on disk>"
                elif name == "file_edit":
                    for k in ("old_content", "new_content", "content"):
                        v = args.get(k, "")
                        if isinstance(v, str) and len(v) > 400:
                            args[k] = f"<{len(v)} chars — elided>"
                tc_json = json.dumps({"name": name, "arguments": args})
                msgs.append({"role": "assistant", "content": tc_json})
            else:
                msgs.append({"role": m.role, "content": m.content})

        # Enforce strict user/assistant alternation — merge consecutive same-role
        merged = []
        for msg in msgs:
            if merged and msg["role"] == merged[-1]["role"] and msg["role"] != "system":
                merged[-1]["content"] += "\n" + msg["content"]
            else:
                merged.append(msg)

        # Manus technique: append current plan at END of context
        # Recency bias means the model pays more attention to recent tokens.
        # Putting the plan at the tail (not in system prompt) keeps it salient.
        if self.plan:
            plan_reminder = f"[CURRENT PLAN]\n{self.plan.summary()}\n\nYou MUST call exactly one tool. Save findings to files constantly."
            # Append as user message so it's at the tail of context
            if merged and merged[-1]["role"] == "user":
                merged[-1]["content"] += "\n\n" + plan_reminder
            else:
                merged.append({"role": "user", "content": plan_reminder})

        return merged

    def _compact_conversation(self, max_pairs: int) -> list[Message]:
        """Keep system + first user message + last `max_pairs` (assistant,
        tool_result) pairs verbatim; collapse everything between into a
        single summary system_note. Scaffold state lives on disk — the
        model re-reads via file_read when it needs detail, so older
        tool-call bodies are dead weight in the prompt.
        """
        if not self.conversation:
            return self.conversation

        action_idxs = [i for i, m in enumerate(self.conversation)
                       if m.role in ("assistant", "tool_result")]
        if len(action_idxs) <= max_pairs * 2:
            return self.conversation  # short enough, no compaction needed

        keep_from = action_idxs[-(max_pairs * 2)]

        head: list[Message] = []
        first_user_seen = False
        for m in self.conversation[:keep_from]:
            if m.role == "system":
                head.append(m)
            elif m.role == "user" and not first_user_seen:
                head.append(m)
                first_user_seen = True

        dropped = [m for m in self.conversation[:keep_from]
                   if m.role in ("assistant", "tool_result")]
        summary_lines = []
        pair_counter = 0
        for m in dropped:
            if m.role == "assistant" and m.tool_call:
                tc = m.tool_call.get("function", m.tool_call)
                name = tc.get("name", "?")
                pair_counter += 1
                summary_lines.append(f"  {pair_counter}. {name}")
            elif m.role == "tool_result":
                if summary_lines:
                    snippet = m.content.split("\n", 1)[0][:80]
                    summary_lines[-1] += f" → {snippet}"
        if summary_lines:
            summary = ("[Prior iterations — scaffold state is on disk, file_read to inspect]\n"
                       + "\n".join(summary_lines))
            head.append(Message(role="system_note", content=summary))

        return head + list(self.conversation[keep_from:])
