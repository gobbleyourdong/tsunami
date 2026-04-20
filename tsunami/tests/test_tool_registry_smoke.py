"""Smoke tests for the tool registry — every core tool must load,
have a valid schema, and register under its expected name.

A tool module failing at import time, or having a schema that trips
JSON validation, silently breaks the agent loop — the drone calls
the tool by name and gets "unknown tool" errors with no good trace.
This is a cheap belt-and-suspenders suite: no subprocess work, just
import + schema shape.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO))

from tsunami.tools import build_registry  # noqa: E402
from tsunami.config import TsunamiConfig  # noqa: E402


CORE_TOOLS = (
    "emit_design",
    "file_read",
    "file_write",
    "file_edit",
    "shell_exec",
    "message_result",
    "message_chat",
    "project_init",
    "generate_image",
)


def _registry():
    cfg = TsunamiConfig(workspace_dir="/tmp/tool_smoke_test")
    return build_registry(cfg)


def test_all_core_tools_registered():
    reg = _registry()
    for name in CORE_TOOLS:
        assert reg.get(name) is not None, f"core tool missing from registry: {name}"


def test_all_core_tools_have_valid_schema():
    """Each tool's .schema() must return an OpenAI-flavored function
    schema: `{"type": "function", "function": {"name": ..., ...}}`."""
    reg = _registry()
    for name in CORE_TOOLS:
        tool = reg.get(name)
        if tool is None:
            continue
        schema = tool.schema()
        assert schema.get("type") == "function", (
            f"{name} schema missing 'type: function': {schema}"
        )
        fn = schema.get("function", {})
        assert fn.get("name") == name, (
            f"{name} schema name mismatch: {fn.get('name')}"
        )
        params = fn.get("parameters", {})
        assert params.get("type") == "object", (
            f"{name} parameters.type missing"
        )


def test_emit_design_schema_matches_fix_21_contract():
    """Fix #21 contract: emit_design accepts design AND project_name."""
    reg = _registry()
    tool = reg.get("emit_design")
    schema = tool.schema()
    props = schema.get("function", {}).get("parameters", {}).get("properties", {})
    assert "design" in props
    assert "project_name" in props
    required = schema.get("function", {}).get("parameters", {}).get("required", [])
    # project_name must be required for Fix #21 hoist-check to run
    assert "project_name" in required, (
        f"project_name must be required to trigger Fix #21 hoist; got {required}"
    )


def test_file_write_schema_matches_fix_9_widening():
    """Fix #9: file_write content field accepts string/object/array
    (wave often emits design JSON as a dict arg to file_write)."""
    reg = _registry()
    tool = reg.get("file_write")
    schema = tool.schema()
    props = schema.get("function", {}).get("parameters", {}).get("properties", {})
    content_type = props.get("content", {}).get("type")
    # Should be a list like ["string", "object", "array"]
    assert isinstance(content_type, list), (
        f"Fix #9 regression: file_write content.type should be list, got {content_type}"
    )
    for t in ("string", "object", "array"):
        assert t in content_type, (
            f"file_write content.type missing {t!r}; got {content_type}"
        )


def test_registry_has_no_name_collisions():
    """Two tools sharing the same name would cause nondeterministic
    dispatch. Registry should expose unique names."""
    reg = _registry()
    names = reg.names()
    assert len(names) == len(set(names)), (
        f"registry has duplicate names: {names}"
    )


def test_registry_names_match_individual_schemas():
    """For each registered name, the corresponding tool's schema must
    declare that same name. Mismatches silently break the drone."""
    reg = _registry()
    for name in reg.names():
        tool = reg.get(name)
        if tool is None:
            continue
        schema_name = tool.schema().get("function", {}).get("name")
        assert schema_name == name, (
            f"registry says {name!r} but tool.schema() says {schema_name!r}"
        )


def main():
    tests = [
        test_all_core_tools_registered,
        test_all_core_tools_have_valid_schema,
        test_emit_design_schema_matches_fix_21_contract,
        test_file_write_schema_matches_fix_9_widening,
        test_registry_has_no_name_collisions,
        test_registry_names_match_individual_schemas,
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
