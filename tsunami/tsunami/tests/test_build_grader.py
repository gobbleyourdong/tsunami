"""Tests for Expansion support: Build grader + pattern tracker.

Verifies:
- BuildScore scoring and summary
- BuildTracker persistence, averages, patterns, trends
- Scaffold stats aggregation
- Systemic failure detection
"""

import json
import tempfile
from pathlib import Path

from tsunami.build_grader import (
    BuildScore,
    BuildTracker,
    FailurePattern,
)


class TestBuildScore:
    """Individual build scoring."""

    def test_total_score(self):
        s = BuildScore(prompt="test", compiles=1, renders=1, functional=2, visual=2, assets=1)
        assert s.total == 7

    def test_max_score(self):
        s = BuildScore(prompt="test", compiles=1, renders=1, functional=3, visual=3, assets=3)
        assert s.total == 11  # intentional: 1+1+3+3+3=11 — PLAN says /10 but we keep raw

    def test_zero_score(self):
        s = BuildScore(prompt="test")
        assert s.total == 0

    def test_summary_format(self):
        s = BuildScore(prompt="test", compiles=1, renders=1, functional=2, visual=2, assets=1, iterations=15, duration_s=45.2)
        summary = s.summary()
        assert "7/10" in summary
        assert "15 iters" in summary


class TestBuildTracker:
    """Build tracking across expansion."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_save_and_load(self):
        tracker = BuildTracker(self.tmpdir)
        tracker.add_score(BuildScore(prompt="build a weather app", scaffold="react-app", compiles=1, renders=1))
        tracker2 = BuildTracker(self.tmpdir)
        tracker2.load()
        assert len(tracker2.scores) == 1
        assert tracker2.scores[0].prompt == "build a weather app"

    def test_average_score(self):
        tracker = BuildTracker(self.tmpdir)
        tracker.add_score(BuildScore(prompt="a", compiles=1, renders=1, functional=2, visual=2, assets=2))  # 8
        tracker.add_score(BuildScore(prompt="b", compiles=0, renders=1, functional=1, visual=1, assets=1))  # 4
        assert tracker.average_score() == 6.0

    def test_average_iterations(self):
        tracker = BuildTracker(self.tmpdir)
        tracker.add_score(BuildScore(prompt="a", iterations=10))
        tracker.add_score(BuildScore(prompt="b", iterations=20))
        assert tracker.average_iterations() == 15.0

    def test_pattern_tracking(self):
        tracker = BuildTracker(self.tmpdir)
        tracker.add_score(BuildScore(prompt="a", failures=["blank_page"]))
        tracker.add_score(BuildScore(prompt="b", failures=["blank_page"]))
        tracker.add_score(BuildScore(prompt="c", failures=["blank_page"]))
        assert tracker.patterns["blank_page"].count == 3

    def test_systemic_failures(self):
        tracker = BuildTracker(self.tmpdir)
        for i in range(4):
            tracker.add_score(BuildScore(prompt=f"p{i}", failures=["css_broken"]))
        systemic = tracker.systemic_failures(threshold=3)
        assert len(systemic) == 1
        assert systemic[0].name == "css_broken"

    def test_no_systemic_below_threshold(self):
        tracker = BuildTracker(self.tmpdir)
        tracker.add_score(BuildScore(prompt="a", failures=["rare_bug"]))
        assert len(tracker.systemic_failures()) == 0


class TestScaffoldStats:
    """Per-scaffold performance breakdown."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_scaffold_stats(self):
        tracker = BuildTracker(self.tmpdir)
        tracker.add_score(BuildScore(prompt="a", scaffold="react-app", compiles=1, renders=1, functional=2, visual=2, assets=2))
        tracker.add_score(BuildScore(prompt="b", scaffold="react-app", compiles=1, renders=1, functional=3, visual=3, assets=3))
        tracker.add_score(BuildScore(prompt="c", scaffold="dashboard", compiles=0, renders=0))
        stats = tracker.scaffold_stats()
        assert "react-app" in stats
        assert "dashboard" in stats
        assert stats["react-app"]["builds"] == 2
        assert stats["react-app"]["avg_score"] > stats["dashboard"]["avg_score"]

    def test_empty_stats(self):
        tracker = BuildTracker(self.tmpdir)
        assert tracker.scaffold_stats() == {}


class TestScoreTrend:
    """Score trend detection."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_insufficient_data(self):
        tracker = BuildTracker(self.tmpdir)
        tracker.add_score(BuildScore(prompt="a", compiles=1))
        assert tracker.score_trend() == "insufficient_data"

    def test_improving_trend(self):
        tracker = BuildTracker(self.tmpdir)
        # Early: low scores
        for i in range(5):
            tracker.add_score(BuildScore(prompt=f"early{i}", compiles=0, renders=0))
        # Late: high scores
        for i in range(5):
            tracker.add_score(BuildScore(prompt=f"late{i}", compiles=1, renders=1, functional=3, visual=3, assets=3))
        assert tracker.score_trend() == "improving"

    def test_declining_trend(self):
        tracker = BuildTracker(self.tmpdir)
        for i in range(5):
            tracker.add_score(BuildScore(prompt=f"good{i}", compiles=1, renders=1, functional=3, visual=3, assets=3))
        for i in range(5):
            tracker.add_score(BuildScore(prompt=f"bad{i}", compiles=0))
        assert tracker.score_trend() == "declining"

    def test_flat_trend(self):
        tracker = BuildTracker(self.tmpdir)
        for i in range(10):
            tracker.add_score(BuildScore(prompt=f"p{i}", compiles=1, renders=1))
        assert tracker.score_trend() == "flat"


class TestFormatReport:
    """Report formatting."""

    def test_empty_report(self):
        tracker = BuildTracker(tempfile.mkdtemp())
        assert "No builds" in tracker.format_report()

    def test_populated_report(self):
        tracker = BuildTracker(tempfile.mkdtemp())
        tracker.add_score(BuildScore(prompt="a", scaffold="react-app", compiles=1, renders=1, iterations=15))
        report = tracker.format_report()
        assert "Builds: 1" in report
        assert "react-app" in report

    def test_report_with_failures(self):
        tracker = BuildTracker(tempfile.mkdtemp())
        for i in range(3):
            tracker.add_score(BuildScore(prompt=f"p{i}", failures=["blank_page"]))
        report = tracker.format_report()
        assert "blank_page" in report
        assert "3x" in report


class TestFailurePattern:
    """FailurePattern dataclass."""

    def test_default(self):
        p = FailurePattern(name="blank_page")
        assert p.count == 0
        assert p.fixed is False

    def test_fields(self):
        p = FailurePattern(name="css_broken", count=5, root_cause="missing base styles", fixed=True)
        assert p.count == 5
        assert p.fixed is True
