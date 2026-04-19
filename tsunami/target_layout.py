"""Full-page ERNIE target-layout generation.

One-shot image generation that produces a full-page mockup for the drone
to match. Runs ONCE per task, after scaffold provisioning, before the
agent loop. Output lands at `<project>/.tsunami/target_layout.png` and
its path gets appended to the style directive.

User override: if `~/.tsunami/inputs/<project>/.tsunami/target_layout.png`
exists, the pre-scaffold user-passthrough step copies it in, and this
module's existence-check short-circuits the ERNIE call. Lets a designer
drop a Figma export and have the drone match that instead of an
AI-generated target.

Opt-in: env `TSUNAMI_TARGET_LAYOUT=1`. Off by default — target generation
adds 15-30s to every task boot, and not every build needs a visual
reference (utility apps, simple forms, etc).

Vision-gate integration: if the target exists at delivery time, the gate
runs in "match the reference" mode instead of open-ended QA — the VLM
compares dist/ screenshot to target_layout.png and scores structural
similarity (layout, color palette, typography density).
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

_ERNIE_BUCKETS: list[tuple[int, int]] = [
    (1024, 1024),
    (1264, 848), (848, 1264),
    (1200, 896), (896, 1200),
    (1376, 768), (768, 1376),
]


def _snap_bucket(w: int, h: int) -> tuple[int, int]:
    target_ar = w / max(h, 1)
    return min(_ERNIE_BUCKETS, key=lambda wh: abs((wh[0] / wh[1]) - target_ar))


def _target_path(project_dir: Path) -> Path:
    return project_dir / ".tsunami" / "target_layout.png"


def has_target(project_dir: Path) -> bool:
    """True if a target layout is available for this project."""
    p = _target_path(project_dir)
    try:
        return p.is_file() and p.stat().st_size > 1024
    except Exception:
        return False


def target_path(project_dir: Path) -> Path | None:
    """Return the target-layout path, or None if absent."""
    return _target_path(project_dir) if has_target(project_dir) else None


def is_enabled() -> bool:
    """Target layout generation runs only when TSUNAMI_TARGET_LAYOUT=1."""
    return os.environ.get("TSUNAMI_TARGET_LAYOUT", "").strip() in ("1", "true", "yes", "on")


def _layout_prompt(task: str, style_name: str, style_mood: str) -> str:
    """Build the ERNIE prompt for the target-layout image.

    The target is a full-page MOCKUP screenshot, not a hero image — we
    want layout structure (nav, hero, sections, footer) visible as a
    single composed image at 16:9 for the drone to eyeball-match.
    """
    # Extract the 'brand' + core request from the first 400 chars so the
    # mockup shows the right product category (car, dashboard, portfolio,
    # etc.). Strip image-manifest directives that don't help layout.
    lines = [
        ln for ln in task.splitlines()
        if not ln.lstrip().startswith(("- public/", "GENERATE", "USE"))
    ]
    brief = " ".join(lines)[:400]
    mood_hint = f", {style_mood}" if style_mood else ""
    return (
        f"Full webpage screenshot mockup, desktop browser 16:9 composition. "
        f"Show the complete homepage from top navigation to footer as a "
        f"single scrollable image: header + hero section + content blocks "
        f"+ footer visible. Subject: {brief}. Style: {style_name}{mood_hint}. "
        f"Flat UI design mockup, no browser chrome, no scroll bars, no cursor. "
        f"High-fidelity layout render, clean typography, deliberate spacing. "
        f"The image should look like a designer's Figma preview of the "
        f"finished site."
    )


async def generate_target_layout(
    project_dir: Path,
    task: str,
    style_name: str = "",
    style_mood: str = "",
    endpoint: str | None = None,
) -> Path | None:
    """Generate the target-layout image for a project. Returns path or None.

    Short-circuits if:
      - disabled via env (TSUNAMI_TARGET_LAYOUT not set)
      - a target already exists (user dropped one via inputs/ passthrough)
      - ERNIE endpoint unreachable
    """
    if not is_enabled():
        return None
    if has_target(project_dir):
        log.info(f"target_layout: existing target at {_target_path(project_dir)} — skipping generation")
        return _target_path(project_dir)

    endpoint = (
        endpoint
        or os.environ.get("TSUNAMI_IMAGE_ENDPOINT")
        or "http://localhost:8092"
    )
    if not endpoint.startswith("http"):
        endpoint = f"http://{endpoint}"

    w, h = _snap_bucket(1376, 768)  # 16:9 landscape
    prompt = _layout_prompt(task, style_name, style_mood)
    out_path = _target_path(project_dir)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        import httpx
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{endpoint}/v1/images/generate",
                json={
                    "prompt": prompt,
                    "width": w,
                    "height": h,
                    "steps": 8,
                    "guidance_scale": 1.0,
                    "n": 1,
                },
            )
        if resp.status_code != 200:
            log.warning(f"target_layout: ERNIE returned {resp.status_code}")
            return None
        body = resp.json()
        b64 = body.get("data", [{}])[0].get("b64_json")
        if not b64:
            log.warning("target_layout: response missing b64_json")
            return None
        out_path.write_bytes(base64.b64decode(b64))
        log.info(
            f"target_layout: generated {out_path} "
            f"({out_path.stat().st_size} bytes, style={style_name!r})"
        )
        return out_path
    except Exception as e:
        log.debug(f"target_layout: generation failed: {e}")
        return None


def format_layout_directive(path: Path) -> str:
    """Render a directive block referencing the target layout image."""
    return (
        f"\n\n=== TARGET LAYOUT ===\n"
        f"A full-page visual reference for this build exists at:\n"
        f"  {path}\n"
        f"Your App.tsx should render a page whose overall composition —\n"
        f"navigation placement, hero proportions, section ordering, color\n"
        f"palette, spacing rhythm, typographic weight — matches this\n"
        f"reference. The reference is a mockup, not a spec; copy the\n"
        f"layout DNA, not pixel-for-pixel. The vision gate at delivery\n"
        f"time will compare your built page against this image.\n"
        f"=== END TARGET LAYOUT ===\n"
    )


__all__ = [
    "is_enabled",
    "has_target",
    "target_path",
    "generate_target_layout",
    "format_layout_directive",
]
