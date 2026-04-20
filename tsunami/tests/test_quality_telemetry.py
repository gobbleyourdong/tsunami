"""Tests for quality_telemetry — per-delivery rich telemetry."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO))

from tsunami import quality_telemetry as qt  # noqa: E402


def test_disabled_noop():
    qt.disable()
    with tempfile.TemporaryDirectory() as td:
        qt._DEFAULT_PATH = Path(td) / "q.jsonl"
        qt.log_delivery(prompt="build a landing", tool_history=["file_write"])
        assert not qt._DEFAULT_PATH.exists()


def test_enabled_writes_row():
    with tempfile.TemporaryDirectory() as td:
        log = Path(td) / "q.jsonl"
        qt.enable(log)
        try:
            qt.log_delivery(
                run_id="r1",
                project_dir=td,
                prompt="build a landing page",
                scaffold="landing",
                style="shadcn_startup",
                tool_history=["file_write", "shell_exec", "file_write", "message_result"],
                iter_count=8,
                time_to_deliver_s=123.4,
                build_pass_count=1,
                vision_pass=True,
            )
        finally:
            qt.disable()
        assert log.is_file()
        row = json.loads(log.read_text())
        assert row["run_id"] == "r1"
        assert row["scaffold"] == "landing"
        assert row["style"] == "shadcn_startup"
        assert row["tool_count"] == 4
        assert row["file_write_count"] == 2
        assert row["shell_exec_count"] == 1
        assert row["vision_pass"] is True
        assert len(row["tool_sequence_hash"]) == 8
        assert row["direction_verdict"]["passed"] is None


def test_tool_sequence_hash_stable():
    h1 = qt.tool_sequence_hash(["a", "b", "c"])
    h2 = qt.tool_sequence_hash(["a", "b", "c"])
    h3 = qt.tool_sequence_hash(["a", "b", "d"])
    assert h1 == h2
    assert h1 != h3
    assert len(h1) == 8


def test_parse_direction_verdict_pass():
    v = qt.parse_direction_set_verdict("PASS\nScore: 9/10\nAll questions answered yes.")
    assert v["passed"] is True
    assert v["score"] == "9/10"


def test_parse_direction_verdict_fail():
    v = qt.parse_direction_set_verdict(
        "FAIL\nq1: no (palette violation)\nq3: no (four fonts visible)"
    )
    assert v["passed"] is False
    # The regex finds q# tokens; the exact list order depends on regex
    assert "1" in v["flagged_questions"] or "3" in v["flagged_questions"]


def test_measure_app_tsx_missing():
    with tempfile.TemporaryDirectory() as td:
        stats = qt.measure_app_tsx(Path(td))
        assert stats == {}


def test_measure_app_tsx_present():
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "src"
        src.mkdir()
        app = src / "App.tsx"
        app.write_text("import './index.css';\n\nexport default function App() {\n  return null;\n}\n")
        stats = qt.measure_app_tsx(Path(td))
        assert stats["bytes"] > 50
        assert stats["lines"] >= 5


def test_quality_report_aggregates():
    with tempfile.TemporaryDirectory() as td:
        log = Path(td) / "q.jsonl"
        qt.enable(log)
        try:
            # 3 deliveries: 2 build-pass/vision-pass, 1 build-fail
            qt.log_delivery(run_id="a", prompt="x", scaffold="landing",
                            tool_history=["file_write", "shell_exec", "message_result"],
                            iter_count=5, time_to_deliver_s=100.0,
                            build_pass_count=1, vision_pass=True)
            qt.log_delivery(run_id="b", prompt="y", scaffold="dashboard",
                            tool_history=["file_write", "shell_exec", "file_edit",
                                          "shell_exec", "message_result"],
                            iter_count=10, time_to_deliver_s=200.0,
                            build_pass_count=2, vision_pass=True)
            qt.log_delivery(run_id="c", prompt="z", scaffold="gamedev",
                            tool_history=["generate_image"]*6 + ["file_write", "message_result"],
                            iter_count=15, time_to_deliver_s=300.0,
                            build_pass_count=0, build_fail_count=1,
                            vision_pass=False)
        finally:
            qt.disable()
        rep = qt.quality_report(log)
        assert rep["total_deliveries"] == 3
        assert rep["delivery_health"]["build_pass_rate"] == 2/3
        assert rep["delivery_health"]["vision_pass_rate"] == 2/3
        assert rep["loop_density"]["median_iter_count"] == 10
        # The 'c' run had 6 generate_image calls — flagged as image-heavy
        assert rep["generation_arc"]["image_heavy_runs"] == 1


def main():
    tests = [
        test_disabled_noop,
        test_enabled_writes_row,
        test_tool_sequence_hash_stable,
        test_parse_direction_verdict_pass,
        test_parse_direction_verdict_fail,
        test_measure_app_tsx_missing,
        test_measure_app_tsx_present,
        test_quality_report_aggregates,
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
