"""Per-genre content pool injector (F-I3b).

Implementation of `scaffolds/.claude/CONTENT_INJECTOR_SPEC.md` (JOB-P).

Generalizes the F-I3 per-game content directive (which only fires when
the prompt names a specific title like "zelda-like") to **every genre**
by pulling canonical enemy/boss/item/level/npc names from
`scaffolds/.claude/GENRE_CONTENT_POOL.md` (JOB-M output) when the
detected genre is supported and F-I3 didn't match.

Sigma-audit Round T observed an ~18% content-adoption lift from F-I3
injection on Zelda prompts. This module generalizes that baseline.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

# Path resolution — the pool lives under scaffolds/.claude/ at the repo root.
_REPO_ROOT = Path(__file__).parent.parent.parent
_POOL_PATH = _REPO_ROOT / "scaffolds" / ".claude" / "GENRE_CONTENT_POOL.md"


# -----------------------------------------------------------------------------
# Parser
# -----------------------------------------------------------------------------

# Role-header → canonical role key mapping. First needle that hits wins.
_ROLE_MAP: list[tuple[tuple[str, ...], str]] = [
    (("enem",), "enemies"),
    (("boss",), "bosses"),
    (("item", "weapon", "pickup"), "items"),
    (("level", "region", "stage", "map", "world"), "levels"),
    (("npc", "character", "playab", "fighter", "hero", "party"), "npcs"),
]

# Attribution regex: "(YYYY, Title)" anywhere in a chunk.
_ATTR_ANY_RE = re.compile(r"\((\d{4})\s*,\s*([^)]+?)\)")

# Per-entry regex: "Name (YYYY, Title)" with the name captured.
_ATTR_WITH_NAME_RE = re.compile(
    r"^\s*(?:\*\*)?([A-Z][\w \t'&/:\-]+?)(?:\*\*)?\s*\(\s*(\d{4})\s*,\s*([^)]+?)\s*\)"
)


def _clean_name(raw: str) -> str:
    """Strip wrappers, attribution residue, and trailing punctuation from
    a name chunk. Returns '' when nothing meaningful survives."""
    s = raw.strip().strip("*").strip()
    # Drop any trailing (attribution) residue — '(1986, Zelda)' etc.
    s = re.sub(r"\s*\([^)]*\)\s*$", "", s)
    # Drop trailing commas / semicolons / bullets left by lazy splits.
    s = s.rstrip(",;-").strip()
    return s


def _parse_pool(md_text: str) -> dict[str, dict[str, list[dict]]]:
    """Parse GENRE_CONTENT_POOL.md into nested dict.

    Pool shape: ``{ genre: { role: [ {name, year, title}, ... ] } }``.

    Handles two bullet patterns present in the corpus:

      1. Per-name attribution:
         ``- Octorok (1986, Zelda), Moblin (1986, Zelda), ...``

      2. Chunk-shared attribution (separated by ``;``):
         ``- Wooden Sword, White Sword, Magical Sword (1986, Zelda);
            Boomerang, Magic Boomerang; Bomb; ...``

      For (2), each ``;``-chunk has at most one ``(year, title)``; all
      comma-separated names in the chunk inherit that attribution.
      Chunks with no attribution at all are dropped.
    """
    pool: dict[str, dict[str, list[dict]]] = {}
    cur_genre: Optional[str] = None
    cur_role: Optional[str] = None

    # Track last attribution within a bullet's semicolon-chunks: a chunk
    # without its own parenthetical inherits the most-recent one (common
    # platformer/fps pattern).
    for raw_line in md_text.splitlines():
        line = raw_line.rstrip()

        # L2 header: "## action_adventure (27 essences)"
        m2 = re.match(r"^##\s+(\w[\w_]+)\s*\((\d+)\s+essence", line)
        if m2:
            cur_genre = m2.group(1).lower()
            pool.setdefault(cur_genre, {})
            cur_role = None
            continue

        # L3 header: "### Enemies (top 30, year-sorted)"
        m3 = re.match(r"^###\s+(.+?)\s*(?:\([^)]*\))?\s*$", line)
        if m3 and cur_genre:
            role_phrase = m3.group(1).lower()
            cur_role = None
            for needles, role_key in _ROLE_MAP:
                if any(n in role_phrase for n in needles):
                    cur_role = role_key
                    break
            if cur_role:
                pool[cur_genre].setdefault(cur_role, [])
            continue

        # Bullet line
        if line.startswith("- ") and cur_genre and cur_role:
            body = line[2:]
            last_attr_year: Optional[int] = None
            last_attr_title: Optional[str] = None

            for chunk in body.split(";"):
                chunk = chunk.strip()
                if not chunk:
                    continue

                # Find all attributions in this chunk.
                all_attrs = list(_ATTR_ANY_RE.finditer(chunk))

                if len(all_attrs) >= 2:
                    # Per-name attribution pattern: multiple "Name (YYYY, Title)"
                    # in the chunk. Walk them in order — each attribution's
                    # name is the text from the previous boundary up to this
                    # attribution's parenthetical.
                    prev_end = 0
                    for m in all_attrs:
                        name_span = chunk[prev_end:m.start()]
                        # Strip leading "," / "and" left by the previous entry.
                        name_text = name_span.lstrip(",").lstrip("&").lstrip().strip()
                        # The entry name is the text up to (but not including)
                        # the trailing "(YYYY, Title)" match.
                        name = _clean_name(name_text)
                        if name and len(name) >= 2:
                            pool[cur_genre][cur_role].append({
                                "name": name,
                                "year": int(m.group(1)),
                                "title": m.group(2).strip(),
                            })
                        prev_end = m.end()
                    last_attr_year = int(all_attrs[-1].group(1))
                    last_attr_title = all_attrs[-1].group(2).strip()
                    continue

                if len(all_attrs) == 1:
                    # Single chunk-level attribution applies to all names
                    # in the chunk. Strip the "(YYYY, Title)" from the
                    # chunk, then split remaining text on commas.
                    attr = all_attrs[0]
                    chunk_year = int(attr.group(1))
                    chunk_title = attr.group(2).strip()
                    names_text = (chunk[:attr.start()] + chunk[attr.end():]).strip()
                    for piece in names_text.split(","):
                        name = _clean_name(piece)
                        if not name or len(name) < 2:
                            continue
                        pool[cur_genre][cur_role].append({
                            "name": name, "year": chunk_year, "title": chunk_title,
                        })
                    last_attr_year = chunk_year
                    last_attr_title = chunk_title
                    continue

                # No attribution in this chunk — inherit from previous
                # chunk in the bullet (common shorthand pattern).
                if last_attr_year is not None and last_attr_title is not None:
                    for piece in chunk.split(","):
                        name = _clean_name(piece)
                        if not name or len(name) < 2:
                            continue
                        pool[cur_genre][cur_role].append({
                            "name": name,
                            "year": last_attr_year,
                            "title": last_attr_title,
                        })

    return _dedupe_pool(pool)


def _dedupe_pool(
    pool: dict[str, dict[str, list[dict]]],
) -> dict[str, dict[str, list[dict]]]:
    """Within each (genre, role), drop duplicate-name entries across
    different titles by keeping the first-year occurrence. Case-
    insensitive on name."""
    for genre, roles in pool.items():
        for role, entries in list(roles.items()):
            seen: dict[str, dict] = {}
            for e in entries:
                key = e["name"].lower()
                prev = seen.get(key)
                if prev is None or e["year"] < prev["year"]:
                    seen[key] = e
            pool[genre][role] = list(seen.values())
    return pool


# -----------------------------------------------------------------------------
# Mtime-aware loader
# -----------------------------------------------------------------------------

_POOL_CACHE: Optional[tuple[float, dict[str, dict[str, list[dict]]]]] = None


def _load_pool() -> dict[str, dict[str, list[dict]]]:
    """Load + cache the pool. Reparses when the source file's mtime
    changes (dev-ergonomic)."""
    global _POOL_CACHE
    if not _POOL_PATH.exists():
        return {}
    mtime = _POOL_PATH.stat().st_mtime
    if _POOL_CACHE and _POOL_CACHE[0] == mtime:
        return _POOL_CACHE[1]
    parsed = _parse_pool(_POOL_PATH.read_text())
    _POOL_CACHE = (mtime, parsed)
    return parsed


def _load_genre_content_pool() -> dict[str, dict[str, list[dict]]]:
    """Public re-export for tests + downstream callers."""
    return _load_pool()


# -----------------------------------------------------------------------------
# Title narrowing
# -----------------------------------------------------------------------------

_STOPWORDS = {
    "the", "a", "an", "like", "style", "inspired", "of", "to", "and",
    "game", "clone", "for", "with", "make", "me", "build", "give",
    "create", "design", "want", "need", "please", "2d", "3d",
    "demo", "mvp", "prototype", "minute", "minutes", "sec", "seconds",
    "my", "our", "new", "some", "any", "this", "that", "in", "on",
    "from", "using", "based", "genre", "type",
}


def _narrow_pool_by_title(
    pool_for_genre: dict[str, list[dict]],
    prompt: str,
) -> dict[str, list[dict]]:
    """Narrow the pool to names whose `title` shares a non-stopword
    token with the prompt. Reverts to full pool if fewer than 3 names
    survive across all roles (thin-filter safety)."""
    title_tokens = {
        t.lower() for t in re.findall(r"[a-zA-Z]{3,}", prompt)
        if t.lower() not in _STOPWORDS
    }
    if not title_tokens:
        return pool_for_genre
    narrowed: dict[str, list[dict]] = {}
    total_kept = 0
    for role, items in pool_for_genre.items():
        kept = []
        for e in items:
            title_words = {
                w.lower().strip("'\".,:;") for w in e["title"].split()
            }
            if title_words & title_tokens:
                kept.append(e)
        narrowed[role] = kept
        total_kept += len(kept)
    if total_kept < 3:
        return pool_for_genre
    return narrowed


# -----------------------------------------------------------------------------
# Formatter
# -----------------------------------------------------------------------------

_DEFAULT_COUNTS: dict[str, int] = {
    "enemies": 8,
    "bosses": 3,
    "items": 6,
    "levels": 5,
    "npcs": 4,
}

_ROLE_HEADERS: dict[str, str] = {
    "enemies": "Enemies (pick 3-5 for level-1-spawns):",
    "bosses":  "Bosses (pick 1 per dungeon):",
    "items":   "Items (inventory starter):",
    "levels":  "Levels (overworld + dungeon naming):",
    "npcs":    "NPCs:",
}


def _select_topn(entries: list[dict], n: int) -> list[dict]:
    """Year-sort ascending (older = more canonical); tiebreak by name.
    Take first N."""
    sorted_entries = sorted(entries, key=lambda e: (e["year"], e["name"].lower()))
    return sorted_entries[:n]


def format_genre_content_directive(
    genre: str,
    prompt: str,
    counts: Optional[dict[str, int]] = None,
) -> str:
    """Format a directive block for the given genre + prompt.

    Returns empty string when:
      - The genre isn't in the pool (e.g. 'open_world').
      - No roles have ≥1 entry after narrowing.
    """
    pool = _load_pool()
    if genre not in pool:
        return ""

    active_counts = dict(_DEFAULT_COUNTS)
    if counts:
        active_counts.update(counts)

    genre_pool = pool[genre]
    narrowed = _narrow_pool_by_title(genre_pool, prompt)

    # Build the per-role blocks. Skip roles with fewer than 3 entries
    # after narrowing (thin-pool fallback).
    sections: list[str] = []
    total_names = 0
    for role in ("enemies", "bosses", "items", "levels", "npcs"):
        entries = narrowed.get(role, [])
        if len(entries) < 3:
            continue
        n = active_counts.get(role, _DEFAULT_COUNTS.get(role, 5))
        picked = _select_topn(entries, n)
        if not picked:
            continue
        header = _ROLE_HEADERS[role]
        lines = [f"- {e['name']} ({e['year']}, {e['title']})" for e in picked]
        sections.append(f"{header}\n" + "\n".join(lines))
        total_names += len(picked)

    if total_names == 0:
        return ""

    genre_title = genre.replace("_", " ").title()
    preamble = (
        f"=== GENRE CONTENT POOL: {genre_title} ===\n"
        "The prompt didn't name a specific game. For this "
        f"{genre_title}, use canonical content archetypes BY NAME "
        "from the corpus below. Names carry (year, title) provenance "
        "— prefer older/more-canonical names when conflicts arise.\n"
    )
    closer = (
        "\nDo not invent generic placeholders like 'Enemy 1' / 'Boss A' "
        "when the pool has a canonical name that fits. Mix names from "
        "different titles only when the prompt explicitly crosses eras "
        "(e.g. 'zelda-meets-metroid'); otherwise stick to one lineage "
        "for coherence.\n"
        "=== END GENRE CONTENT POOL ==="
    )
    return preamble + "\n" + "\n\n".join(sections) + closer


def should_emit_genre_pool(prompt: str, fi3_hit: bool) -> bool:
    """Gate whether F-I3b fires at all.

    - If F-I3 already hit (pick_game_replica matched), skip F-I3b to
      avoid double-injection.
    - If the prompt is empty / whitespace only, skip.
    """
    if fi3_hit:
        return False
    if not prompt.strip():
        return False
    return True
