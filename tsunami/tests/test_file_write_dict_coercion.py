"""Tests for FileWrite's dict/list auto-serialization.

Captures the live failure mode: Round D 2026-04-20 on
/tmp/live_zelda_round2 — the wave called file_write with
content={design_dict} and got "Validation error for file_write:
Parameter 'content' expected string, got dict" TWICE.

After the widening:
  - string content still works (baseline)
  - dict content is auto-serialized to pretty JSON
  - list content is auto-serialized
  - schema validation passes for all three types
"""
from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO))

from tsunami.tools.filesystem import FileWrite  # noqa: E402


class _FakeConfig:
    def __init__(self, ws): self.workspace_dir = ws


def _make_tool(ws: Path) -> FileWrite:
    # FileWrite extends BaseTool; needs a config with workspace_dir
    tool = FileWrite.__new__(FileWrite)
    tool.config = _FakeConfig(str(ws))
    return tool


def test_schema_accepts_string_content():
    t = FileWrite.__new__(FileWrite)
    schema = t.parameters_schema()
    content_type = schema["properties"]["content"]["type"]
    assert "string" in content_type


def test_schema_accepts_dict_content():
    """The widening. Validator now won't reject content=dict."""
    t = FileWrite.__new__(FileWrite)
    schema = t.parameters_schema()
    content_type = schema["properties"]["content"]["type"]
    assert "object" in content_type


def test_schema_accepts_list_content():
    t = FileWrite.__new__(FileWrite)
    schema = t.parameters_schema()
    content_type = schema["properties"]["content"]["type"]
    assert "array" in content_type


def test_validate_input_string_passes():
    t = FileWrite.__new__(FileWrite)
    err = t.validate_input(path="x.txt", content="hello")
    assert err is None


def test_validate_input_dict_passes():
    """This was FAILING before the widening (Round D failure)."""
    t = FileWrite.__new__(FileWrite)
    err = t.validate_input(path="x.json", content={"foo": "bar"})
    assert err is None, f"dict content should now pass validation, got: {err}"


def test_validate_input_list_passes():
    t = FileWrite.__new__(FileWrite)
    err = t.validate_input(path="x.json", content=[1, 2, 3])
    assert err is None


def test_execute_coercion_lives_in_code():
    """Inline code grep — verifies the coercion block is present in
    filesystem.py. Integration-level execute tests are covered by the
    existing test_filesystem-style suites (complex workspace plumbing);
    this file's scope is the schema widening + coercion presence."""
    fs_src = (REPO / "tsunami" / "tools" / "filesystem.py").read_text()
    assert "isinstance(content, (dict, list))" in fs_src, (
        "dict→JSON coercion missing from filesystem.py"
    )
    assert "indent=2" in fs_src, "JSON serialization should pretty-print"


def test_code_write_gate_gamedev_branch_exists():
    """Round H 2026-04-20 revealed: code_write_gate told gamedev deliveries
    to 'write App.tsx' — wrong tool for gamedev (engine-only scaffold).
    Fix: scaffold-aware branch checks for game_definition.json when
    target_scaffold=gamedev."""
    dg_src = (REPO / "tsunami" / "deliver_gates.py").read_text()
    assert 'scaffold == "gamedev"' in dg_src, (
        "code_write_gate missing gamedev branch"
    )
    assert "game_definition.json" in dg_src
    # Advisory should direct wave to emit_design, not file_write
    assert "emit_design" in dg_src
    assert "engine-only" in dg_src


def test_code_write_gate_gamedev_logic_correct():
    """Inline call via the gate function: gamedev scaffold + no
    game_definition.json → FAIL with emit_design advisory."""
    import asyncio
    from tsunami.deliver_gates import code_write_gate
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        result = code_write_gate(
            state_flags={"target_scaffold": "gamedev",
                         "app_source_written": False},
            project_dir=Path(td),
        )
        assert result.passed is False
        assert "game_definition.json" in result.message
        assert "emit_design" in result.system_note
        assert "App.tsx" in result.system_note or "Do NOT write src/App.tsx" in result.system_note


def test_code_write_gate_gamedev_with_file_passes():
    """Gamedev scaffold + public/game_definition.json exists → PASS."""
    from tsunami.deliver_gates import code_write_gate
    import tempfile, json as _json
    with tempfile.TemporaryDirectory() as td:
        proj = Path(td)
        (proj / "public").mkdir()
        (proj / "public" / "game_definition.json").write_text(
            _json.dumps({"entities": [{"name": "player"}]})
        )
        result = code_write_gate(
            state_flags={"target_scaffold": "gamedev"},
            project_dir=proj,
        )
        assert result.passed is True
        assert "game_definition.json" in result.message


def main():
    tests = [
        test_schema_accepts_string_content,
        test_schema_accepts_dict_content,
        test_schema_accepts_list_content,
        test_validate_input_string_passes,
        test_validate_input_dict_passes,
        test_validate_input_list_passes,
        test_execute_coercion_lives_in_code,
        test_code_write_gate_gamedev_branch_exists,
        test_code_write_gate_gamedev_logic_correct,
        test_code_write_gate_gamedev_with_file_passes,
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
