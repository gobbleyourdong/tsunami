"""Tests for the per-genre content-pool injector (F-I3b).

Implements the pytest scenarios from
`scaffolds/.claude/CONTENT_INJECTOR_SPEC.md` §8.

The injector generalizes F-I3 (per-game content directive) to every
genre by pulling canonical names from GENRE_CONTENT_POOL.md when the
prompt names no specific title but pick_genre returns a supported
genre.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO))

from tsunami.genre_scaffolds.content_pool import (  # noqa: E402
    _load_genre_content_pool,
    format_genre_content_directive,
    should_emit_genre_pool,
)


# ----- Pool parsing ---------------------------------------------------------

class TestPoolParsing:
    def test_parses_action_adventure_with_enemies(self):
        """GENRE_CONTENT_POOL.md parses → action_adventure has ≥5 enemies."""
        pool = _load_genre_content_pool()
        assert "action_adventure" in pool
        enemies = pool["action_adventure"].get("enemies", [])
        assert len(enemies) >= 5
        for e in enemies:
            assert isinstance(e["year"], int)
            assert 1970 < e["year"] < 2030
            assert e["title"]
            assert e["name"]

    def test_parses_all_registered_genres(self):
        """Every genre the wave can detect should be present (minus
        open_world which is intentionally unsupported)."""
        pool = _load_genre_content_pool()
        expected = {
            "action_adventure", "fighting", "platformer", "jrpg",
            "fps", "rts", "stealth",
        }
        assert expected.issubset(set(pool.keys()))

    def test_canonical_names_survive_parse(self):
        """Spot-check: canonical names should all parse cleanly."""
        pool = _load_genre_content_pool()
        aa = pool["action_adventure"]
        aa_enemy_names = {e["name"] for e in aa.get("enemies", [])}
        aa_boss_names = {e["name"] for e in aa.get("bosses", [])}
        aa_item_names = {e["name"] for e in aa.get("items", [])}
        # Zelda canonicals — AUDIT Round T's 18% adoption target:
        assert "Octorok" in aa_enemy_names
        assert "Aquamentus" in aa_boss_names
        assert "Wooden Sword" in aa_item_names


# ----- Directive formatting ------------------------------------------------

class TestDirectiveFormat:
    def test_zelda_style_prompt_emits_octorok(self):
        """action_adventure pool contains Octorok and the directive
        surfaces it under 'Enemies'."""
        directive = format_genre_content_directive(
            "action_adventure", "make me a zelda-like top-down adventure",
        )
        assert "Octorok" in directive
        assert "=== GENRE CONTENT POOL:" in directive
        assert "=== END GENRE CONTENT POOL ===" in directive

    def test_ff_prompt_narrows_to_final_fantasy(self):
        """'final fantasy' prompt narrows jrpg pool so FF-lineage names
        surface. The corpus uses 'Final Fantasy classes' as a title
        tag for FF1-era class names — these should survive narrowing
        even though other entries use abbreviated 'FF 1' / 'FF IV'
        titles that the naive tokenizer misses."""
        directive = format_genre_content_directive(
            "jrpg", "make me a final fantasy style rpg",
        )
        # Any of the four FF1 class names lands — they all share
        # attribution 'Final Fantasy classes' which matches 'final' + 'fantasy'.
        assert any(n in directive for n in (
            "Black Mage", "Red Mage", "White Mage", "Monk", "Thief",
            "Warrior of Light", "Fighter",
        ))

    def test_generic_platformer_falls_back_to_full_pool(self):
        """Generic prompt with no title-keyword → no narrowing → full
        pool surfaces SMB canonicals."""
        directive = format_genre_content_directive(
            "platformer", "make me a 2d platformer for mobile",
        )
        # Goomba is the SMB-1985 canonical enemy.
        assert "Goomba" in directive

    def test_empty_genre_returns_empty(self):
        """Unsupported genre → empty string. Wave falls back to scaffold
        md alone."""
        assert format_genre_content_directive("open_world", "any") == ""
        assert format_genre_content_directive("nonexistent_genre", "x") == ""

    def test_directive_has_all_role_headers_when_pool_rich(self):
        """A pool-rich genre (action_adventure) surfaces all 5 role
        sections in the directive."""
        directive = format_genre_content_directive(
            "action_adventure", "zelda-like",
        )
        assert "Enemies (" in directive
        assert "Bosses (" in directive
        assert "Items (" in directive
        assert "Levels (" in directive
        assert "NPCs:" in directive

    def test_per_role_count_override(self):
        """Custom counts narrow the output."""
        big = format_genre_content_directive(
            "platformer", "any platformer",
        )
        small = format_genre_content_directive(
            "platformer", "any platformer",
            counts={"enemies": 2, "bosses": 1, "items": 2, "levels": 2, "npcs": 2},
        )
        # Smaller count → fewer Goomba/Koopa/etc. bullet entries.
        assert small.count("\n- ") < big.count("\n- ")


# ----- F-I3 priority gating -----------------------------------------------

class TestPriorityGating:
    def test_should_emit_false_when_fi3_hits(self):
        """When F-I3 hits, F-I3b should short-circuit."""
        assert should_emit_genre_pool("zelda-like adventure", fi3_hit=True) is False

    def test_should_emit_true_when_fi3_misses(self):
        """When F-I3 returns empty, F-I3b takes over."""
        assert should_emit_genre_pool("2d platformer", fi3_hit=False) is True

    def test_should_emit_false_for_empty_prompt(self):
        """Empty prompt → no injection. Nothing to narrow against."""
        assert should_emit_genre_pool("", fi3_hit=False) is False
        assert should_emit_genre_pool("   ", fi3_hit=False) is False


# ----- Mtime cache ---------------------------------------------------------

class TestCacheBehavior:
    def test_repeated_load_is_cached(self):
        """Back-to-back loads return the same dict object (same mtime)."""
        pool1 = _load_genre_content_pool()
        pool2 = _load_genre_content_pool()
        assert pool1 is pool2


# ----- F-I3 ↔ F-I3b integration surface (spec §3 interaction rule) --------

class TestFI3FI3bInteraction:
    """Integration-level surface: F-I3 (per-game) takes priority; F-I3b
    (per-genre) fills in when F-I3 missed. Exercises the two injectors
    together via the same gating logic agent.py uses at line ~1647."""

    def test_zelda_prompt_prefers_fi3_over_fi3b(self):
        """A 'zelda-like' prompt should trigger F-I3 (pick_game_replica
        returns the Zelda essence). should_emit_genre_pool must return
        False so F-I3b doesn't double-inject."""
        from tsunami.game_content import pick_game_replica
        essence = pick_game_replica("make me a zelda-like top-down adventure")
        # F-I3 hits — essence is truthy.
        assert essence
        # F-I3b gates off.
        assert should_emit_genre_pool(
            "make me a zelda-like top-down adventure", fi3_hit=bool(essence),
        ) is False

    def test_generic_platformer_triggers_fi3b_only(self):
        """Generic '2D platformer' with no title named → F-I3 returns
        empty. F-I3b then injects the full platformer pool."""
        from tsunami.game_content import pick_game_replica
        essence = pick_game_replica("make me a 2d platformer for mobile")
        # F-I3 misses — essence is empty/falsy.
        assert not essence
        # F-I3b takes over.
        assert should_emit_genre_pool(
            "make me a 2d platformer for mobile", fi3_hit=bool(essence),
        ) is True
        directive = format_genre_content_directive(
            "platformer", "make me a 2d platformer for mobile",
        )
        assert "Goomba" in directive
        assert "=== GENRE CONTENT POOL:" in directive
