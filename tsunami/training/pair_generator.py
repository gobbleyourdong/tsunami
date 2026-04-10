"""Pair generator — convert session traces into training pairs.

Two types of pairs:

1. **Builder pairs (2B)**: Short instruction → code output
   - "Fill this scaffold with a habit tracker" → App.tsx content
   - "Write a Chart component using recharts" → Component code
   - Used for SFT on the 2B model

2. **Orchestrator pairs (9B)**: User prompt → tool call sequence
   - "build a weather dashboard" → [project_init, file_write, file_write, shell_exec, ...]
   - The full plan + execution trace, not just the code
   - Used for SFT on the 9B model

3. **DPO pairs**: (prompt, good_trace, bad_trace)
   - Same prompt, one trace compiled + rendered, one didn't
   - Used for preference optimization
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from .trace_extractor import SessionTrace, ToolCallRecord

log = logging.getLogger("tsunami.training.pair_generator")


@dataclass
class BuilderPair:
    """Training pair for the 2B builder model."""
    instruction: str
    context: str  # scaffold info, component list, types
    output: str   # the code that was written
    metadata: dict = field(default_factory=dict)


@dataclass
class OrchestratorPair:
    """Training pair for the 9B orchestrator model."""
    user_prompt: str
    context: str  # available scaffolds, tools, components
    plan: str     # the plan the agent created
    tool_sequence: list[dict]  # [{name, arguments_summary}]
    metadata: dict = field(default_factory=dict)


@dataclass
class DPOPair:
    """Preference pair for DPO training."""
    prompt: str
    chosen: str    # good trace (compiled + rendered)
    rejected: str  # bad trace (failed)
    metadata: dict = field(default_factory=dict)


def generate_builder_pairs(trace: SessionTrace) -> list[BuilderPair]:
    """Extract builder (2B) training pairs from a session trace.

    Each file_write/file_edit becomes a pair:
      instruction = "Write {filename} for {user_prompt}"
      context = scaffold + types + existing components
      output = the actual file content
    """
    pairs = []

    for tc in trace.tool_calls:
        if tc.tool_name not in ("file_write", "file_edit"):
            continue
        if tc.was_error:
            continue

        path = tc.arguments.get("path", "")
        content = tc.arguments.get("content", "")

        if not path or not content:
            continue
        if len(content) < 50:  # skip trivial writes
            continue

        # Skip non-source files
        if not any(path.endswith(ext) for ext in (".tsx", ".ts", ".jsx", ".js", ".css")):
            continue

        filename = path.rsplit("/", 1)[-1] if "/" in path else path
        instruction = f"Write {filename} for: {trace.user_prompt[:200]}"

        # Build context from what the agent knew at this point
        context_parts = []
        if trace.scaffold_used:
            context_parts.append(f"Scaffold: {trace.scaffold_used}")

        # Collect types.ts and component names from earlier tool calls
        types_content = ""
        components = []
        for prev_tc in trace.tool_calls:
            if prev_tc is tc:
                break
            if prev_tc.tool_name == "file_write":
                prev_path = prev_tc.arguments.get("path", "")
                if "types.ts" in prev_path:
                    types_content = prev_tc.arguments.get("content", "")[:500]
                elif prev_path.endswith(".tsx") and "components" in prev_path:
                    comp_name = prev_path.rsplit("/", 1)[-1].replace(".tsx", "")
                    components.append(comp_name)

        if types_content:
            context_parts.append(f"Types:\n{types_content}")
        if components:
            context_parts.append(f"Existing components: {', '.join(components)}")

        pairs.append(BuilderPair(
            instruction=instruction,
            context="\n".join(context_parts),
            output=content,
            metadata={
                "session_id": trace.session_id,
                "scaffold": trace.scaffold_used,
                "filename": filename,
                "iteration": tc.iteration,
            },
        ))

    return pairs


def generate_orchestrator_pairs(trace: SessionTrace) -> list[OrchestratorPair]:
    """Extract orchestrator (9B) training pairs from a session trace.

    One pair per session: the full prompt → plan + tool sequence.
    """
    if not trace.task_complete:
        return []  # only learn from completed sessions

    # Build plan string
    plan_str = ""
    if trace.plan:
        phases = trace.plan.get("phases", [])
        plan_str = f"Goal: {trace.plan.get('goal', '')}\n"
        for p in phases:
            status = p.get("status", "pending")
            plan_str += f"  [{status}] Phase {p.get('id', '')}: {p.get('title', '')}\n"

    # Build tool sequence (summarized — just name + key args)
    tool_seq = []
    for tc in trace.tool_calls:
        summary = {"name": tc.tool_name}
        args = tc.arguments
        # Include only the most important argument per tool
        if tc.tool_name == "file_write":
            summary["path"] = args.get("path", "")
        elif tc.tool_name == "file_edit":
            summary["path"] = args.get("path", "")
        elif tc.tool_name == "project_init":
            summary["name_arg"] = args.get("name", "")
        elif tc.tool_name == "shell_exec":
            summary["command"] = args.get("command", "")[:80]
        elif tc.tool_name == "search_web":
            summary["query"] = args.get("query", "")[:80]
        elif tc.tool_name == "message_result":
            summary["delivered"] = True

        summary["error"] = tc.was_error
        tool_seq.append(summary)

    # Context: what scaffolds and tools are available
    context = (
        "Available scaffolds: react-app, dashboard, data-viz, form-app, landing, "
        "fullstack, game, realtime, chrome-extension, electron-app, api-only\n"
        "Available tools: project_init, file_write, file_edit, file_read, shell_exec, "
        "search_web, match_grep, match_glob, generate_image, message_result, message_info, "
        "message_ask, plan_update"
    )

    return [OrchestratorPair(
        user_prompt=trace.user_prompt[:500],
        context=context,
        plan=plan_str,
        tool_sequence=tool_seq,
        metadata={
            "session_id": trace.session_id,
            "scaffold": trace.scaffold_used,
            "iterations": trace.iterations,
            "tool_count": len(trace.tool_calls),
            "compiles": trace.compiles,
            "renders": trace.renders,
            "score": trace.score,
        },
    )]


def generate_dpo_pairs(
    good_traces: list[SessionTrace],
    bad_traces: list[SessionTrace],
) -> list[DPOPair]:
    """Generate DPO pairs from good vs bad traces.

    Matches by similar user prompts (fuzzy) and pairs the good trace
    with the bad trace for the same intent.
    """
    pairs = []

    for good in good_traces:
        # Find a bad trace with similar intent
        good_words = set(good.user_prompt.lower().split())
        best_match = None
        best_score = 0

        for bad in bad_traces:
            bad_words = set(bad.user_prompt.lower().split())
            overlap = len(good_words & bad_words) / max(len(good_words | bad_words), 1)
            if overlap > best_score and overlap > 0.3:
                best_score = overlap
                best_match = bad

        if best_match:
            # Format traces as text
            good_text = _format_trace_for_dpo(good)
            bad_text = _format_trace_for_dpo(best_match)

            pairs.append(DPOPair(
                prompt=good.user_prompt[:300],
                chosen=good_text,
                rejected=bad_text,
                metadata={
                    "good_session": good.session_id,
                    "bad_session": best_match.session_id,
                    "similarity": round(best_score, 2),
                },
            ))

    return pairs


def _format_trace_for_dpo(trace: SessionTrace) -> str:
    """Format a trace as a text string for DPO."""
    lines = []
    if trace.plan:
        lines.append(f"Plan: {trace.plan.get('goal', '')}")
    for tc in trace.tool_calls[:20]:  # cap at 20 for context
        args_summary = str(tc.arguments)[:100]
        status = "ERR" if tc.was_error else "OK"
        lines.append(f"[{status}] {tc.tool_name}({args_summary})")
    return "\n".join(lines)
