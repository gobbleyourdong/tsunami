"""Trace extractor — pull structured training data from session history.

Walks workspace/.history/ for completed sessions and extracts:
- Full conversation traces (system, user, tool calls, results)
- Per-tool-call pairs (instruction → action)
- Session metadata (iterations, scaffold, compile status)

Output: list of SessionTrace objects ready for pair generation.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger("tsunami.training.trace_extractor")


@dataclass
class ToolCallRecord:
    """A single tool call extracted from a session."""
    tool_name: str
    arguments: dict
    result: str
    was_error: bool
    iteration: int = 0


@dataclass
class SessionTrace:
    """Full trace from one agent session."""
    session_id: str
    user_prompt: str
    system_prompt: str
    tool_calls: list[ToolCallRecord]
    plan: dict | None = None
    iterations: int = 0
    task_complete: bool = False
    scaffold_used: str = ""
    deliverable_path: str = ""

    # Quality signals (filled by quality_filter)
    compiles: bool = False
    renders: bool = False
    score: int = 0


def extract_session(session_path: Path) -> SessionTrace | None:
    """Extract a structured trace from a session JSONL file.

    Returns None if the session is too short or malformed.
    """
    try:
        lines = session_path.read_text().strip().split("\n")
        if len(lines) < 3:
            return None

        messages = [json.loads(line) for line in lines]
    except (json.JSONDecodeError, IOError) as e:
        log.warning(f"Failed to parse {session_path.name}: {e}")
        return None

    # First line is metadata
    meta = messages[0] if messages[0].get("_meta") else None
    conversation = [m for m in messages if not m.get("_meta")]

    if len(conversation) < 2:
        return None

    # Extract system prompt and user message
    system_prompt = ""
    user_prompt = ""
    for msg in conversation:
        if msg.get("role") == "system" and not system_prompt:
            system_prompt = msg.get("content", "")
        elif msg.get("role") == "user" and not user_prompt:
            user_prompt = msg.get("content", "")
            break

    if not user_prompt:
        return None

    # Extract tool calls
    tool_calls = []
    iteration = 0
    scaffold_used = ""

    for msg in conversation:
        tc = msg.get("tool_call")
        if tc and msg.get("role") == "assistant":
            func = tc.get("function", tc)
            name = func.get("name", "")
            args = func.get("arguments", {})

            # Find the corresponding result
            result_content = ""
            was_error = False
            idx = conversation.index(msg)
            for subsequent in conversation[idx + 1:]:
                if subsequent.get("role") == "tool_result":
                    result_content = subsequent.get("content", "")
                    was_error = "ERROR" in result_content[:100]
                    break
                elif subsequent.get("role") == "assistant":
                    break  # next tool call, no result found

            iteration += 1
            tool_calls.append(ToolCallRecord(
                tool_name=name,
                arguments=args,
                result=result_content[:2000],  # cap result size
                was_error=was_error,
                iteration=iteration,
            ))

            # Track scaffold
            if name == "project_init":
                scaffold_used = args.get("scaffold", "") or _infer_scaffold(args)

    # Extract plan from metadata
    plan = meta.get("plan") if meta else None

    trace = SessionTrace(
        session_id=session_path.stem,
        user_prompt=user_prompt,
        system_prompt=system_prompt[:500],  # truncate system prompt for storage
        tool_calls=tool_calls,
        plan=plan,
        iterations=meta.get("iteration", len(tool_calls)) if meta else len(tool_calls),
        task_complete=meta.get("task_complete", False) if meta else False,
        scaffold_used=scaffold_used,
    )

    return trace


def _infer_scaffold(args: dict) -> str:
    """Infer scaffold from project_init arguments."""
    name = args.get("name", "")
    deps = args.get("dependencies", [])
    # Import the classifier
    try:
        from tsunami.tools.project_init import _pick_scaffold
        return _pick_scaffold(name, deps)
    except Exception:
        return ""


def extract_all(history_dir: Path) -> list[SessionTrace]:
    """Extract traces from all sessions in the history directory.

    Returns traces sorted by session ID (chronological).
    """
    if not history_dir.exists():
        return []

    traces = []
    for session_file in sorted(history_dir.glob("session_*.jsonl")):
        trace = extract_session(session_file)
        if trace and len(trace.tool_calls) >= 2:  # skip trivial sessions
            traces.append(trace)

    log.info(f"Extracted {len(traces)} traces from {history_dir}")
    return traces


def extract_stats(traces: list[SessionTrace]) -> dict:
    """Compute statistics over extracted traces."""
    if not traces:
        return {"count": 0}

    total_tool_calls = sum(len(t.tool_calls) for t in traces)
    complete = sum(1 for t in traces if t.task_complete)
    scaffolds = {}
    for t in traces:
        s = t.scaffold_used or "none"
        scaffolds[s] = scaffolds.get(s, 0) + 1

    tool_freq = {}
    for t in traces:
        for tc in t.tool_calls:
            tool_freq[tc.tool_name] = tool_freq.get(tc.tool_name, 0) + 1

    return {
        "count": len(traces),
        "total_tool_calls": total_tool_calls,
        "avg_tool_calls": round(total_tool_calls / len(traces), 1),
        "complete_rate": round(complete / len(traces), 2),
        "scaffolds": scaffolds,
        "top_tools": dict(sorted(tool_freq.items(), key=lambda x: -x[1])[:10]),
    }
