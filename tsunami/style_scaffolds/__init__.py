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
    # High-specificity routes first — multi-word phrases take priority
    # over the single-word category words that follow.
    (("brutalist", "brutalism", "raw html", "anti-design"), "brutalist_web"),
    (("editorial long-form", "long form", "kinfolk", "cereal",
      "apartamento", "gentlewoman", "personal essays", "cultural commentary",
      "lifestyle blog", "wellness blog", "holistic", "writer's site",
      "book signing", "author", "novel", "memoir", "short stories",
      "travel blog", "food blog", "recipe blog"),
     "magazine_editorial"),
    (("swiss", "müller-brockmann", "muller-brockmann", "grid-strict",
      "helvetica", "strict grid", "functional typography"), "swiss_modern"),
    (("playful", "stripe-style", "linear-style", "mesh gradient",
      "bento grid", "chromatic", "syne", "bricolage"), "playful_chromatic"),
    (("editorial dark", "luxury dark", "apple-style", "tesla-style",
      "noir"), "editorial_dark"),
    (("photographer", "photo portfolio", "photo studio",
      "portfolio site", "creative director", "visual storyteller",
      "design portfolio", "designer portfolio", "artist portfolio",
      "graphic designer", "product designer", "brand designer",
      "illustrator", "visual design"),
     "photo_studio"),
    (("band", "music site", "album", "film studio", "nightclub",
      "cinematic dark", "bebas", "anton", "oversized display",
      "songwriter", "songwriting", "singer", "musician", "dj ",
      "record label", "tour dates", "merch store"),
     "cinematic_display"),
    (("newspaper", "news site", "newsroom", "broadsheet", "tribune",
      "chronicle", "daily paper", "trade publication", "local news",
      "breaking news"),
     "newsroom_editorial"),
    (("atelier", "handcraft", "handcrafted", "handmade", "ceramics",
      "ceramic", "studio brand", "dtc", "small brand", "craft brand",
      "cream palette", "homeware", "stoneware", "pottery",
      "pet boarding", "pet care", "dog boarding", "pet daycare",
      "animal shelter", "rescue",
      "wedding", "bridal", "florist",
      "wellness platform", "holistic wellness",
      "boutique hotel", "bed and breakfast"),
     "atelier_warm"),
    (("saas", "dashboard", "admin", "crm", "tracker", "dev tool",
      "shadcn", "utility app", "startup landing", "tier comparison",
      "habit tracker", "expense tracker", "bug tracker",
      "growth marketing", "product launch", "b2b saas",
      "ai studio", "ai platform", "ai tool",
      "tracking tool", "calculator", "internal tool", "calculator tool",
      "conference", "event platform", "event hub",
      "mood board", "preview tool", "editor tool"),
     "shadcn_startup"),
    # Low-specificity single-word fallbacks — placed LAST so multi-word
    # routes match first. These cover the bare-word cases common in the
    # corpus (titles like "Portfolio — Brand & Visual Design").
    (("portfolio",), "photo_studio"),
    (("magazine",), "magazine_editorial"),
    (("blog",), "magazine_editorial"),
]


def _available_styles() -> list[str]:
    return sorted(p.stem for p in _HERE.glob("*.md"))


def _load(name: str) -> str | None:
    path = _HERE / f"{name}.md"
    if not path.is_file():
        return None
    return path.read_text()


_ANCHOR_RE = re.compile(r"^anchors:\s*(.+?)\s*$", re.MULTILINE)
_CORPUS_RE = re.compile(r"(\d+)\s*/\s*155", re.IGNORECASE)
_CORPUS_FIELD_RE = re.compile(r"^corpus_share:\s*(\d+)\s*$", re.MULTILINE)


def _style_weight(body: str) -> float:
    """Weight a style by its grounding in the scraped corpus.

    Priority order — first signal wins:
      1. Explicit `(none in corpus — ...)` in anchors field → 0.0
         (escape hatches must be keyword-routed, not randomly selected).
      2. `corpus_share: N` frontmatter — the calibrated, deliberate share.
         This is the preferred way for a doctrine to declare its weight.
      3. Any "<N>/155" mention in the body — legacy prose-based signal.
         Less reliable because an evidence note may cite a parent vertical
         ("portfolio = 40/155") rather than the doctrine's own share.
      4. Comma-separated anchor slug count — each listed template = 1.
      5. Fallback 1.0 for styles without evidence (don't exclude, just
         keep them low-weight until corpus data lands).
    """
    m_anchors = _ANCHOR_RE.search(body)
    if m_anchors:
        anchors_line = m_anchors.group(1).strip()
        if "none" in anchors_line.lower() or anchors_line.startswith("("):
            return 0.0

    m_field = _CORPUS_FIELD_RE.search(body)
    if m_field:
        return float(m_field.group(1))

    m_corpus = _CORPUS_RE.search(body)
    if m_corpus:
        return float(m_corpus.group(1))

    if m_anchors:
        count = sum(1 for a in m_anchors.group(1).split(",") if a.strip())
        return float(count) if count else 1.0
    return 1.0


def pick_style(task: str, scaffold: str = "", seed: int | None = None) -> tuple[str, str]:
    """Return (style_name, style_body) for a task.

    Resolution order:
      0. env TSUNAMI_STYLE_SEED=<path_or_url> — extract palette + VLM
         mood + closest doctrine, synthesize a hybrid body where the seed
         image overrides the matched doctrine's palette. Returns name
         prefixed `seed_<base>` so logs trace provenance.
      1. env TSUNAMI_STYLE=<name>
      2. keyword match in task text
      3. corpus-weighted random choice from scaffolds whose `applies_to`
         frontmatter lists `scaffold` (or contains '*'). Weight comes
         from corpus_share frontmatter or anchor count. Zero-weight
         styles (brutalist) never land here — they're keyword-only.
      4. empty ("", "") — no style injection
    """
    seed_path = os.environ.get("TSUNAMI_STYLE_SEED")
    if seed_path:
        try:
            from . import seed_from_image as _sfi
            seed_record = _sfi.extract_seed(seed_path)
            return _sfi.synthesize_seeded_style(seed_record)
        except Exception as e:
            # Graceful fallback — log and continue through the normal pipeline
            # so a misconfigured seed doesn't break delivery.
            import logging
            logging.getLogger("tsunami.style_scaffolds").warning(
                "TSUNAMI_STYLE_SEED resolution failed (%s): %s — falling through",
                seed_path, e,
            )

    forced = os.environ.get("TSUNAMI_STYLE")
    if forced:
        body = _load(forced)
        if body:
            return forced, body

    # Delegate keyword matching to the unified routing module so
    # word-boundary + multi-word substring rules live in one place.
    from ..routing import match_first
    name = match_first(task, _KEYWORD_MAP, default="")
    # F-C1 telemetry — logs even on non-match so the stall-report
    # sees fall-through frequency for styles.
    try:
        from ..routing_telemetry import log_pick
        log_pick("style", task, name, default="",
                 match_source="default" if not name else "keyword")
    except Exception:
        pass
    if name:
        body = _load(name)
        if body:
            # F-E3 doctrine-history wiring — only log if the style
            # actually survived the body-load step (we're about to
            # inject it). Output Quality Gradient cold-start cohort is
            # counted from here.
            try:
                from ..doctrine_history import log_pick as _dh_log
                _dh_log("style", name, scaffold=scaffold)
            except Exception:
                pass
            return name, body

    # Corpus-weighted random among applicable.
    applicable: list[tuple[str, float]] = []
    for p in _HERE.glob("*.md"):
        text = p.read_text()
        m = re.search(r"applies_to:\s*\[([^\]]+)\]", text)
        if not m:
            continue
        targets = [t.strip().strip('"').strip("'") for t in m.group(1).split(",")]
        if scaffold and "*" not in targets and scaffold not in targets:
            continue
        w = _style_weight(text)
        if w <= 0:
            continue  # escape-hatch doctrines — keyword-only
        applicable.append((p.stem, w))
    if not applicable:
        return "", ""
    rng = random.Random(seed) if seed is not None else random
    names = [a[0] for a in applicable]
    weights = [a[1] for a in applicable]
    chosen = rng.choices(names, weights=weights, k=1)[0]
    # F-C1 telemetry + F-E3 doctrine history for the corpus-weighted
    # random tier (otherwise style picks taken via this path never
    # surface in the stall report or the cold-start cohort).
    try:
        from ..routing_telemetry import log_pick as _rt_log
        _rt_log("style", task, chosen, default="", match_source="random")
        from ..doctrine_history import log_pick as _dh_log
        _dh_log("style", chosen, scaffold=scaffold)
    except Exception:
        pass
    return chosen, _load(chosen) or ""


_MODE_RE = re.compile(r"^default_mode\s*:\s*(light|neutral|dark)\s*$", re.MULTILINE)


def _doctrine_mode(body: str) -> str:
    """Parse `default_mode: light|neutral|dark` from frontmatter; fallback dark.

    Three modes reflect the three surface families in the scraped corpus:
      - light   — pure-white / near-white (#fff, #fafafa). 69% of corpus.
      - neutral — warm-cream / bone / sand (`40 33% 96%`). ~17%.
      - dark    — near-black (#0a0a0a, #000). ~14%.

    Dark is the scaffold's baseline in index.css, so doctrines without a
    declared mode get dark (legacy-compatible).
    """
    m = _MODE_RE.search(body)
    return m.group(1) if m else "dark"


_MODE_NOTES = {
    "light": (
        "SCAFFOLD ACTIVATION: this doctrine wants a LIGHT surface. At the\n"
        "VERY TOP of src/App.tsx, ensure these TWO imports appear as the\n"
        "first lines, in this order:\n"
        "    import './index.css';\n"
        "    import './tokens_light.css';\n"
        "Order is load-bearing: tokens_light.css overrides :root vars set\n"
        "by index.css — reversed order leaves dark tokens winning. If\n"
        "App.tsx already has `import './index.css';`, add only the second\n"
        "import immediately after it. If neither is present (auth-app /\n"
        "ai-app scaffolds), add both. tokens_light.css ships in the\n"
        "scaffold — shadcn-aligned light tokens (pure white bg, near-black\n"
        "text, system sans). Do NOT edit src/main.tsx — it's scaffold\n"
        "infrastructure and the drone gate rejects writes there.\n"
    ),
    "neutral": (
        "SCAFFOLD ACTIVATION: this doctrine wants a NEUTRAL (warm-paper)\n"
        "surface. At the VERY TOP of src/App.tsx, ensure these TWO imports\n"
        "appear as the first lines, in this order:\n"
        "    import './index.css';\n"
        "    import './tokens_neutral.css';\n"
        "Order is load-bearing: tokens_neutral.css overrides :root vars\n"
        "set by index.css — reversed order leaves dark tokens winning. If\n"
        "App.tsx already has `import './index.css';`, add only the second\n"
        "import immediately after it. If neither is present (auth-app /\n"
        "ai-app scaffolds), add both. tokens_neutral.css sets warm-cream\n"
        "tokens (hsl(40 33% 96%) bg, warm near-black text, serif-first\n"
        "font stack). Do NOT edit src/main.tsx — scaffold infrastructure,\n"
        "the drone gate rejects writes there. Do not use pure white —\n"
        "destroys the handcraft / editorial / atelier mood.\n"
    ),
    "dark": "",  # scaffold default; no import needed
}


_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_INFO_SECTION_RE = re.compile(
    r"## (?:Reference sites(?: \([^)]*\))?|Evidence note|Evidence|Examples?|Corpus evidence|Sources?)"
    r"\b.*?(?=\n## |\Z)",
    re.DOTALL | re.IGNORECASE,
)
_FRONTMATTER_RE = re.compile(r"^---\n.*?\n---\n?", re.DOTALL)
_MULTI_BLANK_RE = re.compile(r"\n{3,}")


def compact_body(body: str) -> str:
    """Strip non-actionable prose from a style-scaffold body for drone
    injection. Humans read the full .md (with Evidence note, Reference
    sites, corpus provenance); the drone only needs the actionable
    palette / typography / layout / motion sections.

    Removed:
      - YAML frontmatter (the _doctrine_mode parser reads the raw body
        beforehand; once that's extracted the frontmatter is noise in
        the drone's context).
      - HTML comments (always human-only).
      - "## Reference sites" sections.
      - "## Evidence note" / "## Evidence" / "## Examples" / "## Sources"
        sections.
      - Collapsed runs of blank lines.

    Empirically ~25-35% reduction on today's 10-doctrine library —
    700+ chars / ~175 tokens saved per injection, without losing any
    actionable instruction.
    """
    s = body
    s = _FRONTMATTER_RE.sub("", s)
    s = _COMMENT_RE.sub("", s)
    s = _INFO_SECTION_RE.sub("", s)
    s = _MULTI_BLANK_RE.sub("\n\n", s).strip()
    return s


def format_style_directive(name: str, body: str, *, compact: bool = True) -> str:
    """Render the style body as a task-prepended directive block.

    `compact=True` (default) strips non-actionable sections via
    compact_body() — ~25-35% token reduction. Pass compact=False to
    inject the raw .md (useful for debugging / audit / tests).
    """
    if not name or not body:
        return ""
    mode = _doctrine_mode(body)
    token_note = "\n" + _MODE_NOTES[mode] if _MODE_NOTES[mode] else ""
    rendered = compact_body(body) if compact else body
    return (
        f"\n\n=== STYLE: {name} ===\n"
        f"Embody this doctrine; override scaffold defaults where they conflict.\n"
        f"{token_note}"
        f"\n{rendered}\n"
        f"=== END STYLE ===\n"
    )


__all__ = ["pick_style", "format_style_directive", "compact_body"]
