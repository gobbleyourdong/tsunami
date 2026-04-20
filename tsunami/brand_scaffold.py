"""Brand-definition scaffold — per-run brief with concrete prompt templates.

Problem: drones write generate_image prompts like "AURUM luxury brand logo,
wordmark AURUM in elegant gold serif" — ERNIE draws the literal word AURUM
as text instead of a brand mark. And the drone has no consistent visual
vocabulary across the 9 images in a brief, so each asset reads as its own
AI generation rather than one brand's library.

Fix: produce a per-run brand_brief.md at pre-scaffold time. The brief
contains concrete prompt templates for each common asset type (logo,
hero, product shots, portraits, environments) with visual-metaphor
language baked in. Drone reads the brief via the style directive and
reuses the templates — one brand's visual language applied consistently
across all 9+ images in the delivery.

Pairs with:
  - style_scaffolds: palette / typography / layout doctrine
  - generate_image tool description: per-asset prompt strategy
  - generate_image auto-upgrade to mode='icon' for logo paths

This module is deterministic — it builds the brief from the task text
using structured templates rather than a separate LLM call. Sigma team
can extend later with a synthesis-via-text-model step if briefs need
more creative range.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

log = logging.getLogger("tsunami.brand_scaffold")


# Industry → default symbol concepts + aesthetic refs. First-match keyword
# routing. These are PROMPT SEEDS, not exhaustive — the drone is free to
# deviate; we just want to start from something stronger than "wordmark
# in serif".
_INDUSTRY_BRIEFS: list[tuple[tuple[str, ...], dict]] = [
    # Compact / city / budget EV — FRIENDLY urban positioning. Listed
    # before the luxury-hypercar entry so "compact urban electric" / "city
    # car" / "affordable EV" don't fall through to the hypercar brief with
    # aerodynamic-wing emblems that don't fit a €15k commuter.
    (("compact car", "city car", "city-car", "mini car", "mini-car",
      "urban ev", "urban-ev", "micro ev", "micro-ev",
      "city ev", "city-ev", "compact ev", "compact-ev",
      "budget car", "affordable car", "commuter car", "micro car",
      "micro-car", "small car", "micromobility", "hatchback",
      "subcompact", "mini electric", "compact electric",
      "urban electric", "city electric", "compact urban"), {
        "symbol_concepts": [
            "rounded pebble shape with single directional mark",
            "friendly circular monogram with rounded initial",
            "geometric house + wheels pictogram simplified",
            "stacked rounded rectangles suggesting a tiny car profile",
            "single lowercase letter emblem in a soft rounded frame",
            "abstract leaf + wheel combined pictogram",
        ],
        "aesthetic_refs": [
            "friendly sans rounded wordmark",
            "playful geometric pictogram",
            "Muji-adjacent minimalist icon",
            "Scandinavian soft-brand mark",
            "civic utility pictogram",
        ],
        "environment_refs": [
            "narrow European city street with cobblestones",
            "bright white daylight parking spot with leafy background",
            "corner grocery storefront at morning",
            "Copenhagen bike lane with the car at curb",
            "small town square fountain backdrop",
            "underground parking garage with warm overhead light",
        ],
    }),
    (("hypercar", "supercar", "sportscar", "sports car", "race car",
      "automotive", "car brand", "electric car"), {
        "symbol_concepts": [
            "interlocking aerodynamic wings forming a shield",
            "octagonal monogram with carbon-fiber weave texture",
            "stylized arrow-piercing-circle emblem",
            "abstract silhouette of a wing in profile",
            "heraldic crest with vertical stripe and laurel flank",
        ],
        "aesthetic_refs": [
            "greeble mechanical detail",
            "art deco medallion with brass tooling",
            "brutalist monoline industrial insignia",
            "heraldic crest minimalist",
            "Bauhaus geometric emblem",
        ],
        "environment_refs": [
            "mountain road at golden hour",
            "rim-lit studio with dark floor",
            "racetrack at dusk with track-light flare",
            "Alpine glacier with snow ridge backdrop",
            "Mediterranean coast cliff road",
            "private showroom with single spotlight",
        ],
    }),
    (("watch", "chronograph", "horology", "timepiece"), {
        "symbol_concepts": [
            "clean circle with single tick mark at twelve o'clock",
            "enameled shield with understated centered monogram",
            "concentric ring emblem with minute markers",
        ],
        "aesthetic_refs": [
            "guilloché engraving",
            "Swiss heraldic minimalism",
            "art deco badge engraved on brass",
        ],
        "environment_refs": [
            "atelier workshop with warm tungsten light",
            "leather workbench with loupe and tools",
        ],
    }),
    (("photograph", "portfolio", "creative director", "studio"), {
        "symbol_concepts": [
            "single vertical bar mark",
            "serif initial inside a soft circle",
            "minimal rectangle outline with tick",
        ],
        "aesthetic_refs": [
            "editorial minimalism",
            "Helvetica-era Swiss mark",
            "neo-monogram",
        ],
        "environment_refs": [
            "empty gallery wall with soft skylight",
            "concrete studio with single chair",
        ],
    }),
    (("restaurant", "cafe", "food", "dining", "bakery", "coffee"), {
        "symbol_concepts": [
            "hand-illustrated wheat sheaf",
            "ceramic plate circle with fork-knife crossed",
            "steaming cup silhouette",
        ],
        "aesthetic_refs": [
            "botanical woodcut",
            "hand-lettered script serif",
            "Victorian apothecary mark",
        ],
        "environment_refs": [
            "warm dining room with candles",
            "marble bar with brass rail",
        ],
    }),
    (("saas", "startup", "dev tool", "platform", "dashboard",
      "analytics", "api"), {
        "symbol_concepts": [
            "geometric abstract shape — rotated square, layered triangles, chevron",
            "minimal wordmark-pair (first letter doubled into ligature)",
            "nested squares suggesting depth",
        ],
        "aesthetic_refs": [
            "Linear-style brand mark",
            "shadcn-aligned monochrome emblem",
            "Stripe-era minimalist geometry",
        ],
        "environment_refs": [
            "clean white studio with single soft light",
            "gradient mesh background, low saturation",
        ],
    }),
    (("bank", "finance", "fintech", "investment", "wealth"), {
        "symbol_concepts": [
            "architectural column silhouette",
            "minimalist chevron stack",
            "shield with vertical bar",
        ],
        "aesthetic_refs": [
            "classical banking emblem minimalist",
            "monoline institutional mark",
            "Swiss-modernist financial identity",
        ],
        "environment_refs": [
            "marble-lobby architectural detail",
            "glass-and-steel tower base",
        ],
    }),
]


# Default fallback for task briefs that don't match any industry keyword.
_DEFAULT_BRIEF: dict = {
    "symbol_concepts": [
        "geometric monogram with negative-space cutout",
        "minimal circular emblem with single internal mark",
        "stylized letterform as standalone glyph",
    ],
    "aesthetic_refs": [
        "monoline minimalist mark",
        "modernist geometric emblem",
        "neo-heraldic crest",
    ],
    "environment_refs": [
        "studio with soft directional light",
        "clean gradient backdrop",
    ],
}


_BRAND_NAME_RE = re.compile(r"\b(?:BRAND|Brand)\s*[:=]\s*([A-Z][A-Za-z0-9]+)")
_QUOTED_NAME_RE = re.compile(r"\bBuild\s+([A-Z][A-Z]+)\b")


def _extract_brand_name(task: str) -> str:
    """Pull the brand name out of the task text.

    Priority:
      1. "BRAND: Name" explicit declaration
      2. "Build NAME —" imperative with a capitalized noun
      3. first ALLCAPS token in the first 200 chars
      4. empty string (no brand inferred)
    """
    m = _BRAND_NAME_RE.search(task)
    if m:
        return m.group(1)
    m = _QUOTED_NAME_RE.search(task[:200])
    if m:
        return m.group(1)
    # First ALLCAPS word 2+ chars in leading text
    for tok in task[:200].split():
        cleaned = tok.strip(",.—-:;")
        if cleaned.isupper() and len(cleaned) >= 2 and cleaned.isalpha():
            return cleaned
    return ""


def _match_industry(task: str) -> dict:
    """Return the industry brief dict whose keyword first hits the task.

    Delegates to the unified routing matcher so word-boundary /
    multi-word substring rules stay consistent across every router
    in the codebase (the 'car brand' substring hitting 'compact
    city-car brand' collision that made PIKO route to hypercar
    would now be caught in one place, not six).
    """
    from .routing import match_first
    result = match_first(task, _INDUSTRY_BRIEFS, default=_DEFAULT_BRIEF)
    # F-C1 telemetry — log by industry_name (stable id). No-op unless
    # TSUNAMI_ROUTING_TELEMETRY=1.
    try:
        from .routing_telemetry import log_pick
        winner = result.get("industry_name", "") if isinstance(result, dict) else ""
        default_name = _DEFAULT_BRIEF.get("industry_name", "") if isinstance(_DEFAULT_BRIEF, dict) else ""
        log_pick("industry", task, winner, default=default_name,
                 match_source="default" if winner == default_name else "keyword")
    except Exception:
        pass
    return result


def generate_brand_brief(task: str, style_name: str = "") -> dict:
    """Produce a structured per-run brand brief from the task text.

    Returns a dict with:
      - brand_name:      e.g. "AURUM"
      - industry_brief:  symbol_concepts / aesthetic_refs / environment_refs
      - style_name:      the chosen doctrine (passed through for the brief)
      - prompt_templates: dict[asset_type → str] with placeholders filled
    """
    name = _extract_brand_name(task)
    ind = _match_industry(task)

    # Pick ONE concept / ONE aesthetic / up to 3 environment refs for the
    # brief. Deterministic index (hash of brand+style) so repeated runs on
    # the same brand+style get the SAME brief — avoids drift.
    seed = hash((name, style_name)) & 0xFFFFFFFF
    sym = ind["symbol_concepts"][seed % len(ind["symbol_concepts"])]
    aes = ind["aesthetic_refs"][(seed >> 8) % len(ind["aesthetic_refs"])]
    envs = [
        ind["environment_refs"][(seed + i) % len(ind["environment_refs"])]
        for i in range(min(3, len(ind["environment_refs"])))
    ]

    # Concrete prompt templates. Drone picks the right one based on
    # save_path and substitutes its specific subject description.
    # Note: NO brand-name placeholder in the prompts. The name shows up
    # only in the save_path and the <img alt> in JSX.
    templates = {
        "logo": (
            f"{sym}, {aes}, centered on dark field, clean silhouette, "
            f"no text, no lettering, hard edges, printable as a single-color "
            f"emblem. Pass mode='icon' so the magenta chromakey drops out."
        ),
        "hero": (
            f"<primary-subject> in {envs[0]}, cinematic lighting, "
            f"editorial composition, wide angle, {aes.replace('mark', 'tone')}."
        ),
        "product": (
            f"<subject> photographed {envs[1] if len(envs) > 1 else envs[0]}, "
            f"product-studio lighting, single directional highlight, matte "
            f"surface response, hero side-profile."
        ),
        "portrait": (
            f"<person's role> portrait in {envs[2] if len(envs) > 2 else envs[0]}, "
            f"warm directional light, tactile textures visible, editorial "
            f"photography, no visible branding."
        ),
        "environment": (
            f"<environment description>, {envs[0]}, golden-hour palette, "
            f"architectural photography, no people no vehicles."
        ),
    }

    return {
        "brand_name": name,
        "industry_brief": ind,
        "style_name": style_name,
        "symbol_concept": sym,
        "aesthetic_reference": aes,
        "environment_refs": envs,
        "prompt_templates": templates,
    }


def format_brand_directive(brief: dict) -> str:
    """Render the brief as a compact directive block for the drone's
    context. Compressed — one line per asset template; the anti-wordmark
    rule stated once; brand name only in the header (don't repeat it in
    each template).
    """
    if not brief or not brief.get("brand_name"):
        return ""
    name = brief["brand_name"]
    t = brief["prompt_templates"]
    return (
        f"\n\n=== BRAND {name} ===\n"
        f"Use these prompt templates for generate_image. Fill <…>. "
        f"NEVER include {name!r} as text in the prompt — put it only in "
        f"save_path and <img alt>.\n"
        f"BUDGET: 3 images max for a typical landing/brand page (logo + hero "
        f"+ one product OR one environment). Only reach for PORTRAIT and the "
        f"remaining slots if the task explicitly asks for a founder shot, a "
        f"gallery, or a multi-model catalog. Missing optional images render "
        f"as broken <img> — that is fine; vision gate only flags critical.\n"
        f"SYMBOL: {brief['symbol_concept']}\n"
        f"AESTHETIC: {brief['aesthetic_reference']}\n"
        f"ENVIRONMENTS: {', '.join(brief['environment_refs'])}\n"
        f"LOGO     → {t['logo']}\n"
        f"HERO     → {t['hero']}\n"
        f"PRODUCT  → {t['product']}\n"
        f"PORTRAIT → {t['portrait']}\n"
        f"ENV      → {t['environment']}\n"
        f"=== END BRAND ===\n"
    )


def write_brief_file(brief: dict, project_dir: Path) -> Path:
    """Persist the brief to <project>/.tsunami/brand_brief.json for audit."""
    out = project_dir / ".tsunami" / "brand_brief.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(brief, indent=2))
    return out


__all__ = [
    "generate_brand_brief",
    "format_brand_directive",
    "write_brief_file",
]
