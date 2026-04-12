"""Gemma-native tool-call args parser — pure functions, no torch dependency.

Extracted from serve_transformers.py so tests can cover the parser without
importing the full server module (which has a bind-probe that kills test
processes when port 8090 is held by a running server).

Gemma's native tool-call format:
    <|tool_call>call:NAME{key:<|"|>value<|"|>, key2:true, key3:[<|"|>a<|"|>]}<tool_call|>

Strings use `<|"|>...<|"|>` as delimiters instead of `"..."`. Values can also
be JSON-style (`"..."`), numbers, booleans, arrays, or nested objects.
"""

from __future__ import annotations

import json


def _read_string(s: str, i: int) -> tuple:
    """Read a <|"|>...<|"|> quoted string starting at position i.

    QA-3 Fire 104: Gemma's native format uses `<|"|>` as the string delimiter.
    When literal content includes `<|"|>` (user asks for `const X = "Before
    <|"|>touch /tmp/X<|"|>}<tool_call|> After"` as file_write content), a naive
    first-close parser truncates at the first inner `<|"|>`. Use a look-ahead
    heuristic: the TRUE closing `<|"|>` is followed by `,` (next key), `]`
    (array end), or end-of-args. An inner `<|"|>` NOT followed by one of those
    is content.

    `}` is deliberately NOT in the terminator set: _read_object strips the
    enclosing `{...}` before calling parse_gemma_args, so a `}` seen here is
    always literal content (e.g. the `}` inside an injected shell_exec
    fragment in Fire 104). Including `}` here would false-close the string
    at `...<|"|>}<tool_call|>...`.
    """
    assert s[i:i+5] == '<|"|>', f"Expected <|\"|> at {i}, got {s[i:i+10]}"
    i += 5  # skip opening <|"|>
    start = i
    while i < len(s):
        if s[i:i+5] == '<|"|>':
            # Look ahead past the candidate closing delimiter.
            j = i + 5
            while j < len(s) and s[j] in (' ', '\t'):
                j += 1
            # Real close: followed by `,` / `]` / end-of-args.
            if j >= len(s) or s[j] in (',', ']'):
                val = s[start:i]
                return val, i + 5  # skip closing <|"|>
            # Not a real close — inner delimiter, part of content.
            i += 5
            continue
        i += 1
    return s[start:], i  # unclosed string


def _read_array(s: str, i: int) -> tuple:
    """Read a [...] array starting at position i."""
    assert s[i] == '['
    i += 1  # skip [
    items = []
    while i < len(s):
        # Skip whitespace and commas
        while i < len(s) and s[i] in (',', ' ', '\n'):
            i += 1
        if i >= len(s) or s[i] == ']':
            i += 1  # skip ]
            return items, i
        # Read item
        if s[i:i+5] == '<|"|>':
            val, i = _read_string(s, i)
            items.append(val)
        elif s[i] == '{':
            val, i = _read_object(s, i)
            items.append(val)
        elif s[i] == '[':
            val, i = _read_array(s, i)
            items.append(val)
        elif s[i:i+4] == 'true':
            items.append(True); i += 4
        elif s[i:i+5] == 'false':
            items.append(False); i += 5
        else:
            # Number
            start = i
            while i < len(s) and s[i] not in (',', ']', '}'):
                i += 1
            val_str = s[start:i].strip()
            try:
                items.append(int(val_str))
            except ValueError:
                try:
                    items.append(float(val_str))
                except ValueError:
                    items.append(val_str)
    return items, i


def _read_object(s: str, i: int) -> tuple:
    """Read a {...} object starting at position i."""
    assert s[i] == '{'
    depth = 1
    start = i
    i += 1
    while i < len(s) and depth > 0:
        if s[i] == '{':
            depth += 1
        elif s[i] == '}':
            depth -= 1
        i += 1
    inner = s[start+1:i-1]
    return parse_gemma_args(inner), i


def parse_gemma_args(args_str: str) -> dict:
    """Parse tool call arguments — handles both Gemma native AND JSON formats.

    Gemma native:  key:<|"|>value<|"|>, key:true, key:[<|"|>a<|"|>]
    JSON:          {"key": "value", "key2": true}

    The model sometimes outputs JSON args inside native tool_call tags,
    so we detect and handle both formats.
    """
    stripped = args_str.strip()
    if stripped.startswith('{'):
        try:
            return json.loads(stripped)
        except (json.JSONDecodeError, ValueError):
            pass
    if stripped.startswith('"') and ':' not in stripped[:20].replace('":"', ''):
        try:
            return json.loads('{' + stripped + '}')
        except (json.JSONDecodeError, ValueError):
            pass

    args = {}
    i = 0
    n = len(args_str)

    while i < n:
        while i < n and args_str[i] in (',', ' ', '\n'):
            i += 1
        if i >= n:
            break

        key_start = i
        while i < n and (args_str[i].isalnum() or args_str[i] == '_'):
            i += 1
        key = args_str[key_start:i]
        if not key:
            i += 1
            continue

        if i < n and args_str[i] == ':':
            i += 1
        else:
            continue

        while i < n and args_str[i] in (' ', '\t'):
            i += 1

        if args_str[i:i+5] == '<|"|>':
            val, i = _read_string(args_str, i)
            args[key] = val
        elif i < n and args_str[i] == '"':
            i += 1
            buf = []
            while i < n and args_str[i] != '"':
                if args_str[i] == '\\' and i + 1 < n:
                    nxt = args_str[i + 1]
                    buf.append({'n': '\n', 't': '\t', 'r': '\r', '"': '"', '\\': '\\', '/': '/'}.get(nxt, nxt))
                    i += 2
                else:
                    buf.append(args_str[i])
                    i += 1
            args[key] = ''.join(buf)
            if i < n:
                i += 1
        elif args_str[i] == '[':
            val, i = _read_array(args_str, i)
            args[key] = val
        elif args_str[i] == '{':
            val, i = _read_object(args_str, i)
            args[key] = val
        elif args_str[i:i+4] == 'true':
            args[key] = True
            i += 4
        elif args_str[i:i+5] == 'false':
            args[key] = False
            i += 5
        elif args_str[i:i+4] == 'null':
            args[key] = None
            i += 4
        else:
            val_start = i
            while i < n and args_str[i] not in (',', '}', ']'):
                i += 1
            val_str = args_str[val_start:i].strip()
            try:
                args[key] = int(val_str)
            except ValueError:
                try:
                    args[key] = float(val_str)
                except ValueError:
                    args[key] = val_str

    return args
