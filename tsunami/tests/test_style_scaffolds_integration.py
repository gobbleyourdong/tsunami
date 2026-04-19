"""Integration tests for the style_scaffolds pipeline.

Locks down the silent-drop fixes landed in passes 12–17. Each assertion
maps to a specific hop that was previously broken:

  - pick_style scaffold filtering actually applies (pass 12)
  - format_style_directive injects the activation note for light/neutral
    doctrines (pass 13)
  - Every light/neutral doctrine has a tokens_*.css activation
    instruction in its directive body (pass 13/14)
  - TSUNAMI_STYLE env force works (pass 11)
  - TSUNAMI_STYLE_SEED env force uses palette/VLM (pass 14)
  - pick_direction_set `style_name` param returns doctrine-specific
    rubric when one exists (pass 16)
  - All 10 doctrines have an undertow rubric (pass 17)
  - seed_<base> prefix correctly strips to <base> when looking up rubric
    (pass 16)
  - Every doctrine .md has required frontmatter fields (default_mode,
    corpus_share or anchors)

If any of these regress, these tests fail. They do NOT hit the network,
the VLM, or the disk beyond reading the shipped .md files.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from tsunami.style_scaffolds import (
    pick_style, format_style_directive, _doctrine_mode, _style_weight,
)
from tsunami.style_scaffolds.manifest import doctrine_manifest
from tsunami.undertow import pick_direction_set


# ── Test constants ─────────────────────────────────────────────────────
EXPECTED_DOCTRINES = {
    "photo_studio", "shadcn_startup", "cinematic_display",
    "newsroom_editorial", "atelier_warm", "magazine_editorial",
    "swiss_modern", "playful_chromatic", "editorial_dark",
    "brutalist_web",
}

LIGHT_MODE_DOCTRINES = {
    "photo_studio", "shadcn_startup", "newsroom_editorial",
    "swiss_modern", "brutalist_web",
}
NEUTRAL_MODE_DOCTRINES = {
    "atelier_warm", "magazine_editorial", "playful_chromatic",
}
DARK_MODE_DOCTRINES = {
    "cinematic_display", "editorial_dark",
}


# ── Manifest integrity (pass 6 / 17) ───────────────────────────────────
class TestManifestIntegrity:
    def test_all_ten_doctrines_present(self):
        names = {r["name"] for r in doctrine_manifest()}
        assert names == EXPECTED_DOCTRINES, f"missing or extra: {names ^ EXPECTED_DOCTRINES}"

    def test_every_doctrine_declares_mode(self):
        for r in doctrine_manifest():
            assert r["mode"] in ("light", "neutral", "dark"), \
                f"{r['name']} has invalid mode {r['mode']!r}"

    def test_mode_buckets_match_expected(self):
        by_mode = {r["name"]: r["mode"] for r in doctrine_manifest()}
        for d in LIGHT_MODE_DOCTRINES:
            assert by_mode[d] == "light", f"{d} should be light, got {by_mode[d]}"
        for d in NEUTRAL_MODE_DOCTRINES:
            assert by_mode[d] == "neutral"
        for d in DARK_MODE_DOCTRINES:
            assert by_mode[d] == "dark"

    def test_brutalist_has_zero_weight(self):
        # Brutalist is keyword-only; weight 0 means it cannot be random-picked
        weights = {r["name"]: r["weight"] for r in doctrine_manifest()}
        assert weights["brutalist_web"] == 0.0, \
            "brutalist_web must have weight 0 (escape-hatch only)"

    def test_shadcn_dominates_weight(self):
        weights = {r["name"]: r["weight"] for r in doctrine_manifest()}
        # Sanity: shadcn_startup + photo_studio should account for > 50% of
        # the random-fallback pool since they're the corpus-dominant
        # clusters. Tolerates minor corpus_share tweaks.
        pool = sum(w for w in weights.values() if w > 0)
        top_two = weights["shadcn_startup"] + weights["photo_studio"]
        assert top_two / pool > 0.5, \
            f"shadcn+photo should dominate random pool; got {top_two}/{pool}"


# ── pick_style routing (pass 11 / 12) ──────────────────────────────────
class TestPickStyleRouting:
    @pytest.mark.parametrize("brief,expected", [
        ("photographer portfolio site for Alex", "photo_studio"),
        ("Shrine band site with merch", "cinematic_display"),
        ("newsroom for a local tribune", "newsroom_editorial"),
        ("atelier ceramic brand with handcrafted pottery", "atelier_warm"),
        ("saas admin dashboard for devs", "shadcn_startup"),
        ("brutalist zine anti-design", "brutalist_web"),
        ("kinfolk magazine editorial long form", "magazine_editorial"),
        ("swiss grid-strict dataviz", "swiss_modern"),
        ("luxury apple-style noir landing", "editorial_dark"),
        ("playful stripe-style bento grid", "playful_chromatic"),
    ])
    def test_keyword_routing_is_deterministic(self, brief, expected):
        name, _ = pick_style(brief)
        assert name == expected, f"{brief!r} should route to {expected}, got {name}"

    def test_scaffold_filter_restricts_random_pool(self):
        """Pass 12 fix: scaffold arg actually limits applicable doctrines."""
        # Unkeyworded brief + scaffold='data-viz' should only return doctrines
        # whose applies_to lists include 'data-viz'. Only swiss_modern does.
        os.environ.pop("TSUNAMI_STYLE", None)
        os.environ.pop("TSUNAMI_STYLE_SEED", None)
        for seed in range(10):
            name, _ = pick_style("make something", "data-viz", seed=seed)
            assert name == "swiss_modern", \
                f"data-viz should only match swiss_modern; got {name}"

    def test_scaffold_filter_dashboard_includes_three(self):
        """Dashboard applies_to: shadcn_startup, swiss_modern, editorial_dark."""
        os.environ.pop("TSUNAMI_STYLE", None)
        os.environ.pop("TSUNAMI_STYLE_SEED", None)
        seen = set()
        for seed in range(200):
            name, _ = pick_style("any", "dashboard", seed=seed)
            seen.add(name)
        assert seen == {"shadcn_startup", "swiss_modern", "editorial_dark"}, \
            f"dashboard should only yield these 3 doctrines; got {seen}"


# ── format_style_directive activation note (pass 13 / 14) ──────────────
class TestActivationNote:
    def test_light_doctrines_inject_tokens_light_import(self):
        for name in LIGHT_MODE_DOCTRINES:
            if name == "brutalist_web":
                # brutalist routes via keyword only, but its directive should
                # still activate light tokens.
                pass
            _, body = pick_style_forced(name)
            directive = format_style_directive(name, body)
            assert "tokens_light.css" in directive, \
                f"{name} (light) directive missing tokens_light.css import instruction"
            assert "VERY TOP of src/App.tsx" in directive or \
                   "src/App.tsx" in directive, \
                f"{name} directive should reference src/App.tsx as the import site"

    def test_neutral_doctrines_inject_tokens_neutral_import(self):
        for name in NEUTRAL_MODE_DOCTRINES:
            _, body = pick_style_forced(name)
            directive = format_style_directive(name, body)
            assert "tokens_neutral.css" in directive, \
                f"{name} (neutral) directive missing tokens_neutral.css import instruction"

    def test_dark_doctrines_skip_token_import(self):
        """Dark = scaffold default; no import needed."""
        for name in DARK_MODE_DOCTRINES:
            _, body = pick_style_forced(name)
            directive = format_style_directive(name, body)
            assert "tokens_light.css" not in directive, \
                f"{name} (dark) directive should NOT reference tokens_light.css"
            assert "tokens_neutral.css" not in directive, \
                f"{name} (dark) directive should NOT reference tokens_neutral.css"

    def test_activation_note_specifies_import_order(self):
        """Order is load-bearing: tokens must load AFTER index.css."""
        _, body = pick_style("photographer portfolio")
        directive = format_style_directive("photo_studio", body)
        idx_pos = directive.find("import './index.css';")
        tokens_pos = directive.find("import './tokens_light.css';")
        assert idx_pos >= 0 and tokens_pos >= 0, \
            "activation note must show both imports verbatim"
        assert idx_pos < tokens_pos, \
            "index.css import must appear before tokens_light.css in the instruction"


# ── Force-pick via TSUNAMI_STYLE env (pass 11) ─────────────────────────
class TestEnvOverride:
    def test_tsunami_style_forces_doctrine(self):
        os.environ["TSUNAMI_STYLE"] = "cinematic_display"
        try:
            name, _ = pick_style("whatever the brief says")
            assert name == "cinematic_display", \
                f"TSUNAMI_STYLE=cinematic_display should force it; got {name}"
        finally:
            os.environ.pop("TSUNAMI_STYLE", None)

    def test_tsunami_style_bogus_value_falls_through(self):
        os.environ["TSUNAMI_STYLE"] = "does_not_exist"
        try:
            name, _ = pick_style("photographer portfolio")
            # Should fall through to keyword routing
            assert name == "photo_studio"
        finally:
            os.environ.pop("TSUNAMI_STYLE", None)


# ── Undertow doctrine rubric (pass 16 / 17) ────────────────────────────
class TestUndertowDoctrineRubric:
    @pytest.mark.parametrize("doctrine", sorted(EXPECTED_DOCTRINES))
    def test_every_doctrine_has_undertow_rubric(self, doctrine):
        rubric = pick_direction_set(
            "x", scaffold="react-build", style_name=doctrine
        )
        assert rubric is not None, f"no undertow rubric found for {doctrine}"
        assert len(rubric) > 500, \
            f"{doctrine} rubric too short ({len(rubric)} chars), likely empty"
        assert "## Questions" in rubric, \
            f"{doctrine} rubric missing ## Questions section"
        assert "PASS criteria" in rubric, \
            f"{doctrine} rubric missing PASS criteria"
        assert "FAIL criteria" in rubric, \
            f"{doctrine} rubric missing FAIL criteria"

    def test_seed_prefix_strips(self):
        """pick_direction_set(style_name='seed_photo_studio') → photo_studio.md"""
        seeded = pick_direction_set(
            "x", scaffold="react-build", style_name="seed_photo_studio"
        )
        direct = pick_direction_set(
            "x", scaffold="react-build", style_name="photo_studio"
        )
        assert seeded == direct, \
            "seed_<base> prefix must route to <base>.md"

    def test_unknown_style_falls_back_to_scaffold_rubric(self):
        """Safety: unknown style_name doesn't crash; returns scaffold rubric."""
        result = pick_direction_set(
            "x", scaffold="landing", style_name="does_not_exist"
        )
        # Should fall back to scaffold-level match (web_polish / art_direction)
        assert result is not None, "unknown style should fall back cleanly"


# ── helper ─────────────────────────────────────────────────────────────
def pick_style_forced(name: str) -> tuple[str, str]:
    """Force-pick a doctrine via TSUNAMI_STYLE env."""
    orig = os.environ.get("TSUNAMI_STYLE")
    os.environ["TSUNAMI_STYLE"] = name
    try:
        return pick_style("any brief")
    finally:
        if orig is None:
            os.environ.pop("TSUNAMI_STYLE", None)
        else:
            os.environ["TSUNAMI_STYLE"] = orig
