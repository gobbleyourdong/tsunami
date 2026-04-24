"""Parser that harvests Qwen-Image-Edit nudge chains from sister's
`progression_description` fields in sprite_sheets/<essence>/sheet_*.json.

Sister extracted 2074 animations from canonical games. Each has a
prose progression_description like:
  "small flash → expanding fire cross → scattered debris → fade"

That IS a Qwen-Image-Edit chain. Parse the arrows (or commas, or
numbered phases) into discrete NudgeStep deltas, and the ERNIE base
frame + Qwen chain-edit of N-1 nudges produces the full N-frame
animation. The canonical games' animations become OUR animations.

No ERNIE/Qwen calls from this module — pure text parsing.

Usage:
    from nudge_library import extract_nudges
    anim_entry = {...}  # one animations[] entry
    nudges = extract_nudges(anim_entry)
    # nudges is list[NudgeSpec]; len = frame_count - 1
    # each has .delta (prose nudge), .confidence (parse confidence)
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ParseStrategy(str, Enum):
    ARROW_SPLIT = "arrow_split"      # N→N→N on → or " / "
    FRAME_ENUMERATE = "frame_enum"   # "frame 1 X, frame 2 Y"
    NARRATIVE = "narrative"          # fallback prose-splitter
    ATLAS_REJECT = "atlas_reject"    # "roster of X" — not a frame sequence
    SINGLE_FRAME = "single_frame"    # frame_count < 2
    UNKNOWN = "unknown"


@dataclass
class NudgeSpec:
    """One chain-edit nudge. Maps 1:1 to Qwen-Image-Edit's NudgeStep."""
    delta: str
    confidence: float  # 0..1 — parse confidence, distinct from Qwen's
    strategy: ParseStrategy
    strength: float = 0.4  # Qwen NudgeStep default (low = identity-preserved)


# Regex: split points for N-frame arrow-or-slash-separated lists.
# Only split on:
#   1. The `→` arrow (unambiguous frame-transition marker)
#   2. " / " or " | " with surrounding whitespace (slash/pipe separator)
# DO NOT split on internal word hyphens (e.g. "left-foot-forward" is ONE
# phrase, not three).
_ARROW_RE = re.compile(r"\s*→\s*|\s+/\s+|\s+\|\s+")

# "frame 1 X, frame 2 Y, ..." — explicit enumeration
_FRAME_ENUM_RE = re.compile(
    r"frame\s+(\d+)\s*[:,-]?\s*([^,;.]+?)(?=\s*(?:,\s*frame|;|\.|$))",
    re.IGNORECASE,
)

# Atlas/roster signal — NOT a frame animation. "N×M grid", "atlas",
# "roster", "variants", "font variant", "palette variant" etc.
_ATLAS_SIGNALS = re.compile(
    r"\b(atlas|roster|variants?|font\b|palette|glyphs?|sprites(?:\s+|$)|sheet|grid(?:\s+|$)|rows?\s*[x×]\s*\d+|[x×]\s*\d+\s*(cols?|grid))",
    re.IGNORECASE,
)

# Cycle/loop signal — aura_vfx, atmospheric_vfx, walk cycles
_CYCLE_SIGNALS = re.compile(
    r"\b(cycle|loop|alternat(e|ing|es)|pulse|flicker|blink|cycling)",
    re.IGNORECASE,
)


def extract_nudges(anim: dict) -> list[NudgeSpec]:
    """Main entry point. Parses a single animations[] entry.

    Returns [] for:
      - frame_count < 2 (single-frame; no nudges needed)
      - atlas/roster entries (structural, not frame-sequential)
      - unparseable prose

    Returns frame_count - 1 NudgeSpecs otherwise (chain starts from
    frame_0 = ERNIE base; each nudge produces the next frame)."""
    fc = anim.get("frame_count") or 0
    if not isinstance(fc, int) or fc < 2:
        return []

    desc = (anim.get("progression_description") or "").strip()
    if not desc:
        return []

    if _ATLAS_SIGNALS.search(desc):
        # Rosters/atlases: not a frame sequence. Caller should flag
        # `needs_animation: false` for these even if frame_count > 1.
        return []

    # Strategy 1: explicit frame-numbered enumeration.
    frame_matches = list(_FRAME_ENUM_RE.finditer(desc))
    if len(frame_matches) >= 2:
        # Extract in order, keep only those numbered 1..fc.
        items: list[tuple[int, str]] = []
        for m in frame_matches:
            idx = int(m.group(1))
            text = m.group(2).strip().rstrip(",;.-")
            if 1 <= idx <= fc:
                items.append((idx, text))
        items.sort()
        if len(items) >= 2:
            # Each nudge describes the TRANSITION to that frame.
            # Nudge for frame i = items[i].
            # Chain input is the base = frame 0 (or frame 1 if 1-indexed).
            nudges = []
            for i in range(1, len(items)):
                nudges.append(NudgeSpec(
                    delta=items[i][1],
                    confidence=0.9,
                    strategy=ParseStrategy.FRAME_ENUMERATE,
                ))
            return nudges[:fc - 1]

    # Strategy 2: arrow/slash splitter — the most common pattern.
    # First, strip the leading "N-frame X —" preamble if present.
    body = re.sub(r"^\s*\d+[\s-]?frame[^—:]*[—:]\s*", "", desc)
    # Also strip trailing "; plays on" or "; drops" metadata.
    body = re.split(r"\s*;\s*", body)[0]
    parts = _ARROW_RE.split(body)
    parts = [p.strip().rstrip(",.;").strip() for p in parts if p.strip()]
    # Keep only substantive parts (3+ chars, alphabetic).
    parts = [p for p in parts if len(p) >= 3 and any(c.isalpha() for c in p)]
    if len(parts) >= 2:
        # Cap to fc parts (arrow chain longer than frame_count → trim)
        parts = parts[:fc]
        nudges = []
        for i in range(1, len(parts)):
            nudges.append(NudgeSpec(
                delta=parts[i],
                confidence=0.85,
                strategy=ParseStrategy.ARROW_SPLIT,
            ))
        return nudges[:fc - 1]

    # Strategy 2b: comma-list splitter — fallback when no arrows/slashes
    # but comma-separated phrases match frame_count. Requires ≥ fc-1
    # comma-delimited parts in the body (e.g. "small flash, expanding,
    # scattered debris, fade" for fc=4). Lower confidence than arrow.
    comma_parts = [p.strip().rstrip(".;") for p in re.split(r"\s*,\s*", body)]
    comma_parts = [p for p in comma_parts if len(p) >= 3 and any(c.isalpha() for c in p)]
    if len(comma_parts) >= fc:
        # Full match — use first `fc` as frame descriptions.
        comma_parts = comma_parts[:fc]
        nudges = []
        for i in range(1, fc):
            nudges.append(NudgeSpec(
                delta=comma_parts[i], confidence=0.7,
                strategy=ParseStrategy.NARRATIVE,
            ))
        return nudges[:fc - 1]

    # Strategy 3: cycle/loop fallback — emit symmetric "slight pulse"
    # nudges. Weaker confidence; runtime may want to re-roll per-frame
    # rather than trust these.
    if _CYCLE_SIGNALS.search(desc):
        # For a 2-frame cycle, 1 nudge "alternate state". For 4-frame,
        # 3 nudges oscillating.
        base_nudge = _extract_cycle_nudge(desc)
        if base_nudge:
            return [
                NudgeSpec(
                    delta=base_nudge, confidence=0.55,
                    strategy=ParseStrategy.NARRATIVE,
                )
            ] * (fc - 1)

    return []


def _extract_cycle_nudge(desc: str) -> Optional[str]:
    """Fallback: pull a short delta from a cycle-description narrative."""
    # "...alternating X and Y" — capture Y.
    m = re.search(r"alternat\w*\s+([^,.;]+?)\s+and\s+([^,.;]+)", desc, re.IGNORECASE)
    if m:
        return f"alternate to {m.group(2).strip()}"
    # "head bobs up/down as legs alternate" → "subtle head-bob + leg-alternate"
    m = re.search(r"(\w+\s+(bobs?|swings?|waves?|flaps?|pulses?|flickers?|blinks?)\s+[^,.;]+)", desc, re.IGNORECASE)
    if m:
        return f"next phase of {m.group(1).strip()}"
    # "N-frame X cycle" or "N-frame Y loop" → return generic-motion nudge.
    m = re.search(r"\d+[\s-]?frame\s+([\w-]+(?:\s+[\w-]+){0,3})\s+(cycle|loop|pulse)", desc, re.IGNORECASE)
    if m:
        return f"next phase of {m.group(1).strip()} {m.group(2).lower()}"
    # "body-wave cycle" / "wing-flap cycle" shorthand
    m = re.search(r"([\w-]+(?:-[\w]+)?)\s+(cycle|loop|pulse|flap|flicker|pulse)", desc, re.IGNORECASE)
    if m:
        return f"next phase of {m.group(1)} {m.group(2).lower()}"
    # Blink/flicker fallback
    if re.search(r"\b(blink|flicker|pulse)s?\b", desc, re.IGNORECASE):
        return "alternate blink state"
    return None


def classify_kind_needs_animation(kind: str, sub_kind: Optional[str] = None) -> bool:
    """Default `needs_animation` flag per kind + sub_kind. Scaffolds can
    override per-entry (e.g., a specific `tile::background` might be
    animated water — override to True). Based on the table proposed
    2026-04-22."""
    if kind == "tile":
        return sub_kind == "background"  # most tiles are static
    if kind == "pickup_item":
        # Power items often have spin animations; others are static.
        return sub_kind == "power_item"
    if kind == "ui":
        return False  # UI is static frames
    if kind == "background_layer":
        return False  # scroll is runtime-applied, not frame-animated
    if kind == "projectile":
        # Single-frame gun_proj static; others animate.
        return sub_kind != "gun_proj"
    if kind == "effect_layer":
        return True  # all effects are multi-frame
    if kind == "character":
        return True  # walk/attack/hit cycles
    return True  # safe default — err on animating unknown kinds
