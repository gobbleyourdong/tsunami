"""Inference-free self-check for F-I3 content injection plumbing
(Fix #4: game_content loader / Fix #5: F-I3 directive injection).

Answers one question: given a "zelda-like" prompt, does the loader
deliver a directive that a probe can distinguish from baseline?

NO model calls. NO network. Pure unit + fixture-based.

Sigma v9 Formalization Exposes Drift: if the probe can't tell apart
a fixture that uses catalog names from one that uses generics, the
scanner is weak — the live A/B would be unreliable. Probe first,
model second.
"""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

# Ensure tsunami is importable relative to the repo root
REPO = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO))

from tsunami.game_content import (  # noqa: E402
    pick_game_replica,
    load_content_catalog,
    extract_content_names,
    format_content_directive,
)


# ─────────── Plumbing checks ────────────────────────────────────────

def test_pick_routes_zelda_like():
    assert pick_game_replica("build a zelda-like top-down action game") == "1986_legend_of_zelda"
    assert pick_game_replica("top-down action-adventure with 3 dungeons") == "1986_legend_of_zelda"
    assert pick_game_replica("build a platformer") == ""
    assert pick_game_replica("") == ""


def test_pick_respects_specificity():
    # "metroid prime" must win over "metroidvania" ordering.
    assert pick_game_replica("metroid prime-style scan visor game") == "2002_metroid_prime"
    # Plain "metroidvania" routes to Super Metroid.
    assert pick_game_replica("build a metroidvania") == "1994_super_metroid"


def test_load_catalog_has_content():
    body = load_content_catalog("1986_legend_of_zelda")
    assert body, "content catalog must be non-empty for the POC essence"
    # Sanity: the key Zelda names must appear verbatim.
    for name in ("Octorok", "Moblin", "Aquamentus", "Dodongo", "Gohma", "Ganon"):
        assert name in body, f"{name!r} missing from loaded catalog"


def test_load_missing_returns_empty():
    assert load_content_catalog("nonexistent_game") == ""
    assert load_content_catalog("") == ""


def test_directive_wraps_content():
    body = load_content_catalog("1986_legend_of_zelda")
    directive = format_content_directive("1986_legend_of_zelda", body)
    assert "=== CONTENT CATALOG:" in directive
    assert "=== END CONTENT CATALOG ===" in directive
    assert "DO NOT invent generic placeholders" in directive
    # Content preserved through wrapping.
    assert "Octorok" in directive
    # Provenance title formatted.
    assert "1986 Legend Of Zelda" in directive


# ─────────── Name extraction ────────────────────────────────────────

def test_extract_names_zelda_floor():
    body = load_content_catalog("1986_legend_of_zelda")
    names = extract_content_names(body)
    # Sanity floors per the Zelda essence — conservative.
    assert len(names["enemies"]) >= 15, f"enemies: got {names['enemies']}"
    assert len(names["bosses"]) >= 7, f"bosses: got {names['bosses']}"
    assert len(names["pickups"]) >= 6, f"pickups: got {names['pickups']}"
    # Named examples present.
    assert "Octorok" in names["enemies"]
    assert "Darknut" in names["enemies"]
    assert "Aquamentus" in names["bosses"]
    assert "Gohma" in names["bosses"]


# ─────────── Fixture A/B — the core probe check ─────────────────────

def _probe_app_tsx(src: str, catalog_names: dict[str, list[str]]) -> dict:
    """Mini-probe: count named-content vs generic references in a src
    blob. Mirrors what F-I4 will do against real deliveries.

    Returns {named, generic, named_list, generic_list, adoption}.
    """
    # All catalog names, case-sensitive (names are proper nouns).
    all_names: set[str] = set()
    for lst in catalog_names.values():
        for n in lst:
            if len(n) >= 3:  # skip noise like "-" or single-char rows
                all_names.add(n)

    named_hits: dict[str, int] = {}
    for name in all_names:
        # Word-boundary match so "Ganon" doesn't eat "Ganondorf" variants
        # accidentally in unrelated strings.
        hits = len(re.findall(rf"\b{re.escape(name)}\b", src))
        if hits:
            named_hits[name] = hits

    # Generic-placeholder patterns (grep recipe from the audit scope).
    generic_patterns = [
        r"\bEnemy\s*[0-9A-Z]+\b",
        r"\benemy[0-9]+\b",
        r"\bBoss\s*[0-9A-Z]\b",
        r"\bMonster[0-9]+\b",
        r"\bItem[0-9]+\b",
        r"\bLevel\s*\d+\b",
        r"'monster'",
        r'"placeholder"',
    ]
    generic_hits: list[str] = []
    for pat in generic_patterns:
        generic_hits.extend(re.findall(pat, src))

    named_total = sum(named_hits.values())
    return {
        "named": named_total,
        "named_distinct": len(named_hits),
        "named_list": sorted(named_hits.items(), key=lambda kv: -kv[1]),
        "generic": len(generic_hits),
        "generic_list": generic_hits[:10],
        "adoption_rate": len(named_hits) / max(1, len(all_names)),
    }


# Fixtures — synthesized App.tsx deliveries.
# "Good" fixture: wave honored the directive → names appear inline.
GOOD_APP_TSX = """\
import './index.css';

type Enemy = { name: string; hp: number; drop: string };

const OVERWORLD_ENEMIES: Enemy[] = [
  { name: 'Octorok', hp: 1, drop: 'Rupee' },
  { name: 'Moblin', hp: 2, drop: 'Rupee' },
  { name: 'Leever', hp: 2, drop: 'Rupee' },
  { name: 'Tektite', hp: 1, drop: 'Rupee' },
  { name: 'Zora', hp: 2, drop: 'Heart' },
  { name: 'Peahat', hp: 2, drop: 'Rupee' },
];

const DUNGEON_ENEMIES: Enemy[] = [
  { name: 'Keese', hp: 1, drop: 'Heart' },
  { name: 'Stalfos', hp: 1, drop: 'Rupee' },
  { name: 'Darknut', hp: 4, drop: 'Rupee' },
  { name: 'Wizzrobe', hp: 3, drop: '-' },
];

const BOSSES = ['Aquamentus', 'Dodongo', 'Gohma', 'Manhandla'];

const FINAL_BOSS = 'Ganon';

export default function App() {
  return <div>Zelda-replica: {OVERWORLD_ENEMIES.length} overworld + {DUNGEON_ENEMIES.length} dungeon enemies, {BOSSES.length} bosses, final: {FINAL_BOSS}</div>;
}
"""

# "Bad" fixture: wave ignored the directive → generic placeholders.
BAD_APP_TSX = """\
import './index.css';

type Enemy = { name: string; hp: number };

const ENEMIES: Enemy[] = [
  { name: 'Enemy 1', hp: 1 },
  { name: 'Enemy 2', hp: 2 },
  { name: 'Enemy 3', hp: 2 },
  { name: 'Enemy 4', hp: 3 },
];

const BOSSES = ['Boss A', 'Boss B', 'Boss C'];

const FINAL_BOSS = 'Boss Z';

export default function App() {
  const monster = 'placeholder';
  return <div>Generic action game with {ENEMIES.length} enemies</div>;
}
"""


def test_probe_surfaces_content_from_gamedev_deliverable():
    """Round F 2026-04-20 caught: probe reported 'skipped: no src dir'
    for gamedev deliveries because the wave wrote public/game_definition.json,
    not src/App.tsx. Probe now also scans game_definition.json for
    named content and mechanic types."""
    import json
    import tempfile
    from scripts.overnight.probe import run as _probe_run
    body = load_content_catalog("1986_legend_of_zelda")
    names = extract_content_names(body)
    with tempfile.TemporaryDirectory() as td:
        proj = Path(td) / "zelda-probe-test"
        (proj / "public").mkdir(parents=True)
        game_def = {
            "project_name": "zelda-probe-test",
            "entities": [
                {"id": "player", "name": "Link"},
                {"id": "octorok1", "name": "Octorok"},
                {"id": "moblin1", "name": "Moblin"},
                {"id": "darknut1", "name": "Darknut"},
                {"id": "aquamentus", "name": "Aquamentus"},
            ],
            "mechanics": [{"id": "rg", "type": "RoomGraph"}],
            "scenes": [{"id": "overworld"}],
        }
        (proj / "public" / "game_definition.json").write_text(json.dumps(game_def))
        # Probe the project ROOT — no src/ dir
        report = _probe_run(proj, "1986_legend_of_zelda")
        assert report["gamedev_deliverable_bytes"] > 0, (
            "probe should read game_definition.json even without src/"
        )
        content = report.get("content", {})
        # The 4 named enemies should all register
        adopted = content.get("adopted", {})
        enemies_adopted = adopted.get("enemies", {})
        for name in ("Octorok", "Moblin", "Darknut"):
            assert name in enemies_adopted, (
                f"{name} missing from probe's enemy-adopted set: {enemies_adopted}"
            )
        # Aquamentus is a boss
        bosses_adopted = adopted.get("bosses", {})
        assert "Aquamentus" in bosses_adopted, (
            f"Aquamentus missing from bosses: {bosses_adopted}"
        )


def test_ab_good_vs_bad_fixtures():
    body = load_content_catalog("1986_legend_of_zelda")
    names = extract_content_names(body)

    good = _probe_app_tsx(GOOD_APP_TSX, names)
    bad = _probe_app_tsx(BAD_APP_TSX, names)

    # Pre-committed kill criteria from the A/B scope:
    #   good: named >= 5, generic <= 2
    #   bad:  named == 0, generic >= 3
    assert good["named_distinct"] >= 5, f"good fixture should have ≥5 named: {good}"
    assert good["generic"] <= 2, f"good fixture should have ≤2 generics: {good}"
    assert bad["named_distinct"] == 0, f"bad fixture should have 0 named: {bad}"
    assert bad["generic"] >= 3, f"bad fixture should have ≥3 generics: {bad}"

    # The A/B signal: good should dominate bad on the named axis by
    # a wide margin.
    assert good["named_distinct"] - bad["named_distinct"] >= 5

    # Print the numbers so the human-readable runner reports them.
    print(f"\n--- probe fixture A/B ---")
    print(f"GOOD fixture: named_distinct={good['named_distinct']} "
          f"named_total={good['named']} generic={good['generic']} "
          f"adoption_rate={good['adoption_rate']:.2%}")
    print(f"  top hits: {good['named_list'][:6]}")
    print(f"BAD  fixture: named_distinct={bad['named_distinct']} "
          f"named_total={bad['named']} generic={bad['generic']} "
          f"adoption_rate={bad['adoption_rate']:.2%}")
    print(f"  generics:  {bad['generic_list']}")


# ─────────── Runner ────────────────────────────────────────────────

def main():
    """Plain-runner mode — no pytest dependency."""
    tests = [
        test_pick_routes_zelda_like,
        test_pick_respects_specificity,
        test_load_catalog_has_content,
        test_load_missing_returns_empty,
        test_directive_wraps_content,
        test_extract_names_zelda_floor,
        test_probe_surfaces_content_from_gamedev_deliverable,
        test_ab_good_vs_bad_fixtures,
    ]
    failed: list[tuple[str, str]] = []
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except AssertionError as e:
            print(f"FAIL  {t.__name__}: {e}")
            failed.append((t.__name__, str(e)))
        except Exception as e:
            print(f"ERROR {t.__name__}: {type(e).__name__}: {e}")
            failed.append((t.__name__, f"{type(e).__name__}: {e}"))

    print()
    if failed:
        print(f"RESULT: {len(failed)}/{len(tests)} failed")
        for name, err in failed:
            print(f"  - {name}: {err}")
        sys.exit(1)
    print(f"RESULT: {len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
