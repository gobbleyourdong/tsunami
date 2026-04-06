"""Format training data using Gemma 4's native tool call tokens.

Matches the EXACT format that gemma4_no_think.jinja produces at inference:
- Role: <|turn>model (NOT assistant)
- Tool declarations: <|tool>declaration:name{...}<tool|> in system turn
- Arg order: alphabetical (jinja dictsort)
- Quotes: <|"|> for all string values
- Tool responses: <|tool_response>response:name{...}<tool_response|>

The model already knows this format from pretraining. We're reinforcing it
for the no-think path so it produces tool calls without the thinking preamble.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from .trace_extractor import SessionTrace, ToolCallRecord

log = logging.getLogger("tsunami.training.native_toolcall_formatter")

QUOTE = '<|"|>'

# ---------------------------------------------------------------------------
# Tool schemas — must match what build_registry() produces at inference.
# These are used to generate <|tool>declaration:...<tool|> blocks.
# ---------------------------------------------------------------------------
TOOL_SCHEMAS = {
    'file_read': {
        'description': 'Read text content from a file.',
        'parameters': {
            'type': 'OBJECT',
            'properties': {
                'path': {'type': 'STRING', 'description': 'Path to the file to read'},
                'offset': {'type': 'INTEGER', 'description': 'Line number to start from (0-indexed)'},
                'limit': {'type': 'INTEGER', 'description': 'Max lines to read'},
            },
            'required': ['path'],
        },
    },
    'file_write': {
        'description': 'Create or overwrite a file with full content.',
        'parameters': {
            'type': 'OBJECT',
            'properties': {
                'content': {'type': 'STRING', 'description': 'Full file content'},
                'path': {'type': 'STRING', 'description': 'Path to write to'},
            },
            'required': ['path', 'content'],
        },
    },
    'file_edit': {
        'description': 'Make targeted modifications to an existing file.',
        'parameters': {
            'type': 'OBJECT',
            'properties': {
                'new_text': {'type': 'STRING', 'description': 'Replacement text'},
                'old_text': {'type': 'STRING', 'description': 'Exact text to find and replace'},
                'path': {'type': 'STRING', 'description': 'Path to the file'},
            },
            'required': ['path', 'old_text', 'new_text'],
        },
    },
    'shell_exec': {
        'description': 'Run a shell command and return its output.',
        'parameters': {
            'type': 'OBJECT',
            'properties': {
                'command': {'type': 'STRING', 'description': 'Shell command to execute'},
                'timeout': {'type': 'INTEGER', 'description': 'Timeout in seconds'},
                'workdir': {'type': 'STRING', 'description': 'Working directory'},
            },
            'required': ['command'],
        },
    },
    'match_glob': {
        'description': 'Find files by name and path patterns.',
        'parameters': {
            'type': 'OBJECT',
            'properties': {
                'directory': {'type': 'STRING', 'description': 'Directory to search in'},
                'limit': {'type': 'INTEGER', 'description': 'Max results'},
                'pattern': {'type': 'STRING', 'description': 'Glob pattern'},
            },
            'required': ['pattern'],
        },
    },
    'match_grep': {
        'description': 'Search file contents by regex pattern.',
        'parameters': {
            'type': 'OBJECT',
            'properties': {
                'directory': {'type': 'STRING', 'description': 'Directory to search in'},
                'file_pattern': {'type': 'STRING', 'description': 'Glob filter for files'},
                'limit': {'type': 'INTEGER', 'description': 'Max results'},
                'pattern': {'type': 'STRING', 'description': 'Regex pattern to search for'},
            },
            'required': ['pattern'],
        },
    },
    'message_info': {
        'description': 'Acknowledge, update, or inform the user.',
        'parameters': {
            'type': 'OBJECT',
            'properties': {
                'text': {'type': 'STRING', 'description': 'Information to share'},
            },
            'required': ['text'],
        },
    },
    'message_ask': {
        'description': 'Request input from the user. Only use when genuinely blocked.',
        'parameters': {
            'type': 'OBJECT',
            'properties': {
                'text': {'type': 'STRING', 'description': 'Question to ask'},
            },
            'required': ['text'],
        },
    },
    'message_result': {
        'description': 'Deliver final outcome and end the task.',
        'parameters': {
            'type': 'OBJECT',
            'properties': {
                'text': {'type': 'STRING', 'description': 'Final result to deliver'},
            },
            'required': [],
        },
    },
    'plan_update': {
        'description': 'Create or revise the task plan.',
        'parameters': {
            'type': 'OBJECT',
            'properties': {
                'goal': {'type': 'STRING', 'description': 'Desired end state'},
                'phases': {'type': 'ARRAY', 'description': 'Ordered list of phases',
                           'items': {'type': 'OBJECT'}},
            },
            'required': ['goal', 'phases'],
        },
    },
    'search_web': {
        'description': 'Search the web for information.',
        'parameters': {
            'type': 'OBJECT',
            'properties': {
                'num_results': {'type': 'INTEGER', 'description': 'Number of results'},
                'query': {'type': 'STRING', 'description': 'Search query'},
                'search_type': {'type': 'STRING', 'description': 'Type of search'},
            },
            'required': ['query'],
        },
    },
    'project_init': {
        'description': 'Create a project from the scaffold library.',
        'parameters': {
            'type': 'OBJECT',
            'properties': {
                'dependencies': {'type': 'ARRAY', 'description': 'Extra npm packages',
                                 'items': {'type': 'STRING'}},
                'name': {'type': 'STRING', 'description': 'Project name'},
            },
            'required': ['name'],
        },
    },
    'generate_image': {
        'description': 'Generate an image from a text description.',
        'parameters': {
            'type': 'OBJECT',
            'properties': {
                'height': {'type': 'INTEGER', 'description': 'Image height'},
                'prompt': {'type': 'STRING', 'description': 'Text description'},
                'save_path': {'type': 'STRING', 'description': 'Path to save image'},
                'style': {'type': 'STRING', 'description': 'Style hint'},
                'width': {'type': 'INTEGER', 'description': 'Image width'},
            },
            'required': ['prompt', 'save_path'],
        },
    },
    'load_toolbox': {
        'description': 'Load tools on demand. Available: browser, webdev, generate, services, parallel, management',
        'parameters': {
            'type': 'OBJECT',
            'properties': {
                'toolbox': {'type': 'STRING', 'description': 'Toolbox to load'},
            },
            'required': [],
        },
    },
    'python_exec': {
        'description': 'Run Python code for computation or data processing.',
        'parameters': {
            'type': 'OBJECT',
            'properties': {
                'code': {'type': 'STRING', 'description': 'Python code to execute'},
            },
            'required': ['code'],
        },
    },
    'swell': {
        'description': 'Dispatch up to 4 parallel eddy workers.',
        'parameters': {
            'type': 'OBJECT',
            'properties': {
                'tasks': {'type': 'ARRAY', 'description': 'List of {prompt, target} tasks',
                          'items': {'type': 'OBJECT'}},
            },
            'required': ['tasks'],
        },
    },
    'undertow': {
        'description': 'Test an HTML file by screenshot, keypresses, clicks.',
        'parameters': {
            'type': 'OBJECT',
            'properties': {
                'expect': {'type': 'STRING', 'description': 'What the app should look like'},
                'path': {'type': 'STRING', 'description': 'Path to HTML file'},
            },
            'required': ['path'],
        },
    },
    'summarize_file': {
        'description': 'Summarize a file via fast model.',
        'parameters': {
            'type': 'OBJECT',
            'properties': {
                'focus': {'type': 'STRING', 'description': 'What to focus on'},
                'path': {'type': 'STRING', 'description': 'Path to file'},
            },
            'required': ['path'],
        },
    },
    # Webdev toolbox tools (loaded dynamically but appear in training data)
    'webdev_scaffold': {
        'description': 'Scaffold a web project.',
        'parameters': {
            'type': 'OBJECT',
            'properties': {
                'name': {'type': 'STRING', 'description': 'Project name'},
            },
            'required': ['name'],
        },
    },
    'webdev_serve': {
        'description': 'Start dev server for a project.',
        'parameters': {
            'type': 'OBJECT',
            'properties': {
                'project': {'type': 'STRING', 'description': 'Project directory'},
            },
            'required': ['project'],
        },
    },
    'webdev_screenshot': {
        'description': 'Take a screenshot of a running web page.',
        'parameters': {
            'type': 'OBJECT',
            'properties': {
                'save_path': {'type': 'STRING', 'description': 'Path to save screenshot'},
                'url': {'type': 'STRING', 'description': 'URL to screenshot'},
            },
            'required': ['url'],
        },
    },
    'webdev_generate_assets': {
        'description': 'Generate assets for a web project.',
        'parameters': {
            'type': 'OBJECT',
            'properties': {
                'prompts': {'type': 'ARRAY', 'description': 'Asset descriptions',
                            'items': {'type': 'STRING'}},
                'save_dir': {'type': 'STRING', 'description': 'Directory to save'},
            },
            'required': ['prompts', 'save_dir'],
        },
    },
    'plan_advance': {
        'description': 'Advance to the next phase of the plan.',
        'parameters': {
            'type': 'OBJECT',
            'properties': {},
            'required': [],
        },
    },
    'file_append': {
        'description': 'Append content to a file.',
        'parameters': {
            'type': 'OBJECT',
            'properties': {
                'content': {'type': 'STRING', 'description': 'Content to append'},
                'path': {'type': 'STRING', 'description': 'Path to file'},
            },
            'required': ['path', 'content'],
        },
    },
    'vision_ground': {
        'description': 'Extract UI element positions from an image.',
        'parameters': {
            'type': 'OBJECT',
            'properties': {
                'elements': {'type': 'ARRAY', 'description': 'Elements to find',
                             'items': {'type': 'STRING'}},
                'image_path': {'type': 'STRING', 'description': 'Path to image'},
            },
            'required': ['image_path'],
        },
    },
}


def _format_param_property(name: str, prop: dict) -> str:
    """Format a single parameter property in Gemma 4 declaration style."""
    parts = []
    if 'description' in prop:
        parts.append(f'description:{QUOTE}{prop["description"]}{QUOTE}')
    if 'items' in prop:
        items = prop['items']
        if isinstance(items, dict) and 'type' in items:
            parts.append(f'items:{{type:{QUOTE}{items["type"]}{QUOTE}}}')
    parts.append(f'type:{QUOTE}{prop["type"]}{QUOTE}')
    return f'{name}:{{{",".join(parts)}}}'


def format_tool_declaration(name: str, schema: dict) -> str:
    """Format a tool declaration matching gemma4_no_think.jinja output.

    Produces: <|tool>declaration:name{description:"...",parameters:{...}}<tool|>
    """
    desc = schema['description']
    params = schema.get('parameters', {})

    # Build properties (alphabetically sorted — matches jinja dictsort)
    props_parts = []
    for pname in sorted(params.get('properties', {}).keys()):
        prop = params['properties'][pname]
        props_parts.append(_format_param_property(pname, prop))

    # Build required list
    req_parts = []
    for r in params.get('required', []):
        req_parts.append(f'{QUOTE}{r}{QUOTE}')

    # Assemble
    inner = f'description:{QUOTE}{desc}{QUOTE}'
    if props_parts:
        inner += f',parameters:{{properties:{{{",".join(props_parts)}}}'
        if req_parts:
            inner += f',required:[{",".join(req_parts)}]'
        inner += f',type:{QUOTE}{params["type"]}{QUOTE}}}'

    return f'<|tool>declaration:{name}{{{inner}}}<tool|>'


def format_native_tool_call(name: str, arguments: dict) -> str:
    """Format a tool call using Gemma 4 native tokens.

    Args are sorted alphabetically to match jinja dictsort behavior.
    """
    args_parts = []
    for key in sorted(arguments.keys()):
        value = arguments[key]
        if isinstance(value, str):
            args_parts.append(f'{key}:{QUOTE}{value}{QUOTE}')
        elif isinstance(value, bool):
            args_parts.append(f'{key}:{"true" if value else "false"}')
        elif isinstance(value, (int, float)):
            args_parts.append(f'{key}:{value}')
        elif isinstance(value, list):
            # Format list items
            items = []
            for item in value:
                if isinstance(item, str):
                    items.append(f'{QUOTE}{item}{QUOTE}')
                elif isinstance(item, dict):
                    dict_parts = []
                    for dk in sorted(item.keys()):
                        dv = item[dk]
                        if isinstance(dv, str):
                            dict_parts.append(f'{dk}:{QUOTE}{dv}{QUOTE}')
                        else:
                            dict_parts.append(f'{dk}:{dv}')
                    items.append('{' + ','.join(dict_parts) + '}')
                else:
                    items.append(str(item))
            args_parts.append(f'{key}:[{",".join(items)}]')
        elif isinstance(value, dict):
            dict_parts = []
            for dk in sorted(value.keys()):
                dv = value[dk]
                if isinstance(dv, str):
                    dict_parts.append(f'{dk}:{QUOTE}{dv}{QUOTE}')
                else:
                    dict_parts.append(f'{dk}:{dv}')
            args_parts.append(f'{key}:{{{",".join(dict_parts)}}}')
        else:
            args_parts.append(f'{key}:{QUOTE}{json.dumps(value)}{QUOTE}')

    args_str = ','.join(args_parts)
    return f'<|tool_call>call:{name}{{{args_str}}}<tool_call|>'


def format_native_tool_response(name: str, result: str) -> str:
    """Format a tool response using Gemma 4 native tokens."""
    truncated = result[:500] if result else 'OK'
    return f'<|tool_response>response:{name}{{value:{QUOTE}{truncated}{QUOTE}}}<tool_response|>'


def trace_to_native_text(trace: SessionTrace) -> str:
    """Convert a session trace into the EXACT text format Gemma 4 sees at inference.

    This is what the gemma4_no_think.jinja template would produce.
    No intermediate ShareGPT — direct to the final token sequence.
    """
    parts = []

    # --- System turn with tool declarations ---
    system_content = (
        "You are Tsunami, an autonomous app builder. "
        "You build apps by calling tools. Call project_init first, then file_write with complete code. "
        "Call message_result when done. One tool call per response. Act immediately, don't explain."
    )

    # Collect tools used in this trace + always include core tools
    tools_used = set(tc.tool_name for tc in trace.tool_calls)
    core_tools = {'file_write', 'file_read', 'file_edit', 'shell_exec',
                  'message_info', 'message_result', 'project_init', 'match_glob'}
    all_tools = tools_used | core_tools

    # Build system turn
    parts.append(f'<|turn>system\n{system_content}')

    # Add tool declarations (alphabetically — matches jinja order)
    for tool_name in sorted(all_tools):
        if tool_name in TOOL_SCHEMAS:
            parts.append(format_tool_declaration(tool_name, TOOL_SCHEMAS[tool_name]))

    parts.append('<turn|>')

    # --- User turn ---
    parts.append(f'<|turn>user\n{trace.user_prompt}<turn|>')

    # --- Tool call / response pairs ---
    for tc in trace.tool_calls:
        # Model makes a tool call (note: "model" not "assistant")
        tool_call_text = format_native_tool_call(tc.tool_name, tc.arguments)
        parts.append(f'<|turn>model\n{tool_call_text}<turn|>')

        # Tool response (comes as user turn in Gemma 4 convention)
        response_text = format_native_tool_response(tc.tool_name, tc.result)
        parts.append(f'<|turn>user\n{response_text}<turn|>')

    return '\n'.join(parts)


def generate_native_training_data(traces: list[SessionTrace]) -> list[dict]:
    """Generate training data using native Gemma 4 format.

    Each example is a single {"text": "..."} dict containing the exact
    token sequence the model should learn to produce.
    """
    examples = []

    for trace in traces:
        if not trace.task_complete:
            continue
        if len(trace.tool_calls) < 3:
            continue

        text = trace_to_native_text(trace)

        examples.append({
            "text": text,
            "metadata": {
                "session_id": trace.session_id,
                "scaffold": trace.scaffold_used,
                "tool_calls": len(trace.tool_calls),
            },
        })

    log.info(f"Generated {len(examples)} native tool call training examples")
    return examples


# ---------------------------------------------------------------------------
# Reformat existing data: fix role + add declarations + sort args
# ---------------------------------------------------------------------------

def reformat_existing_data(input_path: str, output_path: str) -> int:
    """Reformat existing e4b training data to match native Gemma 4 format.

    Fixes:
    1. <|turn>assistant -> <|turn>model
    2. Adds <|tool>declaration:...<tool|> blocks to system turn
    3. Sorts tool call args alphabetically (matches jinja dictsort)

    Returns number of examples reformatted.
    """
    examples = []
    with open(input_path) as f:
        for line in f:
            examples.append(json.loads(line))

    reformatted = []
    for ex in examples:
        text = ex.get('text', '')
        if not text:
            continue

        # Fix 1: assistant -> model
        text = text.replace('<|turn>assistant\n', '<|turn>model\n')

        # Fix 2: Add tool declarations to system turn
        # Find the end of the system content (before <turn|>)
        system_end = text.find('<turn|>')
        if system_end > 0:
            # Extract all tool names used in this example
            tool_names = set(re.findall(r'call:(\w+)\{', text))
            core_tools = {'file_write', 'file_read', 'file_edit', 'shell_exec',
                          'message_info', 'message_result', 'project_init', 'match_glob'}
            all_tools = tool_names | core_tools

            # Check if declarations already present
            if '<|tool>declaration:' not in text:
                declarations = []
                for name in sorted(all_tools):
                    if name in TOOL_SCHEMAS:
                        declarations.append(format_tool_declaration(name, TOOL_SCHEMAS[name]))

                # Insert declarations before the closing <turn|>
                decl_block = '\n'.join(declarations)
                text = text[:system_end] + '\n' + decl_block + text[system_end:]

        # Fix 3: Sort args alphabetically in tool calls
        def sort_tool_call_args(match):
            """Re-sort args inside a <|tool_call>call:name{...}<tool_call|> block."""
            full = match.group(0)
            name_match = re.match(r'<\|tool_call>call:(\w+)\{', full)
            if not name_match:
                return full
            tool_name = name_match.group(1)

            # Extract the args string between { and }<tool_call|>
            args_start = full.index('{') + 1
            args_end = full.rindex('}')
            args_str = full[args_start:args_end]

            # Parse key:value pairs (handling nested braces and <|"|> quotes)
            pairs = _parse_native_args(args_str)
            if pairs is None:
                return full  # couldn't parse, leave as-is

            # Re-sort alphabetically
            sorted_pairs = sorted(pairs, key=lambda p: p[0])
            sorted_str = ','.join(f'{k}:{v}' for k, v in sorted_pairs)

            return f'<|tool_call>call:{tool_name}{{{sorted_str}}}<tool_call|>'

        text = re.sub(
            r'<\|tool_call>call:\w+\{.*?\}<tool_call\|>',
            sort_tool_call_args,
            text,
            flags=re.DOTALL,
        )

        reformatted.append({"text": text})

    # Write output
    with open(output_path, 'w') as f:
        for ex in reformatted:
            f.write(json.dumps(ex, ensure_ascii=False) + '\n')

    log.info(f"Reformatted {len(reformatted)} examples: {input_path} -> {output_path}")
    return len(reformatted)


def _parse_native_args(args_str: str) -> list[tuple[str, str]] | None:
    """Parse key:value pairs from native tool call args string.

    Handles nested braces, <|"|> quoted strings, and arrays.
    Returns list of (key, raw_value_string) tuples, or None on failure.
    """
    pairs = []
    i = 0
    n = len(args_str)

    while i < n:
        # Skip whitespace/commas
        while i < n and args_str[i] in ' ,\n\t':
            i += 1
        if i >= n:
            break

        # Read key (up to :)
        key_start = i
        while i < n and args_str[i] != ':':
            i += 1
        if i >= n:
            return None
        key = args_str[key_start:i].strip()
        i += 1  # skip :

        # Read value (respecting nesting)
        val_start = i
        depth = 0
        in_quote = False
        while i < n:
            # Check for <|"|> quote boundaries
            if args_str[i:i+4] == '<|"|':
                if args_str[i:i+5] == '<|"|>':
                    in_quote = not in_quote
                    i += 5
                    continue
            if not in_quote:
                if args_str[i] in '{[':
                    depth += 1
                elif args_str[i] in '}]':
                    if depth == 0:
                        break
                    depth -= 1
                elif args_str[i] == ',' and depth == 0:
                    break
            i += 1

        value = args_str[val_start:i]
        pairs.append((key, value))

    return pairs


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    import sys
    logging.basicConfig(level=logging.INFO, format='%(message)s')

    if len(sys.argv) < 3:
        print("Usage: python -m tsunami.training.native_toolcall_formatter <input.jsonl> <output.jsonl>")
        print("       Reformats existing training data to match Gemma 4 native format.")
        sys.exit(1)

    count = reformat_existing_data(sys.argv[1], sys.argv[2])
    print(f"Reformatted {count} examples")
