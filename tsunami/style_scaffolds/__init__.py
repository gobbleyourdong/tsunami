"""Style scaffolds — inject high-style direction into drone briefs.

Problem: drones default to 'vanilla web' every time — dark theme, Inter
font, centered hero, ScrollReveal fades. The scaffold's index.css seeds
this, and the drone has no explicit counter-force. Every delivery
converges on the same 2015 aesthetic regardless of brand.

Solution: each run is assigned a style_scaffold — a concrete palette /
typography / layout / motion doctrine — that gets injected into the
user_message before decomposition. The drone sees an opinionated
direction instead of defaults.

Selection: keyword-routed where the brief is explicit ("magazine",
"swiss", "brutalist"); otherwise randomized from scaffolds applicable
to the project type. Set env `TSUNAMI_STYLE` to force a specific one.
"""

from __future__ import annotations

import os
import random
import re
from pathlib import Path

_HERE = Path(__file__).parent

# Keyword → style file (first match wins).
# Single-word keys use word-boundary regex; multi-word are substring.
_KEYWORD_MAP: list[tuple[tuple[str, ...], str]] = [
    (("brutalist", "brutalism", "raw html", "anti-design"), "brutalist_web"),
    (("magazine", "editorial long-form", "long form", "kinfolk", "cereal"),
     "magazine_editorial"),
    (("swiss", "müller-brockmann", "muller-brockmann", "grid-strict",
      "helvetica", "strict grid"), "swiss_modern"),
    (("playful", "stripe-style", "linear-style", "mesh gradient",
      "bento grid", "chromatic"), "playful_chromatic"),
    (("editorial dark", "luxury dark", "apple-style", "tesla-style",
      "cinematic dark", "noir"), "editorial_dark"),
]


def _available_styles() -> list[str]:
    return sorted(p.stem for p in _HERE.glob("*.md"))


def _load(name: str) -> str | None:
    path = _HERE / f"{name}.md"
    if not path.is_file():
        return None
    return path.read_text()


def pick_style(task: str, scaffold: str = "", seed: int | None = None) -> tuple[str, str]:
    """Return (style_name, style_body) for a task.

    Resolution order:
      1. env TSUNAMI_STYLE=<name>
      2. keyword match in task text
      3. random choice from scaffolds whose `applies_to` frontmatter
         lists `scaffold` (or contains '*')
      4. empty ("", "")  — no style injection
    """
    forced = os.environ.get("TSUNAMI_STYLE")
    if forced:
        body = _load(forced)
        if body:
            return forced, body

    tlow = task.lower()
    for keys, name in _KEYWORD_MAP:
        for k in keys:
            if " " in k or "-" in k:
                if k in tlow:
                    body = _load(name)
                    if body:
                        return name, body
            else:
                if re.search(rf"\b{re.escape(k)}\b", tlow):
                    body = _load(name)
                    if body:
                        return name, body

    # Random among applicable. Parse frontmatter applies_to.
    applicable: list[str] = []
    for p in _HERE.glob("*.md"):
        text = p.read_text()
        m = re.search(r"applies_to:\s*\[([^\]]+)\]", text)
        if not m:
            continue
        targets = [t.strip().strip('"').strip("'") for t in m.group(1).split(",")]
        if not scaffold or "*" in targets or scaffold in targets:
            applicable.append(p.stem)
    if not applicable:
        return "", ""
    rng = random.Random(seed) if seed is not None else random
    chosen = rng.choice(applicable)
    return chosen, _load(chosen) or ""


def format_style_directive(name: str, body: str) -> str:
    """Render the style body as a task-prepended directive block."""
    if not name or not body:
        return ""
    return (
        f"\n\n=== STYLE DIRECTION: {name} ===\n"
        f"This project must embody the style defined below. Override the\n"
        f"scaffold's defaults where they conflict. Ship this flavour, not\n"
        f"generic dark-theme-with-accent.\n\n{body}\n"
        f"=== END STYLE ===\n"
    )


__all__ = ["pick_style", "format_style_directive"]
