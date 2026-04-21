"""Genre scaffolds — gamedev-specific mechanic-level doctrine injection.

Parallel of style_scaffolds but for gamedev. When the resolved scaffold
is `gamedev`, `pick_genre(task)` routes the prompt to one of the
genre .md files (action_adventure, platformer, fps, metroidvania, ...)
and `format_genre_directive()` wraps the body for user_message
injection. Composes with content_directive (F-I3) — genre names the
general mechanic set, content names the specific archetypes.

NOT cross-cite-promotable (mechanics cross-cite, genres are template
clusters). Sigma v8 Complementary Operators: genre=template-general,
content=game-specific, both compose.

OPT-IN by virtue of only firing when scaffold=='gamedev'.
"""
from __future__ import annotations

import os
import random
import re
from pathlib import Path

_HERE = Path(__file__).parent

# Keyword → genre stem. First match wins. Specificity-ordered.
_KEYWORD_MAP: list[tuple[tuple[str, ...], str]] = [
    (("metroid prime", "prime-like", "metroid prime-style"),
     "metroidvania"),
    (("metroidvania", "metroid-like", "metroid like",
      "backtracking exploration", "ability-gated exploration",
      "super metroid"),
     "metroidvania"),
    (("metroid",),
     "metroidvania"),
    (("platformer", "side-scroller", "side scroller",
      "run and jump", "jump and run", "mario-like",
      "super mario", "sonic-like", "platform game",
      "2d platformer", "3d platformer"),
     "platformer"),
    (("fps", "first-person shooter", "first person shooter",
      "doom-like", "doom like", "quake-like", "quake like",
      "boomer shooter", "arena shooter",
      "first-person", "first person"),
     "fps"),
    (("zelda-like", "zelda like", "legend of zelda",
      "top-down action", "top-down adventure",
      "top down action", "top down adventure",
      "action-adventure", "action adventure",
      "ocarina of time", "oot-like"),
     "action_adventure"),
    (("jrpg", "turn-based rpg", "turn based rpg",
      "party rpg", "final fantasy-like", "chrono-like"),
     "jrpg"),
    (("rts", "real-time strategy", "real time strategy",
      "starcraft-like", "age of empires", "command and conquer"),
     "rts"),
    (("immersive sim", "deus ex-like", "system shock",
      "prey-like", "0451"),
     "immersive_sim"),
    (("stealth", "sneak game", "thief-like",
      "splinter cell", "mgs-like"),
     "stealth"),
    (("fighter", "street fighter-like", "tekken-like",
      "mortal kombat", "2d fighter", "3d fighter",
      "fighting game"),
     "fighter"),
    (("beat em up", "beat-em-up", "beat_em_up", "brawler",
      "final fight", "streets of rage", "streets-of-rage",
      "double dragon", "double-dragon", "turtles in time",
      "side-scrolling brawler", "side scrolling brawler",
      "arcade brawler"),
     "beat_em_up"),
    (("kart racer", "mario kart", "arcade racer",
      "racing game", "race game", "racing called", "race called",
      "gran turismo", "out run", "outrun"),
     "kart_racer"),
    (("open world", "gta-like", "sandbox game",
      "3d open world", "open-world"),
     "open_world"),
    # Cross-genre canary explicit names. These map to their own
    # scaffold dirs under scaffolds/gamedev/cross/ via the
    # _GENRE_MAP aliases in project_init_gamedev.
    (("magic_hoops", "magic-hoops"), "magic_hoops"),
    (("ninja_garden", "ninja-garden"), "ninja_garden"),
    (("rhythm_fighter", "rhythm-fighter"), "rhythm_fighter"),
    (("action_rpg_atb", "action-rpg-atb"), "action_rpg_atb"),
    (("metroid_runs", "metroid-runs"), "metroid_runs"),
]

_ANCHOR_RE = re.compile(r"^anchors:\s*(.+?)\s*$", re.MULTILINE)
_CORPUS_FIELD_RE = re.compile(r"^corpus_share:\s*(\d+)\s*$", re.MULTILINE)


def _available_genres() -> list[str]:
    return sorted(p.stem for p in _HERE.glob("*.md"))


def _load(name: str) -> str | None:
    path = _HERE / f"{name}.md"
    if not path.is_file():
        return None
    return path.read_text()


def _genre_weight(body: str) -> float:
    """Weight by corpus_share frontmatter, anchor count, or fallback 1.0.

    Mirrors style_scaffolds._style_weight but without the 'none in corpus'
    escape-hatch (no genre has zero corpus yet — every genre has ≥1
    anchor essence). Zero-weight genres can be added later as escape-
    hatches for genres we deliberately don't auto-pick.
    """
    m_field = _CORPUS_FIELD_RE.search(body)
    if m_field:
        return float(m_field.group(1))
    m_anchors = _ANCHOR_RE.search(body)
    if m_anchors:
        count = sum(1 for a in m_anchors.group(1).split(",") if a.strip())
        return float(count) if count else 1.0
    return 1.0


def pick_genre(task: str, scaffold: str = "", seed: int | None = None) -> tuple[str, str]:
    """Return (genre_name, genre_body) for a gamedev task.

    Only fires when scaffold == 'gamedev'. For other scaffolds returns
    ('', '') — non-gamedev scaffolds use style_scaffolds instead.

    Resolution order:
      1. env TSUNAMI_GENRE=<name>
      2. keyword match in task text
      3. corpus-weighted random across all genre files
    """
    if scaffold != "gamedev":
        return "", ""

    forced = os.environ.get("TSUNAMI_GENRE")
    if forced:
        body = _load(forced)
        if body:
            # Telemetry + history (best-effort, non-blocking).
            _log_pick(task, forced, source="env")
            return forced, body

    from ..routing import match_first
    name = match_first(task, _KEYWORD_MAP, default="")
    _log_pick(task, name, source="default" if not name else "keyword")
    if name:
        body = _load(name)
        if body:
            _log_doctrine(name, scaffold)
            return name, body

    # Corpus-weighted random across all genre files.
    applicable: list[tuple[str, float]] = []
    for p in _HERE.glob("*.md"):
        body = p.read_text()
        w = _genre_weight(body)
        if w > 0:
            applicable.append((p.stem, w))
    if not applicable:
        return "", ""
    rng = random.Random(seed) if seed is not None else random
    names = [a[0] for a in applicable]
    weights = [a[1] for a in applicable]
    chosen = rng.choices(names, weights=weights, k=1)[0]
    _log_pick(task, chosen, source="random")
    _log_doctrine(chosen, scaffold)
    return chosen, _load(chosen) or ""


def _log_pick(task: str, winner: str, source: str) -> None:
    """Wire into routing_telemetry. Never raises."""
    try:
        from ..routing_telemetry import log_pick
        log_pick("genre", task, winner, default="", match_source=source)
    except Exception:
        pass


def _log_doctrine(name: str, scaffold: str) -> None:
    """Wire into doctrine_history for cold-start tracking."""
    try:
        from ..doctrine_history import log_pick as _dh
        _dh("genre", name, scaffold=scaffold)
    except Exception:
        pass


def format_genre_directive(name: str, body: str) -> str:
    """Render the genre body as a task-prepended directive block.

    Includes a MECHANIC ACTIVATION note that tells the wave to compose
    from the engine catalog instead of re-implementing primitives.
    """
    if not name or not body:
        return ""
    title = name.replace("_", " ").title()
    activation = (
        "\nMECHANIC ACTIVATION: this prompt matches the "
        f"{title.upper()} genre. Import MechanicType entries from "
        "'@engine/design/catalog' — the catalog already ships tuned "
        "versions of PhysicsModifier, CameraFollow, RoomGraph, "
        "BulletPattern, etc. Do NOT re-implement these primitives. "
        "Reference the default_mechanics and recommended_mechanics "
        "lists in the frontmatter below; compose them via the "
        "emit_design tool (see plan_scaffolds/gamedev.md).\n"
    )
    return (
        f"\n\n=== GENRE: {name} ===\n"
        f"Embody this genre doctrine — it names the mechanic set, "
        f"common shape, and non-goals that distinguish this genre from "
        f"neighbors.\n"
        f"{activation}"
        f"\n{body}\n"
        f"=== END GENRE ===\n"
    )


__all__ = [
    "pick_genre", "format_genre_directive",
    "_KEYWORD_MAP",
]
