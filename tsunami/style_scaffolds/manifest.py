"""Doctrine manifest — programmatic export of the 10-doctrine library.

External consumers (UI galleries, routing UIs, future pick_by_vertical
functions, documentation generators) can query this instead of parsing
frontmatter themselves. Produces a list of dicts:

  {
    "name": "photo_studio",
    "mode": "light",              # default_mode
    "weight": 22.0,                # _style_weight
    "anchors": [...],              # comma-list from frontmatter
    "applies_to": [...],           # scaffolds the doctrine targets
    "mood": "...",                 # mood: line
    "has_hero": True,              # contains a ## Hero shape section
    "size": 5210,                  # body length in chars
  }

The manifest is computed on-demand from the .md files so it stays in sync
with whatever the authoring team has shipped.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import _ANCHOR_RE, _style_weight, _doctrine_mode

_HERE = Path(__file__).parent

_MOOD_RE = re.compile(r"^mood:\s*(.+?)\s*$", re.MULTILINE)
_APPLIES_RE = re.compile(r"^applies_to:\s*\[([^\]]+)\]", re.MULTILINE)
_CORPUS_FIELD_RE = re.compile(r"^corpus_share:\s*(\d+)\s*$", re.MULTILINE)


def doctrine_manifest() -> list[dict]:
    """Return a list of doctrine records sorted by descending weight."""
    records: list[dict] = []
    for p in _HERE.glob("*.md"):
        body = p.read_text()
        mood_m = _MOOD_RE.search(body)
        applies_m = _APPLIES_RE.search(body)
        anchors_m = _ANCHOR_RE.search(body)
        corpus_m = _CORPUS_FIELD_RE.search(body)

        applies_to: list[str] = []
        if applies_m:
            applies_to = [
                t.strip().strip('"').strip("'")
                for t in applies_m.group(1).split(",")
            ]
        anchors: list[str] = []
        if anchors_m:
            raw = anchors_m.group(1).strip()
            if not (raw.startswith("(") or "none" in raw.lower()):
                anchors = [a.strip() for a in raw.split(",") if a.strip()]

        records.append({
            "name": p.stem,
            "mode": _doctrine_mode(body),
            "weight": _style_weight(body),
            "corpus_share": int(corpus_m.group(1)) if corpus_m else None,
            "anchors": anchors,
            "applies_to": applies_to,
            "mood": mood_m.group(1).strip() if mood_m else "",
            "has_hero": "## Hero shape" in body or re.search(r"^## Hero\b", body, re.MULTILINE) is not None,
            "size": len(body),
        })
    records.sort(key=lambda r: -r["weight"])
    return records


def doctrine_manifest_json(indent: int = 2) -> str:
    return json.dumps(doctrine_manifest(), indent=indent)


def doctrines_for_mode(mode: str) -> list[str]:
    """Return doctrine names matching a given mode, ordered by weight."""
    assert mode in ("light", "neutral", "dark"), f"bad mode: {mode}"
    return [r["name"] for r in doctrine_manifest() if r["mode"] == mode]


def doctrines_for_scaffold(scaffold: str) -> list[str]:
    """Return doctrine names applicable to a given scaffold, ordered by weight."""
    return [
        r["name"] for r in doctrine_manifest()
        if "*" in r["applies_to"] or scaffold in r["applies_to"]
    ]


__all__ = [
    "doctrine_manifest",
    "doctrine_manifest_json",
    "doctrines_for_mode",
    "doctrines_for_scaffold",
]


if __name__ == "__main__":
    # CLI usage: python -m tsunami.style_scaffolds.manifest [mode|scaffold|json]
    import sys
    arg = sys.argv[1] if len(sys.argv) > 1 else "json"
    if arg == "json":
        print(doctrine_manifest_json())
    elif arg in ("light", "neutral", "dark"):
        print("\n".join(doctrines_for_mode(arg)))
    elif arg == "table":
        rows = doctrine_manifest()
        print(f"{'name':22s} {'mode':7s} {'wt':>5s}  {'hero':4s}  corpus  anchors")
        for r in rows:
            print(
                f"{r['name']:22s} {r['mode']:7s} {r['weight']:5.1f}  "
                f"{'yes' if r['has_hero'] else 'no':4s}  "
                f"{str(r['corpus_share']) if r['corpus_share'] is not None else '-':>5s}   "
                f"{', '.join(r['anchors'][:3])}"
            )
    else:
        # treat as a scaffold name
        print("\n".join(doctrines_for_scaffold(arg)))
