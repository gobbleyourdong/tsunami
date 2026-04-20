"""Inference-free self-check for F-A2 + F-A3 genre scaffolds.

Verifies:
  - 3 genre files present with required frontmatter fields
  - pick_genre routes canonical keywords
  - scaffold gate (non-gamedev returns empty)
  - env override wins
  - format_genre_directive wraps with MECHANIC ACTIVATION block
  - full pipeline: zelda-like prompt hits action_adventure, injects a
    directive that names real MechanicType entries
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO))

from tsunami.genre_scaffolds import (  # noqa: E402
    pick_genre, format_genre_directive, _KEYWORD_MAP,
)


# Real MechanicType names — read from schema.ts at import time via
# tsunami.engine_catalog. Single source of truth eliminates the drift
# risk of hand-maintained mirrors in both this test and gamedev_probe.
from tsunami.engine_catalog import KNOWN_MECHANIC_TYPES as _KNOWN_MECHANICS

_HERE = Path(__file__).parent.parent / "genre_scaffolds"


def _parse_frontmatter(body: str) -> dict:
    m = re.match(r"^---\n(.*?)\n---", body, re.DOTALL)
    if not m:
        return {}
    out = {}
    for line in m.group(1).splitlines():
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        out[k.strip()] = v.strip()
    return out


# ───────────── structural invariants ─────────────

def test_at_least_three_genres():
    files = sorted(p.stem for p in _HERE.glob("*.md"))
    # We ship 3 to start; back-fill rounds this to ~10.
    assert len(files) >= 3, f"expected >=3 genre files, got {files}"
    for required in ("action_adventure", "platformer", "fps"):
        assert required in files, f"{required}.md missing"


def test_frontmatter_required_fields():
    required = {"applies_to", "mood", "corpus_share",
                "default_mechanics", "recommended_mechanics",
                "would_falsify", "anchors"}
    for p in _HERE.glob("*.md"):
        fm = _parse_frontmatter(p.read_text())
        missing = required - set(fm.keys())
        assert not missing, f"{p.stem}.md missing: {missing}"


def test_default_mechanics_are_real():
    """Every default_mechanics entry must exist in the engine catalog."""
    for p in _HERE.glob("*.md"):
        fm = _parse_frontmatter(p.read_text())
        raw = fm.get("default_mechanics", "").strip("[]")
        names = {n.strip() for n in raw.split(",") if n.strip()}
        unknown = names - _KNOWN_MECHANICS
        assert not unknown, (
            f"{p.stem}.md references unknown MechanicType(s): {unknown}\n"
            f"Valid: sorted sample = {sorted(_KNOWN_MECHANICS)[:10]}..."
        )


def test_recommended_mechanics_are_real():
    for p in _HERE.glob("*.md"):
        fm = _parse_frontmatter(p.read_text())
        raw = fm.get("recommended_mechanics", "").strip("[]")
        names = {n.strip() for n in raw.split(",") if n.strip()}
        unknown = names - _KNOWN_MECHANICS
        assert not unknown, f"{p.stem}.md bad recommended: {unknown}"


def test_would_falsify_is_substantive():
    for p in _HERE.glob("*.md"):
        fm = _parse_frontmatter(p.read_text())
        wf = fm.get("would_falsify", "")
        assert len(wf) >= 60, (
            f"{p.stem}.md would_falsify too short ({len(wf)} chars) — "
            f"needs a specific measurable signal per v9.1 C5"
        )


# ───────────── routing ─────────────

def test_non_gamedev_scaffold_returns_empty():
    name, body = pick_genre("build a zelda-like top-down", "react-app")
    assert name == "" and body == "", "genre should not fire on non-gamedev"


def test_zelda_like_routes_action_adventure():
    name, body = pick_genre(
        "build a zelda-like top-down action adventure with dungeons",
        "gamedev",
    )
    assert name == "action_adventure", f"got {name}"
    # Genre doctrine names the mechanic set, not the specific content
    # (Octorok/Moblin live in the Content Catalog — F-I3 injects those
    # separately for Zelda-replica prompts). The genre body CAN
    # reference anchor-essence content names in prose — that's a
    # pointer to where the content comes from, not the content itself.
    assert "RoomGraph" in body
    assert "LockAndKey" in body
    assert "action-adventure" in body.lower() or "action adventure" in body.lower()


def test_platformer_prompt_routes_platformer():
    name, _ = pick_genre("build a simple 2d platformer", "gamedev")
    assert name == "platformer"


def test_fps_prompt_routes_fps():
    name, _ = pick_genre(
        "build a doom-like first-person shooter with keycards",
        "gamedev",
    )
    assert name == "fps"


def test_metroidvania_routes_metroidvania():
    name, _ = pick_genre("build a metroidvania with ability gates", "gamedev")
    # metroidvania.md doesn't exist yet — falls to default / random.
    # The keyword SHOULD map but the body load fails; assert graceful.
    # Until we ship metroidvania.md, this lands on a weighted-random pick.
    assert name in {"metroidvania", "action_adventure", "platformer", "fps"}


def test_env_override_wins():
    os.environ["TSUNAMI_GENRE"] = "platformer"
    try:
        name, _ = pick_genre(
            "build a doom-like first-person shooter", "gamedev"
        )
        assert name == "platformer", f"env override should win, got {name}"
    finally:
        os.environ.pop("TSUNAMI_GENRE", None)


def test_env_override_missing_file_falls_through():
    os.environ["TSUNAMI_GENRE"] = "nonexistent_genre"
    try:
        name, _ = pick_genre(
            "build a simple 2d platformer", "gamedev"
        )
        # Falls through to keyword — platformer wins.
        assert name == "platformer"
    finally:
        os.environ.pop("TSUNAMI_GENRE", None)


# ───────────── directive formatting ─────────────

def test_format_includes_mechanic_activation():
    name, body = pick_genre("build a zelda-like", "gamedev")
    d = format_genre_directive(name, body)
    assert "=== GENRE: action_adventure ===" in d
    assert "=== END GENRE ===" in d
    assert "MECHANIC ACTIVATION" in d
    assert "@engine/design/catalog" in d
    assert "RoomGraph" in d


def test_format_empty_inputs_safe():
    assert format_genre_directive("", "") == ""
    assert format_genre_directive("xyz", "") == ""


# ───────────── integration with agent.py — smoke ─────────────

def test_genre_directive_budget_reasonable():
    """Injecting genre directive shouldn't balloon user_message 10x.
    Current budget target: ~1500-2500 tokens per directive."""
    name, body = pick_genre("build a zelda-like", "gamedev")
    d = format_genre_directive(name, body)
    # ~4 chars/token — aim for < 3000 tokens per genre injection.
    tokens = len(d) // 4
    assert tokens < 3000, (
        f"genre directive is {tokens} tokens — too big. "
        f"Rewrite or add compact_body()."
    )
    assert tokens > 200, f"too small ({tokens}), probably bug"


def test_agent_py_has_genre_hook():
    """Confirm the agent.py edit landed — hunt for the exact marker."""
    agent_py = (REPO / "tsunami" / "agent.py").read_text()
    assert "F-A3: gamedev genre injection" in agent_py
    assert "from .genre_scaffolds import pick_genre" in agent_py
    assert "if genre_directive:" in agent_py
    assert "context_parts.append(genre_directive)" in agent_py


def test_planfile_gamedev_keywords_expanded():
    """F-C1 telemetry showed 'zelda-like top-down' missing — verify it's in now."""
    pf = (REPO / "tsunami" / "planfile.py").read_text()
    assert '"zelda-like"' in pf
    assert '"top-down action-adventure"' in pf or '"action-adventure"' in pf
    assert '"metroidvania"' in pf
    assert '"fps"' in pf


def main():
    tests = [
        test_at_least_three_genres,
        test_frontmatter_required_fields,
        test_default_mechanics_are_real,
        test_recommended_mechanics_are_real,
        test_would_falsify_is_substantive,
        test_non_gamedev_scaffold_returns_empty,
        test_zelda_like_routes_action_adventure,
        test_platformer_prompt_routes_platformer,
        test_fps_prompt_routes_fps,
        test_metroidvania_routes_metroidvania,
        test_env_override_wins,
        test_env_override_missing_file_falls_through,
        test_format_includes_mechanic_activation,
        test_format_empty_inputs_safe,
        test_genre_directive_budget_reasonable,
        test_agent_py_has_genre_hook,
        test_planfile_gamedev_keywords_expanded,
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
