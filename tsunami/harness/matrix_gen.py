"""Overnight run-matrix generator (SIGMA_AUDIT §17.3).

Emits ~/.tsunami/overnight/matrix.jsonl — one row per tsunami run. Each
row is a dict with {run_id, prompt, env, expected_*, budget_s}.

Six axis crossings per §17.3:
  A. genre × style (when genre_scaffolds lands — today a thin stub)
  B. content-replica × scaffold (zelda-like dashboard, mario form wizard)
  C. seed-image × baseline  (requires image anchor list — stub today)
  D. brand-industry × product-type
  E. exploration-rate sweep — same prompt at 3 explore rates
  F. saturation bait — 5 identical prompts back-to-back

MVP mode (default) ships only A-light (scaffold × style, no genre
coverage yet) + F (saturation bait). That's the smallest matrix that
still produces a non-trivial stall table.

Usage:
    python -m tsunami.harness.matrix_gen --out ~/.tsunami/overnight/matrix.jsonl
    python -m tsunami.harness.matrix_gen --mvp --out ...
    python -m tsunami.harness.matrix_gen --full --out ...
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Prompts per scaffold — representative, not exhaustive. These are the
# seeds; the generator crosses them with axes below.
_SCAFFOLD_PROMPTS: dict[str, list[str]] = {
    "react-app": [
        "build a kanban board with drag-and-drop cards",
        "build a pomodoro timer with task list",
        "build a habit tracker with 30-day grid",
    ],
    "landing": [
        "landing page for a B2B analytics startup with pricing tiers",
        "marketing page for a vinyl record shop with upcoming releases",
        "coming soon splash page for an indie film festival",
    ],
    "dashboard": [
        "admin dashboard for a SaaS company with KPI cards and user list",
        "metrics dashboard for a logistics company with shipments table",
        "ops console for monitoring microservices",
    ],
    "auth-app": [
        "saas app with JWT login, register, and protected routes",
        "user accounts with email verification and password reset",
    ],
    "form-app": [
        "multi-step signup wizard with validation",
        "onboarding flow for a fintech app",
    ],
    "data-viz": [
        "visualize time series of CPU usage with line chart and brush selector",
        "heatmap of user activity by hour and day of week",
    ],
    "realtime": [
        "collaborative whiteboard with live cursors",
        "multiplayer tic-tac-toe with presence indicators",
    ],
    "ai-app": [
        "ai chat app with streaming responses and message history",
        "llm assistant with model picker and token counter",
    ],
    "fullstack": [
        "todo app with sqlite persistence and express backend",
        "note-taking app with full-text search and tags",
    ],
    "gamedev": [
        "build a zelda-like top-down action adventure with 3 dungeons",
        "build a simple platformer with 5 levels",
        "build a bullet-hell shoot-em-up",
        "replicate Mario world 1-1",
    ],
    "chrome-extension": [
        "chrome extension that highlights product prices on shopping sites",
    ],
    "electron-app": [
        "electron menubar app for quick code snippets",
    ],
    "api-only": [
        "rest api for a url shortener with rate limiting",
    ],
}


# Style env overrides to test. "" means "let routing pick".
_STYLE_OVERRIDES = [
    "",
    "shadcn_startup",
    "photo_studio",
    "editorial_dark",
    "brutalist_web",
    "newsroom_editorial",
]

# Genre env overrides (gamedev only). "" means "let routing pick".
_GENRE_OVERRIDES = ["", "platformer", "metroidvania", "fps", "jrpg"]

# Explore-rate sweep — §17.3 axis E.
_EXPLORE_RATES = ["0.0", "0.15", "0.35"]


def _hash(task: str) -> str:
    return hashlib.sha256(task.encode()).hexdigest()[:8]


_ROW_COUNTER = 0

def _make_row(prompt: str, scaffold: str, style: str = "", genre: str = "",
              explore: str = "", budget_s: int = 600) -> dict:
    global _ROW_COUNTER
    _ROW_COUNTER += 1
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    # Sequence number in hash input guarantees uniqueness even for
    # saturation-bait duplicates (same prompt, same second, same style).
    ts_hash = _hash(f"{prompt}|{style}|{genre}|{explore}|{ts}|{_ROW_COUNTER}")
    env: dict[str, str] = {
        "TSUNAMI_VISION_GATE": "1",
        "TSUNAMI_ROUTING_TELEMETRY": "1",
        "TSUNAMI_DOCTRINE_HISTORY": "1",
        "TSUNAMI_QUALITY_TELEMETRY": "1",
    }
    if style:
        env["TSUNAMI_STYLE"] = style
    if genre:
        env["TSUNAMI_GENRE"] = genre
    if explore:
        env["TSUNAMI_STYLE_EXPLORE"] = explore
    return {
        "run_id": f"{ts}-{ts_hash}",
        "prompt": prompt,
        "env": env,
        "expected_scaffold": scaffold,
        "expected_style": style,
        "expected_genre": genre,
        "expected_content_replica": "",
        "budget_s": budget_s,
    }


def generate_mvp() -> list[dict]:
    """Smallest useful matrix: scaffold × 1 prompt each, default style,
    + one saturation-bait cluster. ~15 rows, fits in ~2h at N=2."""
    rows: list[dict] = []
    for scaffold, prompts in _SCAFFOLD_PROMPTS.items():
        rows.append(_make_row(prompts[0], scaffold))
    # Saturation bait — 5 copies of one prompt.
    for _ in range(5):
        rows.append(_make_row("build a habit tracker with 30-day grid",
                              "react-app"))
    return rows


def generate_full() -> list[dict]:
    """Full matrix per §17.3. Several hundred rows."""
    rows: list[dict] = []
    # Axis A (light): scaffold × prompt × style
    for scaffold, prompts in _SCAFFOLD_PROMPTS.items():
        for prompt in prompts:
            # One baseline (no style override)
            rows.append(_make_row(prompt, scaffold))
            # Three style overrides per prompt
            for style in _STYLE_OVERRIDES[1:4]:
                rows.append(_make_row(prompt, scaffold, style=style))
    # Axis B: content-replica × non-gamedev scaffold
    content_prompts = [
        ("zelda-like dashboard with dungeon-themed KPIs", "dashboard"),
        ("zelda-like landing page for a nostalgia brand", "landing"),
    ]
    for prompt, scaffold in content_prompts:
        rows.append(_make_row(prompt, scaffold))
    # Axis D: brand × product — only gamedev-adjacent for MVP
    brand_prompts = [
        ("landing page for a hypercar company", "landing"),
        ("landing page for a watch brand", "landing"),
        ("landing page for a vinyl label", "landing"),
    ]
    for prompt, scaffold in brand_prompts:
        rows.append(_make_row(prompt, scaffold))
    # Axis E: explore-rate sweep on one prompt
    for rate in _EXPLORE_RATES:
        rows.append(_make_row("landing page for a coffee subscription",
                              "landing", explore=rate))
    # Axis F: saturation bait
    for _ in range(5):
        rows.append(_make_row("build a habit tracker with 30-day grid",
                              "react-app"))
    # Gamedev genre coverage (if genre_scaffolds lands)
    for prompt in _SCAFFOLD_PROMPTS["gamedev"]:
        for genre in _GENRE_OVERRIDES:
            rows.append(_make_row(prompt, "gamedev", genre=genre))
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, help="Output matrix.jsonl path")
    parser.add_argument("--mode", choices=["mvp", "full"], default="mvp")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    rows = generate_mvp() if args.mode == "mvp" else generate_full()
    out = Path(args.out).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")
    print(f"Wrote {len(rows)} rows to {out}")


if __name__ == "__main__":
    main()
