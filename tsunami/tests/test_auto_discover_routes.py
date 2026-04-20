"""Tests for tsunami/game_content/_auto_discover_routes.

This function runs at module import and appends routes for every
essence with a `## Content Catalog` section that isn't already in the
hand-curated `_GAME_SIGNALS`. Its variant-derivation rules are the
thin glue between "operator adds a catalog to a new essence" and
"the keyword-router picks it up on matching prompts".

A bug in the derivation rules would silently degrade routing — the
essence's content never gets injected because prompts don't match
its auto-generated variants. These tests pin the derivation logic
without requiring a real essence file.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO))


def _make_essence(tmp: Path, stem: str, title: str, body_extra: str = "") -> Path:
    md = tmp / f"{stem}.md"
    md.write_text(
        f"---\n"
        f"title: {title}\n"
        f"---\n"
        f"# {title}\n\n"
        f"## Content Catalog\n"
        f"### Enemies\n"
        f"- Something\n"
        f"{body_extra}\n"
    )
    return md


def _patched_discover(tmp_essence_dir: Path) -> list:
    """Invoke _auto_discover_routes with a patched essence dir."""
    from tsunami import game_content as gc
    original = gc._ESSENCE_DIR
    # Also patch existing_stems by temporarily clearing _GAME_SIGNALS
    # — this is a read in the function, so we just need the essence
    # stems not to be present.
    gc._ESSENCE_DIR = tmp_essence_dir
    try:
        routes = gc._auto_discover_routes()
    finally:
        gc._ESSENCE_DIR = original
    return routes


def test_basic_title_becomes_single_variant():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _make_essence(tmp, "super_mario_bros", "Super Mario Bros")
        routes = _patched_discover(tmp)
        # find our essence in routes
        stem_routes = [variants for variants, stem in routes if stem == "super_mario_bros"]
        assert stem_routes, f"route missing for super_mario_bros: {routes}"
        variants = stem_routes[0]
        assert "super mario bros" in variants


def test_period_stripped_variant():
    """title 'Super Mario Bros.' → includes 'super mario bros' (period stripped)."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _make_essence(tmp, "smb", "Super Mario Bros.")
        routes = _patched_discover(tmp)
        variants = next(v for v, s in routes if s == "smb")
        # Title is stripped of trailing period by rstrip, so "super mario bros"
        # should appear. Internal periods would also get stripped.
        assert "super mario bros" in variants


def test_ampersand_variant():
    """title with '&' produces 'and' variant too."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _make_essence(tmp, "ratchet_and_clank", "Ratchet & Clank")
        routes = _patched_discover(tmp)
        variants = next(v for v, s in routes if s == "ratchet_and_clank")
        assert "ratchet & clank" in variants
        assert "ratchet and clank" in variants


def test_colon_post_subtitle_variant():
    """'X: Y' produces 'x: y' AND 'y' (post-colon subtitle).
    Pre-colon franchise name is INTENTIONALLY NOT auto-generated."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _make_essence(tmp, "tloz_ww", "The Legend of Zelda: The Wind Waker")
        routes = _patched_discover(tmp)
        variants = next(v for v, s in routes if s == "tloz_ww")
        # Post-colon subtitle must be there
        assert any("wind waker" in v for v in variants)
        # Pre-colon franchise "the legend of zelda" should NOT be a variant
        # (would collide with every other Zelda game)
        assert "the legend of zelda" not in variants


def test_apostrophe_s_variant():
    """'Tom Clancy's Splinter Cell' → also produces 'splinter cell'."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _make_essence(tmp, "splinter_cell", "Tom Clancy's Splinter Cell")
        routes = _patched_discover(tmp)
        variants = next(v for v, s in routes if s == "splinter_cell")
        assert "tom clancy's splinter cell" in variants
        assert "splinter cell" in variants


def test_leading_article_strip():
    """'The Wind Waker' → also 'wind waker'."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _make_essence(tmp, "ww", "The Wind Waker")
        routes = _patched_discover(tmp)
        variants = next(v for v, s in routes if s == "ww")
        assert "the wind waker" in variants
        assert "wind waker" in variants


def test_roman_to_arabic_numeral():
    """'Final Fantasy VII' → also 'final fantasy 7'."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _make_essence(tmp, "ff7", "Final Fantasy VII")
        routes = _patched_discover(tmp)
        variants = next(v for v, s in routes if s == "ff7")
        assert "final fantasy vii" in variants
        assert "final fantasy 7" in variants


def test_initialism_three_words():
    """'Grand Theft Auto III' → 'gta iii' + 'gta 3' (initialism + numeral)."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _make_essence(tmp, "gta3", "Grand Theft Auto III")
        routes = _patched_discover(tmp)
        variants = next(v for v, s in routes if s == "gta3")
        assert "gta 3" in variants or "gta3" in variants or "gta iii" in variants, (
            f"initialism variants missing from: {variants}"
        )


def test_stopword_only_variants_dropped():
    """A variant that's just 'the' / 'of' / 'a' gets dropped."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _make_essence(tmp, "x", "The")  # degenerate title
        routes = _patched_discover(tmp)
        stem_routes = [(v, s) for v, s in routes if s == "x"]
        if stem_routes:
            variants = stem_routes[0][0]
            assert "the" not in variants
            assert "" not in variants


def test_essence_without_content_catalog_skipped():
    """If ## Content Catalog section is absent, route isn't generated."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        md = tmp / "x.md"
        md.write_text("---\ntitle: Foo Bar\n---\n# Foo Bar\n(no catalog here)\n")
        from tsunami import game_content as gc
        orig = gc._ESSENCE_DIR
        gc._ESSENCE_DIR = tmp
        try:
            routes = gc._auto_discover_routes()
        finally:
            gc._ESSENCE_DIR = orig
        assert not any(s == "x" for _, s in routes), (
            "essence without Content Catalog must not auto-discover"
        )


def main():
    tests = [
        test_basic_title_becomes_single_variant,
        test_period_stripped_variant,
        test_ampersand_variant,
        test_colon_post_subtitle_variant,
        test_apostrophe_s_variant,
        test_leading_article_strip,
        test_roman_to_arabic_numeral,
        test_initialism_three_words,
        test_stopword_only_variants_dropped,
        test_essence_without_content_catalog_skipped,
    ]
    failed = []
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except AssertionError as e:
            print(f"FAIL  {t.__name__}: {e}")
            failed.append(t.__name__)
        except Exception as e:
            print(f"ERROR {t.__name__}: {type(e).__name__}: {e}")
            failed.append(t.__name__)
    print()
    if failed:
        print(f"RESULT: {len(failed)}/{len(tests)} failed: {failed}")
        sys.exit(1)
    print(f"RESULT: {len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
