"""Build grader — score deliverables from expansion/hardening builds.

After each build through the agent, grade on 5 dimensions:
1. Compiles (0/1) — does `npm run build` pass?
2. Renders (0/1) — is there visible content (not blank)?
3. Functional (0-3) — do the interactive features work?
4. Visual (0-3) — does it look good?
5. Assets (0-3) — are generated images placed and loading?

Total per build: /10. Target: average 7+/10.

Also tracks patterns across builds for the hardening loop:
- Which scaffolds perform best/worst
- Common failure patterns
- Iteration count per build (efficiency metric)
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path

log = logging.getLogger("tsunami.build_grader")


@dataclass
class BuildScore:
    """Score for a single build."""
    prompt: str
    scaffold: str = ""
    compiles: int = 0          # 0 or 1
    renders: int = 0           # 0 or 1
    functional: int = 0        # 0-3
    visual: int = 0            # 0-3
    assets: int = 0            # 0-3
    iterations: int = 0
    duration_s: float = 0
    failures: list[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    @property
    def total(self) -> int:
        return self.compiles + self.renders + self.functional + self.visual + self.assets

    def summary(self) -> str:
        return (
            f"{self.total}/10 | "
            f"compile={self.compiles} render={self.renders} "
            f"func={self.functional} visual={self.visual} assets={self.assets} | "
            f"{self.iterations} iters, {self.duration_s:.0f}s"
        )


@dataclass
class FailurePattern:
    """A recurring failure pattern across builds."""
    name: str
    count: int = 0
    root_cause: str = ""
    fixed: bool = False
    example_prompt: str = ""


class BuildTracker:
    """Track build scores and patterns across the expansion phase."""

    def __init__(self, workspace_dir: str | Path = "."):
        self.workspace = Path(workspace_dir)
        self._scores_path = self.workspace / ".build_scores.json"
        self._patterns_path = self.workspace / ".build_patterns.json"
        self.scores: list[BuildScore] = []
        self.patterns: dict[str, FailurePattern] = {}

    def load(self):
        """Load scores and patterns from disk."""
        if self._scores_path.exists():
            try:
                data = json.loads(self._scores_path.read_text())
                self.scores = [BuildScore(**s) for s in data]
            except (json.JSONDecodeError, TypeError):
                self.scores = []
        if self._patterns_path.exists():
            try:
                data = json.loads(self._patterns_path.read_text())
                self.patterns = {k: FailurePattern(**v) for k, v in data.items()}
            except (json.JSONDecodeError, TypeError):
                self.patterns = {}

    def save(self):
        """Save scores and patterns to disk."""
        self._scores_path.write_text(json.dumps([asdict(s) for s in self.scores], indent=2))
        self._patterns_path.write_text(json.dumps({k: asdict(v) for k, v in self.patterns.items()}, indent=2))

    def add_score(self, score: BuildScore):
        """Add a build score and update patterns."""
        self.scores.append(score)
        for failure in score.failures:
            if failure not in self.patterns:
                self.patterns[failure] = FailurePattern(
                    name=failure, example_prompt=score.prompt
                )
            self.patterns[failure].count += 1
        self.save()

    def average_score(self, last_n: int = 0) -> float:
        """Average total score across builds."""
        scores = self.scores[-last_n:] if last_n else self.scores
        if not scores:
            return 0
        return sum(s.total for s in scores) / len(scores)

    def average_iterations(self, last_n: int = 0) -> float:
        """Average iteration count per build."""
        scores = self.scores[-last_n:] if last_n else self.scores
        if not scores:
            return 0
        return sum(s.iterations for s in scores) / len(scores)

    def scaffold_stats(self) -> dict[str, dict]:
        """Per-scaffold performance stats."""
        stats: dict[str, list[BuildScore]] = {}
        for s in self.scores:
            if s.scaffold not in stats:
                stats[s.scaffold] = []
            stats[s.scaffold].append(s)

        result = {}
        for scaffold, builds in stats.items():
            avg_score = sum(b.total for b in builds) / len(builds)
            avg_iters = sum(b.iterations for b in builds) / len(builds)
            worst = min(builds, key=lambda b: b.total)
            result[scaffold] = {
                "builds": len(builds),
                "avg_score": round(avg_score, 1),
                "avg_iterations": round(avg_iters, 1),
                "worst_score": worst.total,
                "worst_failures": worst.failures,
            }
        return result

    def systemic_failures(self, threshold: int = 3) -> list[FailurePattern]:
        """Failures that occur 3+ times — need systemic fix."""
        return [p for p in self.patterns.values() if p.count >= threshold and not p.fixed]

    def score_trend(self, window: int = 5) -> str:
        """Are scores trending up, flat, or down?"""
        if len(self.scores) < window * 2:
            return "insufficient_data"
        early = self.scores[-(window * 2):-window]
        late = self.scores[-window:]
        early_avg = sum(s.total for s in early) / len(early)
        late_avg = sum(s.total for s in late) / len(late)
        if late_avg > early_avg + 0.5:
            return "improving"
        elif late_avg < early_avg - 0.5:
            return "declining"
        return "flat"

    def format_report(self) -> str:
        """Format a summary report."""
        if not self.scores:
            return "No builds scored yet."

        lines = [
            f"Builds: {len(self.scores)}",
            f"Average score: {self.average_score():.1f}/10",
            f"Average iterations: {self.average_iterations():.0f}",
            f"Trend: {self.score_trend()}",
        ]

        # Scaffold breakdown
        stats = self.scaffold_stats()
        if stats:
            lines.append("\nScaffold performance:")
            for scaffold, s in sorted(stats.items(), key=lambda x: x[1]["avg_score"], reverse=True):
                lines.append(f"  {scaffold}: {s['avg_score']}/10 avg, {s['avg_iterations']} iters, {s['builds']} builds")

        # Systemic failures
        systemic = self.systemic_failures()
        if systemic:
            lines.append(f"\nSystemic failures ({len(systemic)}):")
            for p in sorted(systemic, key=lambda x: x.count, reverse=True):
                lines.append(f"  [{p.count}x] {p.name} — {p.root_cause or 'not diagnosed'}")

        return "\n".join(lines)


def check_compiles(project_dir: str) -> bool:
    """Check if a project compiles (npm run build)."""
    try:
        result = subprocess.run(
            ["npx", "vite", "build"],
            cwd=project_dir,
            capture_output=True, text=True, timeout=30,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def check_renders(project_dir: str) -> bool:
    """Check if a project renders (index.html has content)."""
    dist = Path(project_dir) / "dist"
    if not dist.exists():
        return False
    index = dist / "index.html"
    if not index.exists():
        return False
    content = index.read_text()
    # Check for non-trivial content (not just empty template)
    return len(content) > 100 and "<div" in content.lower()
