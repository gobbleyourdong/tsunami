"""Load undertow_scaffolds/{web_polish,art_direction}.md and render them as
compact rubric blocks the vision_gate VLM prompt can thread in.

Motivation: the probe instance's `pick_direction_set` (in undertow.py) only
routes rubrics into the lever-based QA flow. The fast-path vision_gate used
during delivery doesn't run levers — it posts a single screenshot + text
prompt to the VLM, so the polish/art-direction rubrics never reach it. This
module exposes the rubric content in a form vision_gate (and any other
single-shot QA caller) can embed in its system message with a 3-line edit.

Non-blocking: every file-read swallows errors. If the scaffold dir is
missing or malformed, callers get "" and baseline vision-gate behavior
is preserved.

Usage (from vision_gate.py, once probe commits and merge conflicts clear):

    from .qa_rubrics import load_polish_rubric
    rubric = load_polish_rubric(scaffold_name=scaffold)
    if rubric:
        messages[0]["content"] += "\n\n" + rubric

Rubric selection:
  - web_polish.md always applies (applies_to ["*"]).
  - art_direction.md applies when scaffold ∈ {landing, dashboard,
    react-build, form-app} per its frontmatter.
  - Callers can override via the `extra_names` param.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Iterable

log = logging.getLogger("tsunami.qa_rubrics")

_SCAFFOLD_DIR = Path(__file__).parent / "undertow_scaffolds"

# Parsed rubric frontmatter keys we care about.
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Cheap YAML-ish frontmatter parse — just what we need to route.
    Returns (meta_dict, body_text). No PyYAML dep."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    head = m.group(1)
    body = text[m.end():]
    meta: dict = {}
    for line in head.splitlines():
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        k = k.strip()
        v = v.strip()
        # Tolerate `applies_to: ["*"]` or `applies_to: [landing, dashboard]`.
        if v.startswith("[") and v.endswith("]"):
            inner = v[1:-1].strip()
            items = [x.strip().strip('"').strip("'") for x in inner.split(",") if x.strip()]
            meta[k] = items
        else:
            meta[k] = v.strip('"').strip("'")
    return meta, body


def _load_one(name: str) -> tuple[dict, str]:
    path = _SCAFFOLD_DIR / f"{name}.md"
    try:
        return _parse_frontmatter(path.read_text())
    except FileNotFoundError:
        log.debug(f"qa_rubrics: missing {path.name}")
        return {}, ""
    except Exception as e:
        log.debug(f"qa_rubrics: failed to read {path.name}: {e}")
        return {}, ""


def _applies(meta: dict, scaffold_name: str | None) -> bool:
    """True if the rubric's applies_to list matches the scaffold. `*` in the
    list is a universal match; missing frontmatter is treated as universal."""
    applies_to = meta.get("applies_to")
    if not applies_to:
        return True
    if "*" in applies_to:
        return True
    if not scaffold_name:
        return False
    return scaffold_name in applies_to


def _strip_to_questions(body: str) -> str:
    """Strip prose around the questions block so we only send the checklist +
    pass/fail criteria to the VLM. Tight token budget in the system prompt."""
    # Capture ## Questions through end-of-file; tolerate missing section.
    m = re.search(r"## Questions.*", body, re.DOTALL)
    return m.group(0).strip() if m else body.strip()


def load_polish_rubric(scaffold_name: str | None = None,
                       extra_names: Iterable[str] = (),
                       max_chars: int = 3200) -> str:
    """Return a formatted rubric block for VLM injection, or "" on failure.

    Order: web_polish (universal) then art_direction (conditional), then any
    `extra_names` requested by the caller. Result is bounded by `max_chars`
    to keep the system prompt lean — overflow is truncated with a marker.
    """
    parts: list[str] = []
    candidates = ["web_polish", "art_direction", *extra_names]
    seen: set[str] = set()
    for name in candidates:
        if name in seen:
            continue
        seen.add(name)
        meta, body = _load_one(name)
        if not body:
            continue
        if not _applies(meta, scaffold_name):
            continue
        title = meta.get("name", name.replace("_", " ").title())
        content = _strip_to_questions(body)
        parts.append(f"RUBRIC — {title}\n{content}")

    if not parts:
        return ""

    block = (
        "Additional QA rubrics (each is a visual checklist; apply in order, "
        "list any concrete failures you see in ISSUES):\n\n"
        + "\n\n".join(parts)
    )
    if len(block) > max_chars:
        block = block[: max_chars - 32].rstrip() + "\n[rubric block truncated]"
    return block


__all__ = ["load_polish_rubric"]
