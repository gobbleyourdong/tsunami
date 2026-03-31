"""Conversation forking — save/restore conversation snapshots.

Creates a copy of the current conversation that can be resumed later,
allowing the agent to explore different approaches without losing progress.

Forks are saved as JSON files in workspace/.forks/.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from .state import AgentState, Message

log = logging.getLogger("tsunami.fork")


def derive_title(state: AgentState, max_len: int = 100) -> str:
    """Derive a fork title from the first user message.

    From deriveFirstPrompt: extract text, collapse whitespace,
    truncate to max_len.
    """
    for m in state.conversation:
        if m.role == "user":
            title = " ".join(m.content.split()).strip()
            if len(title) > max_len:
                title = title[:max_len]
            return title or "Branched conversation"
    return "Branched conversation"


def create_fork(
    state: AgentState,
    workspace_dir: str,
    fork_name: str | None = None,
) -> str:
    """Create a fork (snapshot) of the current conversation.

    Copies all messages with metadata. Returns the fork ID.
    """
    forks_dir = Path(workspace_dir) / ".forks"
    forks_dir.mkdir(parents=True, exist_ok=True)

    fork_id = f"fork_{int(time.time() * 1000)}"
    title = fork_name or derive_title(state)

    # Ensure unique name
    title = _unique_fork_name(forks_dir, title)

    # Serialize conversation
    messages = []
    for m in state.conversation:
        messages.append({
            "role": m.role,
            "content": m.content,
            "tool_call": m.tool_call,
            "timestamp": m.timestamp,
        })

    fork_data = {
        "fork_id": fork_id,
        "title": title,
        "created_at": time.time(),
        "iteration": state.iteration,
        "task_complete": state.task_complete,
        "error_counts": state.error_counts,
        "plan": state.plan.to_dict() if state.plan else None,
        "messages": messages,
    }

    fork_file = forks_dir / f"{fork_id}.json"
    fork_file.write_text(json.dumps(fork_data, indent=2))

    log.info(f"Created fork: {fork_id} ({title}) — {len(messages)} messages")
    return fork_id


def restore_fork(
    fork_id: str,
    workspace_dir: str,
) -> AgentState | None:
    """Restore a conversation from a fork.

    Returns a new AgentState with the forked conversation, or None if not found.
    """
    from .state import Plan

    fork_file = Path(workspace_dir) / ".forks" / f"{fork_id}.json"
    if not fork_file.exists():
        return None

    data = json.loads(fork_file.read_text())

    state = AgentState(workspace_dir=workspace_dir)
    state.iteration = data.get("iteration", 0)
    state.task_complete = data.get("task_complete", False)
    state.error_counts = data.get("error_counts", {})

    if data.get("plan"):
        state.plan = Plan.from_dict(data["plan"])

    for m in data["messages"]:
        state.conversation.append(Message(
            role=m["role"],
            content=m["content"],
            tool_call=m.get("tool_call"),
            timestamp=m.get("timestamp", 0),
        ))

    log.info(f"Restored fork: {fork_id} — {len(state.conversation)} messages")
    return state


def list_forks(workspace_dir: str) -> list[dict]:
    """List all available forks."""
    forks_dir = Path(workspace_dir) / ".forks"
    if not forks_dir.exists():
        return []

    forks = []
    for f in sorted(forks_dir.glob("fork_*.json")):
        try:
            data = json.loads(f.read_text())
            forks.append({
                "fork_id": data["fork_id"],
                "title": data["title"],
                "created_at": data["created_at"],
                "messages": len(data["messages"]),
                "iteration": data.get("iteration", 0),
            })
        except (json.JSONDecodeError, KeyError):
            continue

    return forks


def _unique_fork_name(forks_dir: Path, base_name: str) -> str:
    """Ensure fork name is unique (production pattern)."""
    candidate = f"{base_name} (Branch)"

    # Check if any existing fork has this title
    existing_titles = set()
    for f in forks_dir.glob("fork_*.json"):
        try:
            data = json.loads(f.read_text())
            existing_titles.add(data.get("title", ""))
        except (json.JSONDecodeError, KeyError):
            continue

    if candidate not in existing_titles:
        return candidate

    # Find next available number
    n = 2
    while f"{base_name} (Branch {n})" in existing_titles:
        n += 1
    return f"{base_name} (Branch {n})"
