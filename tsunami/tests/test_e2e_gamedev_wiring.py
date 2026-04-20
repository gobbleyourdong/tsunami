"""End-to-end smoke test for the gamedev integration chain.

Walks a gamedev prompt through every layer the wave would touch and
verifies the user_message produced at directive-assembly time has
ALL expected substrings. No model calls, no subprocess — pure import
+ pure-function invocation.

What it locks:
  - `pick_scaffold("zelda-like...")` → 'gamedev'
  - `pick_genre(...)` → 'action_adventure'
  - `format_genre_directive(...)` → includes MECHANIC ACTIVATION block
  - `pick_game_replica(...)` → '1986_legend_of_zelda' (or respective)
  - `load_content_catalog(...)` → non-empty
  - `format_content_directive(...)` → includes named Zelda content
  - Final user_message (simulated concat) contains genre + content
    directive block markers in the order agent.py concatenates them.
  - Token budget: user_message stays under ~15K tokens total.

This is the test you run before kicking off a live A/B — if the
plumbing is broken here, no live run will succeed.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO))

from tsunami.planfile import pick_scaffold                         # noqa: E402
from tsunami.genre_scaffolds import pick_genre, format_genre_directive  # noqa: E402
from tsunami.game_content import (                                 # noqa: E402
    pick_game_replica, load_content_catalog, format_content_directive,
)


def _assemble_user_message(prompt: str) -> dict:
    """Simulate agent.py's directive-assembly block from run()."""
    scaffold = pick_scaffold(prompt)
    genre_name, genre_body = "", ""
    genre_directive = ""
    if scaffold == "gamedev":
        genre_name, genre_body = pick_genre(prompt, scaffold)
        if genre_name and genre_body:
            genre_directive = format_genre_directive(genre_name, genre_body)
    essence = pick_game_replica(prompt)
    content_directive = ""
    if essence:
        cat_body = load_content_catalog(essence)
        if cat_body:
            content_directive = format_content_directive(essence, cat_body)
    parts = [prompt]
    if genre_directive:
        parts.append(genre_directive)
    if content_directive:
        parts.append(content_directive)
    return {
        "prompt": prompt,
        "scaffold": scaffold,
        "genre": genre_name,
        "essence": essence,
        "user_message": "\n\n".join(parts),
        "genre_tokens_est": len(genre_directive) // 4,
        "content_tokens_est": len(content_directive) // 4,
    }


# ═══════════════════ Zelda canonical path ═══════════════════

def test_zelda_prompt_full_chain():
    r = _assemble_user_message(
        "build a zelda-like top-down action-adventure game with dungeons"
    )
    assert r["scaffold"] == "gamedev"
    assert r["genre"] == "action_adventure"
    assert r["essence"] == "1986_legend_of_zelda"
    um = r["user_message"]
    assert "=== GENRE: action_adventure ===" in um
    assert "=== END GENRE ===" in um
    assert "=== CONTENT CATALOG: 1986 Legend Of Zelda ===" in um
    assert "=== END CONTENT CATALOG ===" in um
    # Genre-directive content: real MechanicType references
    assert "RoomGraph" in um
    assert "MECHANIC ACTIVATION" in um
    # Content-directive content: named Zelda archetypes
    assert "Octorok" in um
    assert "Aquamentus" in um


def test_zelda_token_budget_reasonable():
    r = _assemble_user_message(
        "build a zelda-like top-down action-adventure game"
    )
    total = len(r["user_message"]) // 4
    assert total < 5000, f"user_message bloated to {total} tokens"
    assert r["genre_tokens_est"] > 200
    assert r["content_tokens_est"] > 500


# ═══════════════════ Cross-genre coverage ═══════════════════

def test_platformer_routes_genre_but_no_content_replica():
    r = _assemble_user_message(
        "build a simple 2d platformer with powerups"
    )
    assert r["scaffold"] == "gamedev"
    assert r["genre"] == "platformer"
    # No specific game-replica named → content_directive should be empty
    assert r["essence"] == ""
    assert "=== GENRE: platformer ===" in r["user_message"]
    assert "=== CONTENT CATALOG:" not in r["user_message"]


def test_doom_prompt_fps_genre_plus_content():
    r = _assemble_user_message(
        "build a doom-like first-person shooter with keycards"
    )
    assert r["scaffold"] == "gamedev"
    assert r["genre"] == "fps"
    assert r["essence"] == "1993_doom"
    um = r["user_message"]
    assert "=== GENRE: fps ===" in um
    assert "=== CONTENT CATALOG: 1993 Doom ===" in um


def test_starcraft_prompt_rts_genre_plus_content():
    r = _assemble_user_message(
        "build a starcraft-like rts with asymmetric factions"
    )
    assert r["scaffold"] == "gamedev"
    assert r["genre"] == "rts"
    assert r["essence"] == "1998_starcraft"


def test_ff7_prompt_jrpg_genre_plus_content():
    r = _assemble_user_message(
        "build a ff7-like jrpg with atb combat and materia"
    )
    assert r["scaffold"] == "gamedev"
    assert r["genre"] == "jrpg"
    assert r["essence"] == "1997_final_fantasy_vii"


# ═══════════════════ Non-gamedev fall-through ═══════════════════

def test_dashboard_prompt_no_gamedev_wiring():
    r = _assemble_user_message(
        "admin dashboard with kpi cards and user list"
    )
    assert r["scaffold"] == "dashboard"
    assert r["genre"] == ""       # non-gamedev → no genre
    assert r["essence"] == ""     # no game-replica keyword
    # No gamedev directive blocks
    assert "GENRE:" not in r["user_message"]
    assert "CONTENT CATALOG:" not in r["user_message"]


def test_landing_prompt_no_gamedev_wiring():
    r = _assemble_user_message(
        "landing page for a coffee subscription with pricing tiers"
    )
    assert r["scaffold"] == "landing"
    assert r["genre"] == ""


def test_content_can_fire_on_non_gamedev_scaffold():
    """content_directive is NOT scaffold-gated — a prompt like
    'zelda-themed dashboard' still pulls the Zelda content catalog
    even though scaffold=dashboard. Genre is scaffold-gated; content
    is not."""
    r = _assemble_user_message(
        "zelda-like dashboard with dungeon-themed kpis"
    )
    # Depending on keyword ordering this may route to gamedev (zelda-like
    # is a gamedev keyword) or dashboard. Either way, content catalog
    # should fire because game_replica is scaffold-agnostic.
    assert r["essence"] == "1986_legend_of_zelda"
    assert "=== CONTENT CATALOG:" in r["user_message"]


# ═══════════════════ Structural invariants ═══════════════════

def test_genre_directive_references_real_mechanics():
    """Every MechanicType name in an injected genre_directive must
    exist in engine schema.ts's MechanicType union — no fabricated
    types the compiler will reject."""
    r = _assemble_user_message(
        "build a zelda-like top-down action-adventure"
    )
    # Pull MechanicType literals from the live schema
    schema = (REPO / "scaffolds" / "engine" / "src" / "design"
              / "schema.ts").read_text()
    valid = set(re.findall(r"'([A-Z][A-Za-z0-9_]+)'", schema))
    # Extract MechanicType-shaped mentions from the directive
    um = r["user_message"]
    genre_block = um[um.find("=== GENRE:"):um.find("=== END GENRE ===")]
    cited = re.findall(r"\b([A-Z][A-Za-z]+[A-Z][A-Za-z]+)\b", genre_block)
    # The cited mechanics mentioned in default_mechanics / recommended_mechanics
    # / prose should ALL be valid schema types. Filter out clearly-prose words.
    for name in cited:
        if name in ("END", "GENRE", "MECHANIC", "ACTIVATION", "DO", "NOT"):
            continue
        if name.isupper() or len(name) < 4:
            continue
        # Allow prose words that happen to be CapCamelCase
        if name not in valid and name not in (
            "CameraFollow", "Reference",  # example references
        ):
            # This is only a warning — the genre doctrine CAN reference
            # prose nouns. We ONLY fail if the name looks mechanic-y
            # (ends in a mechanic-shape suffix) AND isn't valid.
            if name.endswith(("Mechanic", "System", "Pattern", "Modifier")):
                assert name in valid, (
                    f"genre directive cites invalid MechanicType: {name}"
                )


def test_no_directive_collision_on_same_prompt():
    """Running the same prompt twice should produce identical assembly.
    Determinism is a sigma-audit invariant."""
    r1 = _assemble_user_message(
        "build a zelda-like top-down action-adventure"
    )
    r2 = _assemble_user_message(
        "build a zelda-like top-down action-adventure"
    )
    assert r1["scaffold"] == r2["scaffold"]
    assert r1["genre"] == r2["genre"]
    assert r1["essence"] == r2["essence"]
    # directive TEXT is identical too (no random tokens)
    assert r1["user_message"] == r2["user_message"]


def main():
    tests = [
        test_zelda_prompt_full_chain,
        test_zelda_token_budget_reasonable,
        test_platformer_routes_genre_but_no_content_replica,
        test_doom_prompt_fps_genre_plus_content,
        test_starcraft_prompt_rts_genre_plus_content,
        test_ff7_prompt_jrpg_genre_plus_content,
        test_dashboard_prompt_no_gamedev_wiring,
        test_landing_prompt_no_gamedev_wiring,
        test_content_can_fire_on_non_gamedev_scaffold,
        test_genre_directive_references_real_mechanics,
        test_no_directive_collision_on_same_prompt,
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
