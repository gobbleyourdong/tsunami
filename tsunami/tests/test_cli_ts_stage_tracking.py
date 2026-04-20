"""Tests for the cli.ts stage-tracking improvement (Fix #11).

Round D.4 captured: emit_design returned `stage=fatal: object is not
iterable` — the outer catch() at cli.ts line 69 ate a validate() error
and reported it as a generic control-flow failure, which misled the
wave into thinking cli.ts itself was broken.

Fix #11: wrap validate() in an explicit try/catch so iteration errors
surface as stage=validate with the real exception message. The outer
catch now only fires for actual control-flow bugs in cli.ts itself,
which should be rare.

These tests are source-inspection — verify the TS code has the right
shape. A real unit test would require Node + tsx, which we don't
spawn here.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).parent.parent.parent


def test_cli_ts_wraps_validate_in_try():
    cli_src = (REPO / "scaffolds" / "engine" / "src" / "design" / "cli.ts").read_text()
    # The fix: validate() call should live inside a try block
    assert "try {\n    result = validate(design)" in cli_src, (
        "cli.ts should wrap validate() in an explicit try — otherwise "
        "iteration errors from validate surface as stage=fatal (Round D.4)"
    )


def test_cli_ts_validate_error_surfaces_as_validate_stage():
    cli_src = (REPO / "scaffolds" / "engine" / "src" / "design" / "cli.ts").read_text()
    # After the fix, an error thrown from validate() should emit
    # stage='validate', not stage='fatal'.
    # Find the validate try block and check it emits stage='validate'.
    try_idx = cli_src.find("try {\n    result = validate(design)")
    assert try_idx > 0
    # Next ~400 chars should contain writeErr with stage:'validate'
    window = cli_src[try_idx:try_idx + 600]
    assert "stage: 'validate'" in window
    # And a useful message that hints at the root cause shape
    assert "validator threw" in window or "malformed" in window


def test_cli_ts_fatal_catch_is_backstop_only():
    """The outer .catch() block at the end of cli.ts should now
    describe itself as a backstop for cli.ts control-flow bugs, NOT
    as the primary error surface."""
    cli_src = (REPO / "scaffolds" / "engine" / "src" / "design" / "cli.ts").read_text()
    assert "backstop" in cli_src or "last-resort" in cli_src or "control-flow error" in cli_src


def test_cli_ts_still_parses_shape():
    """Smoke — the .ts source still has main(), validate(), compile()
    references and standard imports. Not a full parse but catches
    obvious damage."""
    cli_src = (REPO / "scaffolds" / "engine" / "src" / "design" / "cli.ts").read_text()
    for marker in (
        "import { validate }",
        "import { compile }",
        "async function main",
        # The fix changed `const result = validate(design)` to
        # `let result` + `result = validate(design)` inside a try.
        "result = validate(design)",
        "game = compile(result.design)",
        "process.stdout.write",
        "process.exit",
    ):
        assert marker in cli_src, f"cli.ts missing expected shape: {marker!r}"


def main():
    tests = [
        test_cli_ts_wraps_validate_in_try,
        test_cli_ts_validate_error_surfaces_as_validate_stage,
        test_cli_ts_fatal_catch_is_backstop_only,
        test_cli_ts_still_parses_shape,
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
