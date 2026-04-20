"""Per-game content catalog loader (sigma audit F-I2).

When a prompt names a specific game replica ("zelda-like", "Metroid-
style"), load THAT game's `## Content Catalog` block from
scaffolds/.claude/game_essence/<stem>.md and inject it as a wave
directive. Content is per-game provenance — NOT cross-cite-promotable
per `project_content_taxonomy` memory.

Two-step lookup:
  1. pick_game_replica(task) — fuzzy keyword route → essence stem
  2. load_content_catalog(stem) — regex-extract the content block

Then format_content_directive() wraps it for user_message injection.
"""
from __future__ import annotations

import re
from pathlib import Path

_ESSENCE_DIR = (
    Path(__file__).parent.parent.parent
    / "scaffolds" / ".claude" / "game_essence"
)

# Keyword (game-replica phrase) → essence stem. First match wins;
# specificity-ordered (multi-word before single-word).
#
# 2026-04-20: expanded to 30+ games after the operator's other
# instance back-filled Content Catalog sections across 45 essences.
# Coverage now spans: 2D platformer, 3D platformer, action-adventure,
# metroidvania, FPS, immersive sim, survival horror, stealth,
# JRPG, WRPG, RTS, fighter, life-sim, skater, SotN-style vampire-
# action, rhythm, open-world crime. Each route fires only when
# the prompt explicitly names that game or a canonical clone-phrase.
_GAME_SIGNALS: list[tuple[tuple[str, ...], str]] = [
    # ─── Zelda / action-adventure cluster ───
    (("zelda-like", "legend of zelda", "top-down zelda",
      "top-down action-adventure", "top-down action adventure",
      "nes zelda", "nes-zelda"),
     "1986_legend_of_zelda"),
    (("ocarina of time", "oot-like", "3d zelda"),
     "1998_ocarina_of_time"),
    # ─── Metroidvania cluster ───
    (("metroid prime", "prime-like", "metroid prime-like"),
     "2002_metroid_prime"),
    (("super metroid", "super-metroid"),
     "1994_super_metroid"),
    (("metroidvania", "metroid-like", "metroid like",
      "backtracking exploration"),
     "1994_super_metroid"),  # canonical metroidvania
    (("symphony of the night", "sotn-like", "castlevania sotn",
      "igavania"),
     "1997_castlevania_symphony_of_night"),
    # ─── Platformer cluster ───
    (("super mario bros", "smb-like", "classic mario", "nes mario"),
     "1985_super_mario_bros"),
    (("mario 64", "sm64", "3d mario", "3d platformer classic"),
     "1996_super_mario_64"),
    (("sonic the hedgehog", "sonic-like", "classic sonic"),
     "1991_sonic_the_hedgehog"),
    # ─── FPS cluster ───
    (("doom-like", "doom like", "id tech", "boomer shooter"),
     "1993_doom"),
    (("half-life", "half life-like", "half-life-like",
      "scripted fps"),
     "1998_half_life"),
    # ─── Immersive sim / stealth cluster ───
    (("deus ex-like", "deus-ex-like", "0451"),
     "2000_deus_ex"),
    (("thief-like", "thief: the dark project", "thief tdp",
      "light-based stealth"),
     "1998_thief_dark_project"),
    (("metal gear solid", "mgs-like", "mgs1"),
     "1998_metal_gear_solid"),
    # ─── Survival horror ───
    (("resident evil 1", "re1-like", "tank-controls survival"),
     "1996_resident_evil"),
    (("silent hill", "psychological survival-horror"),
     "1999_silent_hill"),
    # ─── JRPG / WRPG cluster ───
    (("final fantasy 6", "ff6-like", "ff6", "final fantasy vi"),
     "1994_final_fantasy_vi"),
    (("final fantasy 7", "ff7-like", "ff7", "final fantasy vii"),
     "1997_final_fantasy_vii"),
    (("pokemon red", "pokemon blue", "pokemon-like",
      "monster-collector rpg"),
     "1996_pokemon_red_blue"),
    (("fallout 1", "fallout-like", "classic fallout",
      "isometric post-apocalypse"),
     "1997_fallout"),
    (("baldur's gate 2", "baldurs gate 2", "bg2", "bg2-like",
      "infinity-engine crpg"),
     "2000_baldurs_gate_ii"),
    (("diablo 1", "diablo-like", "classic diablo"),
     "1996_diablo"),
    # ─── RTS cluster ───
    (("starcraft 1", "starcraft-like", "sc1", "asymmetric rts"),
     "1998_starcraft"),
    (("age of empires 2", "aoe2", "aoe2-like",
      "historical civ rts"),
     "1999_age_of_empires_ii"),
    # ─── Open-world / life-sim ───
    (("the sims", "the-sims", "sims-like", "life-sim"),
     "2000_the_sims"),
    # ─── Open-world-proto / Shenmue ───
    (("shenmue-like", "shenmue 1", "proto-open-world"),
     "1999_shenmue"),
    # ─── Skater ───
    (("jet set radio", "jet-set-radio", "jsr-like",
      "cel-shaded skater"),
     "2000_jet_set_radio"),
    # ─── Majora's Mask (Zelda-extension) ───
    (("majora's mask", "majoras mask", "moon-timer zelda"),
     "2000_majoras_mask"),
    # ─── KOTOR acronym (not derivable from title) ───
    (("kotor", "kotor-like", "star wars rpg"),
     "2003_kotor"),
]


def _auto_discover_routes() -> list[tuple[tuple[str, ...], str]]:
    """Scan every essence with a ## Content Catalog section; for any
    stem not already in _GAME_SIGNALS, derive keyword variants from
    the `title:` frontmatter and append a route.

    This lets the operator back-fill Content Catalog on a new essence
    without also hand-editing _GAME_SIGNALS. Explicit routes above
    still win first-match (canonical clone-phrases like 'zelda-like'
    stay curated); auto-discovered routes only fire when none of the
    hand-routes match.

    Derivation rules:
      - title "Super Mario Bros." → ["super mario bros"]
      - title "Tom Clancy's Splinter Cell" → ["tom clancy's splinter cell",
        "splinter cell"] (post-apostrophe word stripped)
      - title "The Legend of Zelda: The Wind Waker" → ["the legend of
        zelda: the wind waker", "the wind waker", "wind waker"]
    """
    import re as _re
    routes: list[tuple[tuple[str, ...], str]] = []
    existing_stems = {stem for _, stem in _GAME_SIGNALS}
    if not _ESSENCE_DIR.is_dir():
        return routes
    for md in sorted(_ESSENCE_DIR.glob("*.md")):
        stem = md.stem
        if stem in existing_stems:
            continue
        try:
            body = md.read_text()
        except Exception:
            continue
        if "## Content Catalog" not in body:
            continue
        m = _re.search(r"^title:\s*(.+?)\s*$", body, _re.MULTILINE)
        if not m:
            continue
        title = m.group(1).strip().rstrip(".").strip()
        title_lower = title.lower()
        # Base variant + period-stripped (SMB. Melee → SMB Melee).
        variants_raw: list[str] = [title_lower]
        period_stripped = title_lower.replace(".", "")
        if period_stripped != title_lower:
            variants_raw.append(period_stripped)
        # Ampersand variant: "Ratchet & Clank" → "ratchet and clank"
        if "&" in title_lower:
            variants_raw.append(title_lower.replace("&", "and"))
        # Subtitle colon: "X: Y" → add only the POST-colon (subtitle).
        # Pre-colon is usually the franchise name ("The Legend of Zelda")
        # which collides with sibling-titled games (Wind Waker, OoT etc).
        # Keeping only the post-colon avoids auto-generating franchise-
        # level routes that a hand-curated entry should own.
        for v in list(variants_raw):
            if ":" in v:
                post_colon = v.split(":", 1)[1].strip()
                if post_colon:
                    variants_raw.append(post_colon)
        # Post-apostrophe word ("Tom Clancy's Splinter Cell" → "splinter cell")
        for v in list(variants_raw):
            if "'s " in v:
                variants_raw.append(v.split("'s ", 1)[1].strip())
        # Leading-article strip ("the wind waker" → "wind waker")
        for v in list(variants_raw):
            for prefix in ("the ", "a ", "an "):
                if v.startswith(prefix):
                    variants_raw.append(v[len(prefix):])
        # Roman numeral ↔ arabic (III ↔ 3, II ↔ 2, IV ↔ 4)
        roman_map = {" iii": " 3", " ii": " 2", " iv": " 4", " vi": " 6", " vii": " 7"}
        for v in list(variants_raw):
            for r, a in roman_map.items():
                if v.endswith(r):
                    variants_raw.append(v[:-len(r)] + a)
        # Initialism ("grand theft auto iii" → "gta iii", "gta 3")
        words = title_lower.split()
        if len(words) >= 3 and all(w.isalpha() for w in words[:3]):
            initials = "".join(w[0] for w in words[:3])
            if len(initials) == 3:
                variants_raw.append(initials)
                # If followed by a number, combine: "gta" + "iii" → "gta 3"
                if len(words) > 3 and words[3] in ("iii", "iv", "ii", "vi", "vii"):
                    num = {"iii": "3", "iv": "4", "ii": "2",
                           "vi": "6", "vii": "7"}[words[3]]
                    variants_raw.append(f"{initials} {num}")
                    variants_raw.append(f"{initials}{num}")
        # Deduplicate, preserve order, drop truly-empty but KEEP 3-char
        # stems (Ico, FF7 etc.). Drop pure-stopword variants only.
        seen: set[str] = set()
        variants: list[str] = []
        stopwords = {"the", "and", "game", "of", "a", "an"}
        for v in variants_raw:
            v = v.strip()
            if not v or v in seen or v in stopwords:
                continue
            seen.add(v)
            variants.append(v)
        if variants:
            routes.append((tuple(variants), stem))
    return routes


# Append auto-discovered routes ONCE at module import.
# Hand-curated routes above (canonical clone-phrases, "zelda-like") win
# first-match; auto-discovered full-title routes land last.
_GAME_SIGNALS = _GAME_SIGNALS + _auto_discover_routes()


def pick_game_replica(task: str) -> str:
    """Return essence stem when task explicitly names a game template.
    Empty string on no match. First match wins."""
    from ..routing import match_first
    result = match_first(task, _GAME_SIGNALS, default="")
    # F-C1 routing telemetry — best-effort, non-blocking.
    try:
        from ..routing_telemetry import log_pick
        log_pick("game_replica", task, result, default="",
                 match_source="default" if not result else "keyword")
    except Exception:
        pass
    # F-E3 doctrine history — only when an essence actually matched
    # (content directive will fire). Cold-start cohort counts from here.
    if result:
        try:
            from ..doctrine_history import log_pick as _dh_log
            _dh_log("game_replica", result)
        except Exception:
            pass
    return result


_CONTENT_RE = re.compile(
    r"^## Content Catalog\s*\n(.*?)(?=^## |\Z)",
    re.MULTILINE | re.DOTALL,
)


def load_content_catalog(essence_stem: str) -> str:
    """Return the `## Content Catalog` block body (without the heading)
    from the named essence file. Empty string on miss."""
    if not essence_stem:
        return ""
    path = _ESSENCE_DIR / f"{essence_stem}.md"
    if not path.is_file():
        return ""
    body = path.read_text()
    m = _CONTENT_RE.search(body)
    return m.group(1).strip() if m else ""


def extract_content_names(catalog_body: str) -> dict[str, list[str]]:
    """Parse the catalog body's 6 tables and return a per-category
    dict of content names. Used by the probe (F-I4) and by the
    inference-free self-check.

    Tables expected (order doesn't matter): Enemies, Bosses,
    Items / Pickups, Equipment, Levels / Areas, NPCs.

    The `Name` column is always the first `|...|` column after a
    table header row. Multi-part names like `Octorok (Red/Blue)` or
    `Rupee (green)` get split on `(`.
    """
    categories = ("enemies", "bosses", "pickups", "equipment", "levels", "npcs")
    out: dict[str, list[str]] = {c: [] for c in categories}

    # Split by sub-section (### heading). Each sub-section is a
    # category. Match loosely on heading keywords.
    sections = re.split(r"^###\s+", catalog_body, flags=re.MULTILINE)
    # Header keywords that identify the "name" column — in priority
    # order. Zelda's boss table is | Lv | Dungeon | Boss | ... so the
    # name column is #3 (under "Boss"), not #1. Generic fallback: col 0.
    name_headers = ("boss", "enemy", "name", "item", "pickup", "npc",
                    "character", "level", "area", "dungeon")
    skip_col0_headers = {"name", "lv", "slot", "#", "id"}

    for sec in sections:
        if not sec.strip():
            continue
        heading, _, rest = sec.partition("\n")
        heading_lower = heading.lower()
        cat: str | None = None
        if "enem" in heading_lower or "mob" in heading_lower:
            cat = "enemies"
        elif "boss" in heading_lower:
            cat = "bosses"
        elif "pickup" in heading_lower or "item" in heading_lower or "consumable" in heading_lower:
            cat = "pickups"
        elif "equip" in heading_lower:
            cat = "equipment"
        elif "level" in heading_lower or "area" in heading_lower or "dungeon" in heading_lower:
            cat = "levels"
        elif "npc" in heading_lower or "character" in heading_lower:
            cat = "npcs"
        if not cat:
            continue

        # Two-pass over the table block: first find the Name column
        # index from the header row, then extract that column from the
        # data rows.
        lines = [l.strip() for l in rest.splitlines()]
        name_idx: int | None = None
        for line in lines:
            if not line.startswith("|"):
                continue
            cols = [c.strip() for c in line.strip("|").split("|")]
            # Header row? (contains a name-like keyword)
            lowered = [c.lower() for c in cols]
            if name_idx is None:
                for kw in name_headers:
                    for i, col in enumerate(lowered):
                        if col == kw:
                            name_idx = i
                            break
                    if name_idx is not None:
                        break
                # If we saw a header row but found no match, default to 0.
                if name_idx is None and any(c in skip_col0_headers for c in lowered):
                    name_idx = 0
                # Keep scanning; this was the header, advance.
                if name_idx is not None:
                    continue
            # Separator row |---|---|
            if re.match(r"^\|?[\s\-:|]+\|?$", line):
                continue
            # Data row — extract from name_idx (default 0 if header
            # never detected a match).
            idx = name_idx if name_idx is not None else 0
            if idx >= len(cols):
                continue
            raw = cols[idx]
            if not raw or raw.lower() in skip_col0_headers:
                continue
            # Strip parenthetical variant tags and trailing count suffixes.
            raw = raw.split("(")[0].strip()
            raw = re.sub(r"[×x]\d+$", "", raw).strip()
            # Filter obvious noise (pure numbers, single hyphens).
            if not raw or raw == "-" or raw.isdigit():
                continue
            if raw not in out[cat]:
                out[cat].append(raw)
    return out


def format_content_directive(essence_stem: str, body: str) -> str:
    """Wrap the catalog as a task-prepended directive block.

    Ties content to provenance: the wave is told to use these names
    for enemies / bosses / items / equipment / levels / NPCs when
    emitting sprites, state machines, or level data. Don't invent
    generic placeholders when the catalog names a specific thing.
    """
    if not essence_stem or not body:
        return ""
    title = essence_stem.replace("_", " ").title()
    return (
        f"\n\n=== CONTENT CATALOG: {title} ===\n"
        f"This prompt references a specific game. Use the following "
        f"content archetypes BY NAME for enemies, bosses, pickups, "
        f"equipment, levels, and NPCs. When generating sprites or "
        f"state machines, reference these names — DO NOT invent "
        f"generic placeholders like 'Enemy 1' / 'Boss A'. Content is "
        f"per-game provenance; don't generalize across games.\n\n"
        f"{body}\n"
        f"=== END CONTENT CATALOG ===\n"
    )


__all__ = [
    "pick_game_replica",
    "load_content_catalog",
    "extract_content_names",
    "format_content_directive",
]
