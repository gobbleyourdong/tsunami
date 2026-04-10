"""Session persistence — save and restore agent state.

Memory is external. The file system is long-term memory.
Sessions are saved as JSONL in .history/ — one line per message.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from .state import AgentState, Message, Plan


def save_session(state: AgentState, session_dir: Path, session_id: str = "latest"):
    """Save the full conversation to a JSONL file."""
    session_dir.mkdir(parents=True, exist_ok=True)
    path = session_dir / f"{session_id}.jsonl"

    with open(path, "w") as f:
        # Header with metadata
        meta = {
            "_meta": True,
            "iteration": state.iteration,
            "task_complete": state.task_complete,
            "error_counts": state.error_counts,
            "plan": state.plan.to_dict() if state.plan else None,
            "timestamp": time.time(),
        }
        f.write(json.dumps(meta) + "\n")

        # Messages
        for m in state.conversation:
            record = {
                "role": m.role,
                "content": m.content,
                "tool_call": m.tool_call,
                "timestamp": m.timestamp,
            }
            f.write(json.dumps(record) + "\n")

    return path


def load_session(session_dir: Path, session_id: str = "latest") -> AgentState | None:
    """Load a conversation from a JSONL file."""
    path = session_dir / f"{session_id}.jsonl"
    if not path.exists():
        return None

    state = AgentState()
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)

            if record.get("_meta"):
                state.iteration = record.get("iteration", 0)
                state.task_complete = record.get("task_complete", False)
                state.error_counts = record.get("error_counts", {})
                plan_data = record.get("plan")
                if plan_data:
                    state.plan = Plan.from_dict(plan_data)
                continue

            state.conversation.append(Message(
                role=record["role"],
                content=record["content"],
                tool_call=record.get("tool_call"),
                timestamp=record.get("timestamp", 0),
            ))

    return state


def save_session_summary(state: AgentState, session_dir: Path, session_id: str = "latest"):
    """Save a human-readable session summary for injection into next session.

    ECC pattern: structured Markdown with tasks, files modified, tools used.
    Gets auto-injected at next session start.
    """
    session_dir.mkdir(parents=True, exist_ok=True)
    summary_path = session_dir / "last_session.md"

    # Extract key info from conversation
    task = ""
    tools_used = []
    files_written = []
    errors = []

    for m in state.conversation:
        if m.role == "user" and not task:
            task = m.content[:300]
        if m.tool_call:
            tc = m.tool_call.get("function", m.tool_call)
            name = tc.get("name", "")
            tools_used.append(name)
            args = tc.get("arguments", {})
            if isinstance(args, dict) and name in ("file_write", "file_edit", "file_append"):
                path = args.get("path", "")
                if path:
                    files_written.append(path)
        if m.role == "tool_result" and "ERROR" in m.content:
            errors.append(m.content[:150])

    from datetime import datetime
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    complete = "Yes" if state.task_complete else f"No (stopped at iteration {state.iteration})"

    summary = f"""# Previous Session Summary
**Date:** {now}
**Task:** {task}
**Completed:** {complete}
**Iterations:** {state.iteration}
**Tools used:** {', '.join(dict.fromkeys(tools_used))}
"""
    if files_written:
        summary += f"**Files modified:** {', '.join(files_written[-15:])}\n"
    if errors:
        summary += f"**Errors ({len(errors)}):** {errors[-1]}\n"
    if state.plan:
        summary += f"**Plan:** {state.plan.goal}\n"

    # Extract what worked — successful patterns from this session
    successful_patterns = []
    failed_patterns = []
    for i, m in enumerate(state.conversation):
        if m.role == "tool_result":
            prev = state.conversation[i-1] if i > 0 else None
            if prev and prev.tool_call:
                tc = prev.tool_call.get("function", prev.tool_call)
                tool = tc.get("name", "")
                if "ERROR" in m.content or "FAIL" in m.content:
                    failed_patterns.append(tool)
                elif tool in ("file_write", "file_edit") and "Wrote" in m.content:
                    successful_patterns.append(tool)

    if successful_patterns:
        summary += f"**What worked:** {len(successful_patterns)} successful writes\n"
    if failed_patterns:
        fail_counts = {}
        for t in failed_patterns:
            fail_counts[t] = fail_counts.get(t, 0) + 1
        summary += f"**What failed:** {', '.join(f'{t}({c}x)' for t,c in fail_counts.items())}\n"

    summary += "\n**Advice for next session:** "
    if errors:
        summary += "Check imports carefully — errors occurred last time. "
    if state.task_complete:
        summary += "Last build succeeded. Build on it or start fresh."
    else:
        summary += "Last build didn't complete. Consider a simpler approach."
    summary += "\n"

    summary_path.write_text(summary)
    return summary_path


def load_last_session_summary(session_dir: Path) -> str:
    """Load the last session summary for injection into system prompt."""
    summary_path = session_dir / "last_session.md"
    if summary_path.exists():
        # Only inject if less than 7 days old
        age_days = (time.time() - summary_path.stat().st_mtime) / 86400
        if age_days < 7:
            return summary_path.read_text()
    return ""


def list_sessions(session_dir: Path) -> list[dict]:
    """List all saved sessions with metadata."""
    sessions = []
    if not session_dir.exists():
        return sessions

    for path in sorted(session_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            with open(path) as f:
                first_line = f.readline()
                meta = json.loads(first_line)
                if meta.get("_meta"):
                    sessions.append({
                        "id": path.stem,
                        "path": str(path),
                        "iteration": meta.get("iteration", 0),
                        "complete": meta.get("task_complete", False),
                        "timestamp": meta.get("timestamp", 0),
                    })
        except (json.JSONDecodeError, KeyError):
            continue

    return sessions
