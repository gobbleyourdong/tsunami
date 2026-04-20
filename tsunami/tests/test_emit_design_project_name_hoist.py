"""Gap #21 (Round N 2026-04-20): emit_design tool rejects calls where
project_name is nested inside the design dict rather than provided as
a sibling tool-call parameter.

Round N iters 6 and 7 both fired emit_design with `{design: {project_name:
"zelda_overworld", meta: {...}, ...}}` (project_name nested). The tool's
validate_input required `project_name` as a top-level kwarg, rejecting
with "Missing required parameter: 'project_name'" before execute ever ran.

The wave emitted nested project_name because plan_scaffolds/gamedev.md's
design example shows project_name as a top-level JSON key — the model
internalizes that as "part of the design blob" rather than a tool-call
sibling.

Fix #21: override validate_input in EmitDesignTool to hoist
design.project_name into kwargs.project_name if missing. Execute
fallback as defense-in-depth. Two new tests lock:
- Nested project_name is hoisted
- Top-level project_name still works (no regression)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO))

from tsunami.tools.emit_design import EmitDesignTool  # noqa: E402


class _FakeConfig:
    workspace_dir = "/tmp/emit_hoist_test"


def test_nested_project_name_hoisted_on_validate():
    """Wave emits project_name inside design — validator hoists it."""
    tool = EmitDesignTool(_FakeConfig())
    design = {
        "project_name": "zelda_overworld",
        "meta": {"title": "X", "shape": "action", "vibe": []},
        "archetypes": {},
        "mechanics": [],
    }
    # No top-level project_name kwarg
    err = tool.validate_input(design=design)
    assert err is None, (
        f"validate_input should hoist nested project_name, got err: {err}"
    )


def test_top_level_project_name_still_works():
    """Canonical call shape (design + project_name as siblings) continues
    to validate — Fix #21 is additive, not a replacement."""
    tool = EmitDesignTool(_FakeConfig())
    design = {
        "meta": {"title": "X", "shape": "action", "vibe": []},
        "archetypes": {},
        "mechanics": [],
    }
    err = tool.validate_input(design=design, project_name="clean_name")
    assert err is None, f"canonical shape should pass: {err}"


def test_nested_project_name_from_json_string_design():
    """Wave sometimes passes design as a JSON STRING (tool-arg stringification).
    Hoist must also work on the stringified path."""
    tool = EmitDesignTool(_FakeConfig())
    design_str = json.dumps({
        "project_name": "zelda_overworld",
        "meta": {"title": "X", "shape": "action", "vibe": []},
        "archetypes": {},
    })
    err = tool.validate_input(design=design_str)
    assert err is None, f"stringified design should hoist project_name: {err}"


def test_no_project_name_anywhere_still_errors():
    """If project_name is missing from BOTH top-level AND nested, the
    error still surfaces — we're hoisting, not inventing."""
    tool = EmitDesignTool(_FakeConfig())
    design = {"meta": {}, "archetypes": {}}
    err = tool.validate_input(design=design)
    assert err is not None
    assert "project_name" in err


def test_whitespace_nested_project_name_rejected():
    """Nested project_name that's blank/whitespace doesn't get hoisted —
    empty strings are as good as missing."""
    tool = EmitDesignTool(_FakeConfig())
    design = {"project_name": "   ", "meta": {}, "archetypes": {}}
    err = tool.validate_input(design=design)
    assert err is not None  # still rejected


def test_top_level_wins_over_nested():
    """If both top-level and nested are present, top-level wins
    (more specific, presumably intentional)."""
    tool = EmitDesignTool(_FakeConfig())
    design = {
        "project_name": "nested_name",
        "meta": {"title": "X", "shape": "action", "vibe": []},
        "archetypes": {},
    }
    # No error because top-level kwarg takes precedence
    err = tool.validate_input(design=design, project_name="top_level_name")
    assert err is None


def main():
    tests = [
        test_nested_project_name_hoisted_on_validate,
        test_top_level_project_name_still_works,
        test_nested_project_name_from_json_string_design,
        test_no_project_name_anywhere_still_errors,
        test_whitespace_nested_project_name_rejected,
        test_top_level_wins_over_nested,
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
