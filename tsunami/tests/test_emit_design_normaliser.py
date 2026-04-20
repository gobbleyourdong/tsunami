"""Tests for the emit_design JSON auto-normaliser (Fix #7 OSError +
Fix #8 normaliser family).

The Qwen3.6 tool-emit failure mode captured live at /tmp/live_zelda_revalidation:
  - Unquoted property names: `{ RoomGraph: {...} }`
  - Trailing commas in arrays: `[a, b, c,]`
  - Occasional single-quoted strings
  - JS-style line and block comments

Fix #7: emit_design string-path handling was crashing on OSError
(ENAMETOOLONG) when the wave passed a full JSON blob as the design
arg. Guard with looks_like_path heuristic + try/except around
Path().exists().

Fix #8: normaliser family — rewrites common drifts and retries
json.loads. If the retry passes, we send the cleaned version to the
Node CLI. If it still fails, original raw_json goes to Node (which
at least gives the exact error position back to the wave).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO))

# Normaliser was extracted to module level in emit_design.py so tests
# can exercise it directly (Round K cleanup — prior test fixture had
# drifted from the real one by missing block-comment handling).
from tsunami.tools.emit_design import _normalise_qwen_json  # noqa: E402


def test_passthrough_valid_json():
    s = '{"foo": "bar", "list": [1, 2, 3]}'
    out, changed = _normalise_qwen_json(s)
    assert out == s and changed is False


def test_fixes_unquoted_keys():
    bad = '{ foo: 1, bar: "baz" }'
    out, changed = _normalise_qwen_json(bad)
    assert changed is True
    parsed = json.loads(out)
    assert parsed == {"foo": 1, "bar": "baz"}


def test_fixes_trailing_comma_in_array():
    bad = '{"items": [1, 2, 3,]}'
    out, changed = _normalise_qwen_json(bad)
    assert changed is True
    assert json.loads(out) == {"items": [1, 2, 3]}


def test_fixes_trailing_comma_in_object():
    bad = '{"a": 1, "b": 2,}'
    out, changed = _normalise_qwen_json(bad)
    assert changed is True
    assert json.loads(out) == {"a": 1, "b": 2}


def test_fixes_combined_unquoted_and_trailing():
    bad = '{ foo: 1, bar: [1, 2,], baz: 3, }'
    out, changed = _normalise_qwen_json(bad)
    assert changed is True
    assert json.loads(out) == {"foo": 1, "bar": [1, 2], "baz": 3}


def test_qwen_live_case_camera_config():
    """Exact failure signature from the live B-leg at /tmp/live_zelda_revalidation:
       'unquoted keys in the CameraFollow config'."""
    bad = '{"mechanics": {CameraFollow: {target: "player", smoothness: 0.8}}}'
    out, changed = _normalise_qwen_json(bad)
    assert changed is True
    parsed = json.loads(out)
    assert parsed["mechanics"]["CameraFollow"]["target"] == "player"


def test_returns_original_on_unfixable():
    """If the JSON has deeper errors (missing brace, wrong nesting),
    return the original text — let Node's error position through."""
    bad = '{"foo": "bar" broken'  # missing closing brace, extra text
    out, changed = _normalise_qwen_json(bad)
    assert changed is False
    assert out == bad


def test_nested_doesnt_mangle_strings():
    """Unquoted-key regex must NOT rewrite identifiers INSIDE already-
    quoted string values. Sanity check."""
    # Already valid — should pass through unchanged
    s = '{"description": "TurnBasedCombat: hybrid turn/real-time"}'
    out, changed = _normalise_qwen_json(s)
    assert changed is False
    assert out == s


def test_parse_error_annotation_pinpoints_position():
    """Verify the annotator marks the exact character at the reported
    parse-error position with ⟦...⟧ markers."""
    from tsunami.tools.emit_design import _annotate_parse_error
    msg = "Expected ',' or ']' after array element in JSON at position 28"
    raw = '{"items": [1, 2, 3 4, 5, 6, 7, 8]}'
    out = _annotate_parse_error(msg, raw)
    assert "⟦" in out and "⟧" in out
    # The missing-comma is between '3' and '4'; pos 28 should land on a char near that
    assert "Context:" in out


def test_parse_error_annotation_ignores_non_parse():
    """If the msg has no 'at position N', the annotator passes through."""
    from tsunami.tools.emit_design import _annotate_parse_error
    msg = "validation errors: foo missing"
    out = _annotate_parse_error(msg, '{"x": 1}')
    assert out == msg  # unchanged


def test_normaliser_strips_line_comments():
    """Round I 2026-04-20: wave emitted JSON with `// comment` lines
    (JS-style). JSON rejects those. Normaliser strips them."""
    bad = '''{
        // player stats
        "hp": 10,
        // mana
        "mp": 5
    }'''
    out, changed = _normalise_qwen_json(bad)
    assert changed is True
    assert json.loads(out) == {"hp": 10, "mp": 5}


def test_normaliser_strips_line_comments_preserves_strings():
    """Line-comment strip must NOT touch // inside string values.
    'url': 'https://foo' must survive."""
    bad = '{"url": "https://example.com", x: 1}'  # x: unquoted, no comment
    out, changed = _normalise_qwen_json(bad)
    assert changed is True
    parsed = json.loads(out)
    assert parsed["url"] == "https://example.com"
    assert parsed["x"] == 1


def test_normaliser_handles_hyphenated_keys():
    """Qwen sometimes emits kebab-case-keys that need quoting."""
    bad = '{ mode-3d: true, max-speed: 120 }'
    out, changed = _normalise_qwen_json(bad)
    assert changed is True
    assert json.loads(out) == {"mode-3d": True, "max-speed": 120}


def test_parse_error_annotation_out_of_range_safe():
    """Don't crash if position exceeds raw_json length."""
    from tsunami.tools.emit_design import _annotate_parse_error
    msg = "Expected '}' at position 9999"
    out = _annotate_parse_error(msg, '{"x": 1}')
    # Should not raise; returns the original or a safe-annotated version
    assert isinstance(out, str)


def test_normaliser_fixes_single_quoted_string_values():
    """Docstring promises single-quoted → double-quoted. Test proves
    the regex actually covers that case. Qwen sometimes emits
    `name: 'player'` (JS-style string literals)."""
    bad = "{\"entities\": [{\"name\": 'player', \"tags\": ['hero', 'main']}]}"
    out, changed = _normalise_qwen_json(bad)
    assert changed is True, f"normaliser didn't change: {out}"
    parsed = json.loads(out)
    assert parsed["entities"][0]["name"] == "player"
    assert parsed["entities"][0]["tags"] == ["hero", "main"]


def test_normaliser_strips_block_comments():
    """`/* ... */` block comments must be stripped too — the
    `_strip_line_comments` helper supports both forms. Qwen occasionally
    emits block comments in nested configs."""
    bad = '{"scenes": [/* main scene */ {"name": "main"}], "mechanics": []}'
    out, changed = _normalise_qwen_json(bad)
    assert changed is True
    parsed = json.loads(out)
    assert parsed["scenes"][0]["name"] == "main"
    assert parsed["mechanics"] == []


def test_normaliser_block_comments_dont_mangle_division_in_strings():
    """Don't mistake /text/ inside a string value for a block-comment
    opening — the strip walker must respect in_str state."""
    bad = '{"path": "src/main.ts", "glob": "**/*.tsx"}'
    # This is valid JSON — passthrough, no change
    out, changed = _normalise_qwen_json(bad)
    assert changed is False, f"passthrough broke: {out}"
    assert json.loads(out) == {"path": "src/main.ts", "glob": "**/*.tsx"}


def test_normaliser_is_module_level_not_nested():
    """Round K cleanup: _normalise_qwen_json was extracted from the
    emit_design() function body to module level so tests exercise the
    same code path as production. Guard against accidental re-nesting.

    A re-nested helper would (a) invalidate this test file's import,
    (b) let test-fixture drift recur (the Round K failure mode where
    the test-side mirror missed block-comment handling)."""
    import inspect
    from tsunami.tools import emit_design as _mod
    # Module-level symbol must exist and be a function
    assert callable(_mod._normalise_qwen_json)
    assert callable(_mod._strip_json_comments)
    # Source of the outer emit_design() must NOT redefine _normalise_qwen_json
    # — if it does, the module-level one is dead code and tests would
    # stop reflecting live behaviour.
    outer_src = inspect.getsource(_mod.emit_design)
    assert "def _normalise_qwen_json" not in outer_src, (
        "emit_design() re-nested _normalise_qwen_json — module-level "
        "extraction regressed. Tests would stop reflecting live code."
    )
    # And confirm the outer still USES the normaliser (either reference
    # or direct call — the name must appear in the body).
    assert "_normalise_qwen_json" in outer_src, (
        "emit_design() doesn't reference _normalise_qwen_json anywhere — "
        "the normaliser is orphaned from the production path."
    )


def main():
    tests = [
        test_passthrough_valid_json,
        test_fixes_unquoted_keys,
        test_fixes_trailing_comma_in_array,
        test_fixes_trailing_comma_in_object,
        test_fixes_combined_unquoted_and_trailing,
        test_qwen_live_case_camera_config,
        test_returns_original_on_unfixable,
        test_nested_doesnt_mangle_strings,
        test_normaliser_strips_line_comments,
        test_normaliser_strips_line_comments_preserves_strings,
        test_normaliser_handles_hyphenated_keys,
        test_parse_error_annotation_pinpoints_position,
        test_parse_error_annotation_ignores_non_parse,
        test_parse_error_annotation_out_of_range_safe,
        test_normaliser_fixes_single_quoted_string_values,
        test_normaliser_strips_block_comments,
        test_normaliser_block_comments_dont_mangle_division_in_strings,
        test_normaliser_is_module_level_not_nested,
    ]
    failed = []
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except AssertionError as e:
            print(f"FAIL  {t.__name__}: {e}")
            failed.append(t.__name__)
        except Exception as e:
            print(f"ERROR {t.__name__}: {type(e).__name__}: {e}")
            failed.append(t.__name__)
    print()
    if failed:
        print(f"RESULT: {len(failed)}/{len(tests)} failed: {failed}")
        sys.exit(1)
    print(f"RESULT: {len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
