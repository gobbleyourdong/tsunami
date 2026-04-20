"""Preview the vision-gate VLM prompt with rubric threading enabled.

The probe instance's uncommitted vision_gate.py changes add doctrine hints,
but it still doesn't pull the undertow_scaffolds/{web_polish,art_direction}.md
checklist rubrics into the single-shot vision QA path. The loader
`qa_rubrics.load_polish_rubric` is ready; wiring it into vision_gate is a
3-line edit we're holding until the probe instance's diff lands.

This module composes what the *threaded* prompt would look like, so you can
inspect it, tune it, or hand it to a VLM by other means. No dependency on
vision_gate's current state — this is a preview/documentation tool.

Usage:
    python3 -m tsunami.vision_preview --scaffold landing
    python3 -m tsunami.vision_preview --scaffold gamedev --style editorial_dark
    python3 -m tsunami.vision_preview --no-rubric   # show baseline prompt

When the 3-line vision_gate edit lands, running this with the same
arguments should produce the same composed prompt the VLM actually sees.
"""
from __future__ import annotations

import argparse
import sys

from .qa_rubrics import load_polish_rubric


# Mirror of the baseline vision_gate system prompt — the bit before any
# doctrine hints get appended. Kept here as a snapshot so the preview
# stays stable while vision_gate.py is in flux upstream. Update when the
# probe instance's diff lands.
_BASELINE_SYSTEM = (
    "You are a visual QA reviewer for a STATIC screenshot of a React app. "
    "You can ONLY judge what a screenshot shows: visible elements, layout, "
    "typography, color, spacing, completeness of the rendered UI. You CANNOT "
    "judge interactivity (whether buttons click, whether timers run, whether "
    "typing works) — those are tested separately by unit tests. Judge only "
    "the visual/structural presentation.\n\n"
    "Fail criteria (be strict — delivery is blocked on fail):\n"
    "  - Blank or mostly-blank page\n"
    "  - Missing major UI elements the task requires\n"
    "  - Placeholder text like 'TODO' or 'Loading...' as the primary content\n"
    "  - Layout breakage: overlapping elements, off-screen content, broken z-order\n"
    "  - Text CLIPPED by its container\n"
    "  - DUPLICATED content that should appear once\n"
    "  - Inconsistent typography on the same line\n"
    "  - Color hierarchy that obscures meaning\n"
    "Pass criteria: task-relevant elements are visible, no clipping, no "
    "duplicates, consistent style.\n\n"
    "Respond in this exact format:\n"
    "VERDICT: pass | fail\n"
    "ISSUES: <one-line-per-issue, or 'none'>"
)


def compose(scaffold: str | None = None,
            style_name: str | None = None,
            with_rubric: bool = True) -> str:
    """Build the composed system prompt. Mirrors what vision_gate would
    emit once the qa_rubrics wiring is merged."""
    parts = [_BASELINE_SYSTEM]
    if style_name:
        parts.append(f"[Style doctrine in play: {style_name}. Judge "
                     f"coherence RELATIVE to that doctrine, not a generic "
                     f"'clean UI' baseline.]")
    if with_rubric:
        rubric = load_polish_rubric(scaffold_name=scaffold)
        if rubric:
            parts.append(rubric)
    return "\n\n".join(parts)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Preview the rubric-threaded vision-gate prompt.")
    p.add_argument("--scaffold", default="landing",
                   help="Scaffold name (landing, dashboard, gamedev, ...). "
                        "Drives which rubrics apply.")
    p.add_argument("--style", default=None,
                   help="Style doctrine name (editorial_dark, photo_studio, ...).")
    p.add_argument("--no-rubric", action="store_true",
                   help="Show the baseline prompt only, no rubric injection.")
    p.add_argument("--count", action="store_true",
                   help="Print character count only.")
    args = p.parse_args(argv)

    composed = compose(
        scaffold=args.scaffold,
        style_name=args.style,
        with_rubric=not args.no_rubric,
    )

    if args.count:
        print(f"composed_chars={len(composed)} "
              f"scaffold={args.scaffold} style={args.style or 'none'} "
              f"rubric={'off' if args.no_rubric else 'on'}")
    else:
        print(composed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
