"""Expansion prompt runner — automated stress testing through the agent.

Runs expansion prompts (E1-E14, U1-U30) from PLAN.md through the agent,
grades each build, tracks patterns, and reports results.

Usage:
    runner = ExpansionRunner(config)
    await runner.run_prompt("build a counter", prompt_id="U1")
    runner.report()
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path

from .build_grader import BuildScore, BuildTracker, check_compiles, check_renders

log = logging.getLogger("tsunami.expansion_runner")

# Expansion prompts from PLAN.md
TIER1_PROMPTS = {
    "E1": "build a counter",
    "E2": "build a weather app",
    "E3": "build a notes app",
}

TIER2_PROMPTS = {
    "E4": "build a beautiful photography portfolio with 50 AI-generated landscape photos in a masonry grid with lightbox zoom, categories (mountains, ocean, forest, desert, urban), and lazy loading",
    "E5": "build a Netflix-style app with rows of shows. Generate 30 movie posters with SD-Turbo. Include: hero banner, category rows (Action, Comedy, Drama, Sci-Fi, Horror), search with filtering, show detail modal with fake synopsis, and a My List feature",
}

TIER3_GAME_PROMPTS = {
    "E8": "build an interactive Game Boy DMG-01 in the browser. Pixel-perfect shell with working D-pad, A/B/Start/Select buttons that animate on click. Screen shows a simple playable game — Snake or Breakout. Sound effects on button press. Power LED that glows. Volume slider.",
    "E9": "build an interactive Sega Game Gear in the browser. Landscape form factor, wider screen ratio than Game Boy. Working D-pad + 1/2/Start buttons. Screen plays a simple Columns-style puzzle game. Backlit screen effect. Battery indicator that slowly drains.",
    "E10": "build a 3D game where you're an IT technician in a server room. You have to: 1. Physically plug network cables between servers and switches (drag + snap) 2. Swap PCIe cards between slots (GPU, NIC, RAID controller) 3. Diagnose blinking status LEDs (green=ok, amber=degraded, red=down) 4. Boot servers in the right order (DNS → DHCP → App → DB) 5. Each correct connection lights up a network path on a wall dashboard. Use Three.js with orbit controls. Rack-mounted servers with card slots. Cable physics (catenary curves). Score based on uptime percentage.",
    "E11": "build a 2D pinball machine with Matter.js physics. Full table with: flippers (left/right arrow keys), plunger (space bar, hold to charge), bumpers that bounce and score, ramps, drop targets, multiball, tilt detection (shake mouse), and a dot-matrix score display at top. Sound effects. Ball save.",
    "E12": "build Tetris with a twist — 2-player split screen. Player 1 uses WASD, Player 2 uses arrow keys. Completed lines send garbage to opponent. T-spin and Tetris (4-line) bonuses. Ghost piece preview. Hold piece. Next 3 pieces preview. Speed increases every 10 lines. Game over animation.",
}

USER_PROMPTS = {
    "U1": "build a habit tracker where I can add daily habits, check them off, and see streaks",
    "U2": "build a personal finance tracker — add income/expenses, categories, monthly chart",
    "U16": "build a trivia quiz game with multiple categories and a scoreboard",
    "U17": "build a typing speed test with WPM, accuracy, and historical chart",
    "U18": "build a memory card matching game with a timer and best score tracking",
    "U26": "build a password generator — length slider, checkboxes for upper/lower/numbers/symbols, copy button",
    "U29": "build a markdown editor with live preview side by side",
}

ALL_PROMPTS = {**TIER1_PROMPTS, **TIER2_PROMPTS, **TIER3_GAME_PROMPTS, **USER_PROMPTS}


@dataclass
class RunResult:
    """Result of running a single expansion prompt."""
    prompt_id: str
    prompt: str
    score: BuildScore
    project_dir: str = ""
    error: str = ""


class ExpansionRunner:
    """Run expansion prompts through the agent and grade results."""

    def __init__(self, config, workspace_dir: str = "workspace"):
        self.config = config
        self.workspace = Path(workspace_dir)
        self.tracker = BuildTracker(workspace_dir)
        self.tracker.load()
        self.results: list[RunResult] = []

    async def run_prompt(self, prompt: str, prompt_id: str = "") -> RunResult:
        """Run a single prompt through the agent and grade the result."""
        from .agent import Agent

        log.info(f"[{prompt_id}] Running: {prompt[:60]}...")
        start = time.time()

        agent = Agent(self.config)
        try:
            await agent.run(prompt)
        except Exception as e:
            log.error(f"[{prompt_id}] Agent error: {e}")
            result = RunResult(
                prompt_id=prompt_id, prompt=prompt,
                score=BuildScore(prompt=prompt, failures=["agent_crash"]),
                error=str(e),
            )
            self.tracker.add_score(result.score)
            self.results.append(result)
            return result

        elapsed = time.time() - start
        iterations = agent.state.iteration

        # Find the deliverable
        deliverables = self.workspace / "deliverables"
        project_dir = ""
        if deliverables.exists():
            projects = sorted(
                [d for d in deliverables.iterdir() if d.is_dir()],
                key=lambda p: p.stat().st_mtime, reverse=True,
            )
            if projects:
                project_dir = str(projects[0])

        # Grade
        score = self._grade(project_dir, prompt, iterations, elapsed)
        score.scaffold = getattr(agent, '_scaffold_used', '') or ''

        result = RunResult(
            prompt_id=prompt_id, prompt=prompt,
            score=score, project_dir=project_dir,
        )
        self.tracker.add_score(score)
        self.results.append(result)

        log.info(f"[{prompt_id}] Score: {score.summary()}")
        return result

    def _grade(self, project_dir: str, prompt: str, iterations: int, elapsed: float) -> BuildScore:
        """Grade a build on the 5 dimensions."""
        score = BuildScore(
            prompt=prompt,
            iterations=iterations,
            duration_s=elapsed,
        )

        if not project_dir:
            score.failures.append("no_deliverable")
            return score

        # 1. Compiles
        if check_compiles(project_dir):
            score.compiles = 1
        else:
            score.failures.append("compile_error")

        # 2. Renders
        if check_renders(project_dir):
            score.renders = 1
        else:
            score.failures.append("blank_page")

        # 3-5: Functional, Visual, Assets — would need Playwright for full grading
        # For now, give partial credit if it compiles and renders
        if score.compiles and score.renders:
            score.functional = 1  # minimum
            score.visual = 1

        return score

    async def run_tier(self, prompts: dict[str, str]) -> list[RunResult]:
        """Run a set of prompts sequentially."""
        results = []
        for prompt_id, prompt in prompts.items():
            result = await self.run_prompt(prompt, prompt_id)
            results.append(result)

            # Stop if systemic failures detected
            systemic = self.tracker.systemic_failures()
            if systemic:
                log.warning(f"Systemic failures detected: {[f.name for f in systemic]}")
                log.warning("Fix root causes before continuing")
                break

        return results

    def report(self) -> str:
        """Generate the full expansion report."""
        return self.tracker.format_report()
