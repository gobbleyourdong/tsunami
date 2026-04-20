"""Tests for F-C1 routing telemetry + F-C4 force-miss ledger.

Zero-dependency self-check: creates a tmpdir, enable()s telemetry
pointing at it, writes synthetic events, verifies the aggregators.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO))

from tsunami import routing_telemetry as rt  # noqa: E402


def test_disabled_is_noop():
    rt.disable()
    with tempfile.TemporaryDirectory() as td:
        rt._DEFAULT_LOG_DIR = Path(td)
        rt.log_pick("scaffold", "build a dashboard", "dashboard", "react-build")
        assert not (Path(td) / "routing.jsonl").exists(), \
            "telemetry must not write when disabled"


def test_enable_writes_row():
    with tempfile.TemporaryDirectory() as td:
        rt.enable(log_dir=td)
        try:
            rt.log_pick("scaffold", "build a dashboard", "dashboard", "react-build")
            rt.log_pick("scaffold", "some random prompt", "react-build", "react-build",
                        match_source="default")
            log = Path(td) / "routing.jsonl"
            assert log.is_file()
            lines = log.read_text().strip().splitlines()
            assert len(lines) == 2
            ev0 = json.loads(lines[0])
            assert ev0["domain"] == "scaffold"
            assert ev0["winner"] == "dashboard"
            assert ev0["match_source"] == "keyword"
            assert len(ev0["task_hash"]) == 12
        finally:
            rt.disable()


def test_stall_report_aggregates():
    with tempfile.TemporaryDirectory() as td:
        rt.enable(log_dir=td)
        try:
            # 3 scaffold picks: 2 dashboard, 1 default
            rt.log_pick("scaffold", "build a dashboard", "dashboard", "react-build")
            rt.log_pick("scaffold", "admin panel", "dashboard", "react-build")
            rt.log_pick("scaffold", "vague prompt", "react-build", "react-build",
                        match_source="default")
            # 2 style picks: 1 match, 1 default
            rt.log_pick("style", "brutalist shop", "brutalist_web", "")
            rt.log_pick("style", "whatever", "", "", match_source="default")

            report = rt.stall_report(log_dir=td)
            assert "scaffold" in report
            assert report["scaffold"]["total"] == 3
            assert report["scaffold"]["default_count"] == 1
            assert abs(report["scaffold"]["default_rate"] - 1/3) < 0.01
            assert ("dashboard", 2) in report["scaffold"]["top_keywords"]

            assert report["style"]["total"] == 2
            # default="" for style means "" is the default; both empty and
            # missing-match count as defaults.
            assert report["style"]["default_count"] >= 1
        finally:
            rt.disable()


def test_force_miss_report():
    with tempfile.TemporaryDirectory() as td:
        rt.enable(log_dir=td)
        try:
            rt.log_force_miss("message_result", "file_read", iteration=12)
            rt.log_force_miss("message_result", "file_read", iteration=15)
            rt.log_force_miss("message_result", "file_write", iteration=18)
            rep = rt.force_miss_report(log_dir=td)
            assert rep["total"] == 3
            top = dict(rep["top_pairs"])
            assert top[("message_result", "file_read")] == 2
            assert top[("message_result", "file_write")] == 1
        finally:
            rt.disable()


def test_non_blocking_on_disk_error(monkeypatch=None):
    """If Path operations raise, log_pick silently no-ops."""
    rt.enable(log_dir="/nonexistent/absolutely/forbidden/path/xyzzy")
    try:
        # Should NOT raise — this is the critical property.
        rt.log_pick("scaffold", "task", "winner", "default")
    finally:
        rt.disable()


def main():
    tests = [
        test_disabled_is_noop,
        test_enable_writes_row,
        test_stall_report_aggregates,
        test_force_miss_report,
        test_non_blocking_on_disk_error,
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
