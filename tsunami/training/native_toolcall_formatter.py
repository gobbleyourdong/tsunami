"""Format training data using Gemma 4's native tool call tokens.

The model already knows <|tool_call>...<tool_call|> format from pretraining.
We fine-tune it to produce these tokens WITHOUT the thinking preamble,
so it works with the no-think GGUF at 0.3s/step.

Native format:
    <|tool_call>call:file_write{path:<|"|>src/App.tsx<|"|>,content:<|"|>...<|"|>}<tool_call|>

The llama-server already parses this format and returns proper JSON
in the API response. Zero custom parsing needed.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from .trace_extractor import SessionTrace, ToolCallRecord

log = logging.getLogger("tsunami.training.native_toolcall_formatter")

# Gemma 4 native tool call format
QUOTE = '<|"|>'


def format_native_tool_call(name: str, arguments: dict) -> str:
    """Format a tool call using Gemma 4 native tokens."""
    args_parts = []
    for key, value in arguments.items():
        if isinstance(value, str):
            args_parts.append(f'{key}:{QUOTE}{value}{QUOTE}')
        elif isinstance(value, (int, float, bool)):
            args_parts.append(f'{key}:{value}')
        elif isinstance(value, list):
            args_parts.append(f'{key}:{json.dumps(value)}')
        else:
            args_parts.append(f'{key}:{QUOTE}{json.dumps(value)}{QUOTE}')

    args_str = ','.join(args_parts)
    return f'<|tool_call>call:{name}{{{args_str}}}<tool_call|>'


def format_native_tool_response(name: str, result: str) -> str:
    """Format a tool response using Gemma 4 native tokens."""
    return f'<|tool_response>response:{name}{{value:{QUOTE}{result[:500]}{QUOTE}}}<tool_response|>'


def trace_to_native_conversation(trace: SessionTrace) -> list[dict]:
    """Convert a session trace into native Gemma 4 tool call format.

    This is what the chat template would produce — we're teaching the model
    to produce these tokens directly without thinking.
    """
    messages = []

    # System with tool definitions
    tool_defs = []
    tools_used = set(tc.tool_name for tc in trace.tool_calls)
    tool_schemas = {
        'project_init': {'name': 'project_init', 'description': 'Scaffold a new project', 'parameters': {'name': {'type': 'string'}}},
        'file_write': {'name': 'file_write', 'description': 'Write a file', 'parameters': {'path': {'type': 'string'}, 'content': {'type': 'string'}}},
        'file_edit': {'name': 'file_edit', 'description': 'Edit a file', 'parameters': {'path': {'type': 'string'}, 'old_text': {'type': 'string'}, 'new_text': {'type': 'string'}}},
        'file_read': {'name': 'file_read', 'description': 'Read a file', 'parameters': {'path': {'type': 'string'}}},
        'shell_exec': {'name': 'shell_exec', 'description': 'Run a command', 'parameters': {'command': {'type': 'string'}}},
        'message_result': {'name': 'message_result', 'description': 'Deliver the final result', 'parameters': {'content': {'type': 'string'}}},
        'message_info': {'name': 'message_info', 'description': 'Send info to user', 'parameters': {'content': {'type': 'string'}}},
        'search_web': {'name': 'search_web', 'description': 'Search the web', 'parameters': {'query': {'type': 'string'}}},
        'plan_update': {'name': 'plan_update', 'description': 'Update the plan', 'parameters': {'goal': {'type': 'string'}}},
    }

    system_content = (
        "You are Tsunami, an autonomous app builder. "
        "You build apps by calling tools. Call project_init first, then file_write with complete code. "
        "Call message_result when done. One tool call per response. Act immediately, don't explain."
    )

    messages.append({"role": "system", "content": system_content})

    # User request
    messages.append({"role": "user", "content": trace.user_prompt})

    # Tool call / response pairs
    for tc in trace.tool_calls:
        # Assistant makes a tool call
        tool_call_text = format_native_tool_call(tc.tool_name, tc.arguments)
        messages.append({
            "role": "assistant",
            "content": tool_call_text,
            "tool_calls": [{
                "function": {
                    "name": tc.tool_name,
                    "arguments": tc.arguments,
                }
            }],
        })

        # Tool response
        messages.append({
            "role": "user",
            "content": format_native_tool_response(tc.tool_name, tc.result),
            "tool_responses": [{
                "name": tc.tool_name,
                "response": tc.result[:300],
            }],
        })

    return messages


def generate_native_training_data(traces: list[SessionTrace]) -> list[dict]:
    """Generate training data using native Gemma 4 tool call format."""
    examples = []

    for trace in traces:
        if not trace.task_complete:
            continue
        if len(trace.tool_calls) < 3:
            continue

        messages = trace_to_native_conversation(trace)

        # Convert to ShareGPT
        conversations = []
        for msg in messages:
            if msg["role"] == "system":
                conversations.append({"from": "system", "value": msg["content"]})
            elif msg["role"] == "user":
                conversations.append({"from": "human", "value": msg["content"]})
            elif msg["role"] == "assistant":
                conversations.append({"from": "gpt", "value": msg["content"]})

        if len(conversations) >= 4:
            examples.append({
                "conversations": conversations,
                "metadata": {
                    "session_id": trace.session_id,
                    "scaffold": trace.scaffold_used,
                    "tool_calls": len(trace.tool_calls),
                },
            })

    log.info(f"Generated {len(examples)} native tool call training examples")
    return examples
