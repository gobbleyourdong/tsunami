"""Format training data with inline tool calls for no-think Gemma 4.

Instead of using OpenAI's tool_call format (which requires thinking mode),
we train the model to output tool calls as structured text inline:

    <tool>file_write</tool>
    <args>{"path": "src/App.tsx", "content": "import React..."}</args>

The model learns this format during SFT, then at inference the framework
parses these tags from the content field. No thinking tokens needed.

This is similar to how Claude's XML tool format works — structured text
in the response, not a separate JSON channel.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from .trace_extractor import SessionTrace, ToolCallRecord
from .pair_generator import BuilderPair, OrchestratorPair

log = logging.getLogger("tsunami.training.inline_toolcall_formatter")

# The inline format the model will learn
# Use triple-pipe delimiters — can't appear in any valid code
TOOL_CALL_FORMAT = '|||TOOL:{name}|||{args}|||END|||'


def format_tool_call_inline(name: str, arguments: dict) -> str:
    """Format a tool call as inline structured text."""
    args_json = json.dumps(arguments, ensure_ascii=False)
    return TOOL_CALL_FORMAT.format(name=name, args=args_json)


def parse_tool_call_inline(text: str) -> tuple[str, dict] | None:
    """Parse an inline tool call from model output.

    Returns (name, arguments) or None if no tool call found.
    """
    import re
    match = re.search(r'\|\|\|TOOL:(.*?)\|\|\|(.*?)\|\|\|END\|\|\|', text, re.DOTALL)
    if not match:
        return None
    name = match.group(1).strip()
    try:
        args = json.loads(match.group(2).strip())
    except json.JSONDecodeError:
        return None
    return name, args


def trace_to_inline_conversation(trace: SessionTrace) -> list[dict]:
    """Convert a session trace into a conversation with inline tool calls.

    Each tool call becomes an assistant message with inline format,
    and each tool result becomes a user message.
    """
    messages = []

    # System prompt
    messages.append({
        "role": "system",
        "content": (
            "You are Tsunami, an autonomous app builder. "
            "When you need to use a tool, output it as:\n"
            '|||TOOL:tool_name|||{"key": "value"}|||END|||\n\n'
            "Available tools: project_init, file_write, file_edit, file_read, "
            "shell_exec, message_result, message_info\n\n"
            "Rules:\n"
            "- Call project_init FIRST\n"
            "- Write complete code in file_write (not stubs)\n"
            "- Call message_result when done\n"
            "- One tool call per response"
        ),
    })

    # User request
    messages.append({
        "role": "user",
        "content": trace.user_prompt,
    })

    # Tool calls and results
    for tc in trace.tool_calls:
        # Assistant: inline tool call
        inline = format_tool_call_inline(tc.tool_name, tc.arguments)
        messages.append({
            "role": "assistant",
            "content": inline,
        })

        # User: tool result
        result_preview = tc.result[:500] if tc.result else "OK"
        messages.append({
            "role": "user",
            "content": f"[{tc.tool_name} result]: {result_preview}",
        })

    return messages


def generate_inline_training_data(traces: list[SessionTrace]) -> list[dict]:
    """Generate ShareGPT-format training data with inline tool calls.

    Each example is a multi-turn conversation showing the model how to
    use inline tool calls to build an app.
    """
    examples = []

    for trace in traces:
        if not trace.task_complete:
            continue
        if len(trace.tool_calls) < 3:
            continue

        messages = trace_to_inline_conversation(trace)

        # Convert to ShareGPT format
        conversations = []
        for msg in messages:
            if msg["role"] == "system":
                conversations.append({"from": "system", "value": msg["content"]})
            elif msg["role"] == "user":
                conversations.append({"from": "human", "value": msg["content"]})
            elif msg["role"] == "assistant":
                conversations.append({"from": "gpt", "value": msg["content"]})

        if len(conversations) >= 4:  # system + user + at least one tool call + result
            examples.append({
                "conversations": conversations,
                "metadata": {
                    "session_id": trace.session_id,
                    "scaffold": trace.scaffold_used,
                    "iterations": trace.iterations,
                },
            })

    log.info(f"Generated {len(examples)} inline tool call training examples")
    return examples


def generate_inline_pairs_from_builders(builder_pairs: list[BuilderPair]) -> list[dict]:
    """Convert builder pairs into inline tool call format.

    Each builder pair becomes: user asks → assistant calls file_write with inline format.
    """
    examples = []

    for pair in builder_pairs:
        conversations = [
            {
                "from": "system",
                "value": (
                    "You are Tsunami. Use inline tool calls:\n"
                    '|||TOOL:tool_name|||{...}|||END|||\n\n'
                    "Write complete code. No stubs. No explanations."
                ),
            },
            {
                "from": "human",
                "value": pair.instruction,
            },
            {
                "from": "gpt",
                "value": format_tool_call_inline("file_write", {
                    "path": f"src/{pair.metadata.get('filename', 'App.tsx')}",
                    "content": pair.output,
                }),
            },
        ]

        examples.append({
            "conversations": conversations,
            "metadata": pair.metadata,
        })

    log.info(f"Generated {len(examples)} inline builder pairs")
    return examples
