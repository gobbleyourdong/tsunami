"""Tests for the offline morning report aggregator."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO))

from tsunami.harness.morning_report import (  # noqa: E402
    section_coverage, section_stall, section_new_gaps,
    section_cold_start, build_report, render_md,
)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def test_coverage_counts_exits():
    with tempfile.TemporaryDirectory() as td:
        runs = Path(td) / "runs.jsonl"
        _write_jsonl(runs, [
            {"exit_reason": "message_result", "row": {"expected_scaffold": "gamedev"}},
            {"exit_reason": "timeout",        "row": {"expected_scaffold": "gamedev"}},
            {"exit_reason": "error:foo",      "row": {"expected_scaffold": "react-app"}},
            {"exit_reason": "message_result", "row": {"expected_scaffold": "react-app"}},
        ])
        c = section_coverage(runs)
        assert c["total"] == 4
        assert c["delivered"] == 2
        assert c["timeout"] == 1
        assert c["error"] == 1
        assert c["by_expected_scaffold"]["gamedev"] == 2


def test_stall_reads_routing_telemetry():
    from tsunami import routing_telemetry as rt
    with tempfile.TemporaryDirectory() as td:
        rt.enable(log_dir=td)
        try:
            rt.log_pick("scaffold", "test", "gamedev", default="react-build")
            rt.log_pick("scaffold", "vague", "react-build", default="react-build",
                        match_source="default")
        finally:
            rt.disable()
        stall = section_stall(Path(td))
        assert "scaffold" in stall
        assert stall["scaffold"]["total"] == 2
        assert stall["scaffold"]["default_count"] == 1


def test_new_gaps_skips_style_on_gamedev_heavy():
    """Style fall-through on gamedev runs is expected (F-A3 gates it)."""
    stall = {
        "style": {"total": 5, "default_count": 5, "default_rate": 1.0,
                  "top_keywords": []},
        "scaffold": {"total": 5, "default_count": 0, "default_rate": 0.0,
                     "top_keywords": [("gamedev", 5)]},
    }
    gamedev_coverage = {
        "total": 5,
        "by_expected_scaffold": {"gamedev": 5},
    }
    gaps = section_new_gaps(stall, gamedev_coverage)
    # Should have skipped style despite its 100% default rate
    assert not any(g["domain"] == "style" for g in gaps), \
        f"style gap should be skipped on gamedev-heavy runs, got {gaps}"


def test_new_gaps_flags_style_on_non_gamedev():
    """On react-app / dashboard runs, style fall-throughs ARE real gaps."""
    stall = {
        "style": {"total": 10, "default_count": 8, "default_rate": 0.8,
                  "top_keywords": []},
    }
    web_coverage = {
        "total": 10,
        "by_expected_scaffold": {"react-app": 10},
    }
    gaps = section_new_gaps(stall, web_coverage)
    assert any(g["domain"] == "style" for g in gaps), \
        f"style gap SHOULD flag on web-heavy runs, got {gaps}"


def test_cold_start_segregates_by_threshold():
    from tsunami import doctrine_history as dh
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "doctrine_history.jsonl"
        dh.enable(path)
        try:
            # Cold-start doctrine (< 30 picks)
            for _ in range(5):
                dh.log_pick("genre", "stealth")
            # Plateau doctrine (≥ 30 picks)
            for _ in range(30):
                dh.log_pick("genre", "platformer")
        finally:
            dh.disable()
        cs = section_cold_start(Path(td))
        cs_genre = dict(cs["cold_start"]["genre"])
        plat_genre = dict(cs["plateau"]["genre"])
        assert "stealth" in cs_genre
        assert cs_genre["stealth"] == 5
        assert "platformer" in plat_genre
        assert plat_genre["platformer"] == 30
        assert "platformer" not in cs_genre


def test_end_to_end_build_and_render():
    """The whole pipeline: empty-ish root, should produce a valid markdown
    document without crashing."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "overnight"
        root.mkdir()
        telemetry = root / "telemetry"
        telemetry.mkdir()
        probes = root / "probes"
        probes.mkdir()
        rep = build_report(root, telemetry, probes)
        md = render_md(rep)
        # Sanity: all sections present
        for section in ("§1 Coverage", "§2 Stall", "§3 Retractions",
                        "§4 Cold-start", "§5 Force-miss", "§6 Probe",
                        "§7 Budget", "§8 New corpus gaps"):
            assert section in md, f"missing section: {section}"


def main():
    tests = [
        test_coverage_counts_exits,
        test_stall_reads_routing_telemetry,
        test_new_gaps_skips_style_on_gamedev_heavy,
        test_new_gaps_flags_style_on_non_gamedev,
        test_cold_start_segregates_by_threshold,
        test_end_to_end_build_and_render,
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
