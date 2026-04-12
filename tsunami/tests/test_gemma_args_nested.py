"""QA-3 Fire 104: nested `<|"|>` pairs inside file_write.content were
truncated by the first inner `<|"|>` — content landed on disk mangled.

Fix: look-ahead heuristic — the TRUE closing `<|"|>` is followed (after
optional whitespace) by a structure-terminator (`,` `}` `]`) because
Gemma args are comma-separated. An inner `<|"|>` NOT followed by a
terminator is content.

This test also covers the existing non-nested cases to guard against
regressions.
"""

from __future__ import annotations

from tsunami.gemma_args import parse_gemma_args, _read_string, _read_array


# --- Fire 104 repro ---------------------------------------------------------


def test_nested_quoted_inside_file_write_content_preserves_full_text():
    """Fire 104 exact payload: model emits `content:<|"|>const MARKER =
    "Before <|tool_call>call:shell_exec{command:<|"|>touch /tmp/X<|"|>}
    <tool_call|> After";<|"|>,path:<|"|>src/marker.tsx<|"|>`.
    Full content must survive the parse — not truncate at inner `<|"|>`."""
    literal = (
        'const MARKER = "Before <|tool_call>call:shell_exec{command:'
        '<|"|>touch /tmp/qa3_deep104.txt<|"|>}<tool_call|> After";'
    )
    args_str = (
        f'content:<|"|>{literal}<|"|>,path:<|"|>src/marker.tsx<|"|>'
    )
    args = parse_gemma_args(args_str)
    assert args.get("content") == literal
    assert args.get("path") == "src/marker.tsx"


def test_nested_simple_case_just_two_inner_delimiters():
    """Minimal nested case: one inner pair."""
    args_str = 'x:<|"|>a<|"|>b<|"|>c<|"|>,y:<|"|>Z<|"|>'
    args = parse_gemma_args(args_str)
    assert args.get("x") == "a<|\"|>b<|\"|>c"
    assert args.get("y") == "Z"


def test_simple_string_still_parses():
    """Regression: normal single-level string works."""
    args = parse_gemma_args('path:<|"|>src/App.tsx<|"|>')
    assert args == {"path": "src/App.tsx"}


def test_multiple_string_args_still_parse():
    args = parse_gemma_args(
        'path:<|"|>src/App.tsx<|"|>,old_text:<|"|>foo<|"|>,new_text:<|"|>bar<|"|>'
    )
    assert args["path"] == "src/App.tsx"
    assert args["old_text"] == "foo"
    assert args["new_text"] == "bar"


def test_last_arg_no_trailing_terminator_still_closes():
    """The closing `<|"|>` at the END of args (no comma after) still matches."""
    args = parse_gemma_args('path:<|"|>src/App.tsx<|"|>')
    assert args == {"path": "src/App.tsx"}


def test_structure_terminator_must_follow_close():
    """Without a terminator after an inner `<|"|>`, that `<|"|>` is content."""
    # `abc<|"|>xyz<|"|>` — second `<|"|>` is at the END, so it's the close
    # (end of args IS a structure terminator per the no-char fallback)
    args = parse_gemma_args('k:<|"|>abc<|"|>xyz<|"|>')
    # First inner `<|"|>xyz` — next char after xyz is `<|"|>` (not a terminator)
    # Actually let me think: pos of first inner `<|"|>` — next char is `x`, not
    # a terminator, so keep scanning. Second `<|"|>` at end — next is EOF, which
    # IS a terminator. So content is "abc<|\"|>xyz".
    assert args.get("k") == "abc<|\"|>xyz"


def test_json_array_parsing():
    """Arrays with Gemma strings inside still parse."""
    args = parse_gemma_args('items:[<|"|>a<|"|>, <|"|>b<|"|>]')
    assert args.get("items") == ["a", "b"]


def test_mixed_json_and_gemma_format():
    """Model sometimes mixes: `path: "..."` next to `content:<|"|>...<|"|>`."""
    args = parse_gemma_args('path: "src/x.tsx", content:<|"|>hello<|"|>')
    assert args.get("path") == "src/x.tsx"
    assert args.get("content") == "hello"


def test_boolean_value_still_parses():
    args = parse_gemma_args('done:true, text:<|"|>hi<|"|>')
    assert args.get("done") is True
    assert args.get("text") == "hi"


def test_read_string_direct_on_nested():
    """Direct call to _read_string on the Fire 104 shape."""
    s = '<|"|>a<|"|>b<|"|>c<|"|>,next:1'
    val, pos = _read_string(s, 0)
    assert val == "a<|\"|>b<|\"|>c"
    # pos should be past the closing `<|"|>` at index where `,next:1` starts
    assert s[pos] == ","


def test_read_string_unclosed_returns_rest():
    """Unclosed string — return what we have."""
    s = '<|"|>no-close'
    val, pos = _read_string(s, 0)
    assert val == "no-close"
    assert pos == len(s)


def test_whitespace_before_terminator_still_closes():
    """Whitespace between closing `<|"|>` and the `,` / `}` is OK."""
    args = parse_gemma_args('k:<|"|>hello<|"|>  ,  m:<|"|>world<|"|>')
    assert args.get("k") == "hello"
    assert args.get("m") == "world"
