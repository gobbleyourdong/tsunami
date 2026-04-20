"""Tests for F-A1 — promote_to_catalog drift report."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO))

from scripts.overnight.promote_to_catalog import (  # noqa: E402
    parse_promoted, parse_shipped, drift_report,
    render_stub_schema, render_stub_catalog, render_check,
)


FIXTURE_PROPOSALS = """\
# fixture proposals

### Pass 1 promotions
| Mechanic | Cites | Source games |
|---|---|---|
| `TurnBasedCombat` | 3 | FF4 + Chrono Trigger + FF7 |
| `ATBCombat` | 3 | FF4 + Chrono Trigger + FF7 |
| `NotYet` | 2 | A + B |

### Pass 2 promotions
| Mechanic | Cites | Source games |
|---|---|---|
| `DestructibleTerrain` | 3 | SMB + Zelda + Super Metroid |
"""

FIXTURE_SCHEMA = """\
// fixture schema
export type MechanicType =
  | 'Difficulty' | 'HUD' | 'LoseOnZero'
  | 'TurnBasedCombat'

export interface MechanicInstance {}
"""


def test_parse_promoted_picks_up_three_cites_only():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "prop.md"
        p.write_text(FIXTURE_PROPOSALS)
        promoted = parse_promoted(p)
        assert "TurnBasedCombat" in promoted
        assert "ATBCombat" in promoted
        assert "DestructibleTerrain" in promoted
        assert "NotYet" not in promoted  # only 2 cites
        assert promoted["TurnBasedCombat"] == ["FF4", "Chrono Trigger", "FF7"]


def test_parse_shipped_union_literals():
    with tempfile.TemporaryDirectory() as td:
        s = Path(td) / "schema.ts"
        s.write_text(FIXTURE_SCHEMA)
        shipped = parse_shipped(s)
        assert shipped == {"Difficulty", "HUD", "LoseOnZero", "TurnBasedCombat"}


def test_drift_report_identifies_missing():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "prop.md"; p.write_text(FIXTURE_PROPOSALS)
        s = Path(td) / "schema.ts"; s.write_text(FIXTURE_SCHEMA)
        rep = drift_report(p, s)
        assert rep["promoted_count"] == 3
        assert rep["shipped_count"] == 4  # includes non-promoted Difficulty, HUD, LoseOnZero
        assert rep["missing_count"] == 2   # ATBCombat + DestructibleTerrain
        missing_names = {m["name"] for m in rep["missing_mechanics"]}
        assert missing_names == {"ATBCombat", "DestructibleTerrain"}
        # Redundant = shipped but never ≥3-promoted
        assert "Difficulty" in rep["redundant_in_schema"]
        assert "TurnBasedCombat" not in rep["redundant_in_schema"]


def test_render_check_human_readable():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "prop.md"; p.write_text(FIXTURE_PROPOSALS)
        s = Path(td) / "schema.ts"; s.write_text(FIXTURE_SCHEMA)
        rep = drift_report(p, s)
        output = render_check(rep)
        assert "promoted (≥3 cites):" in output and "3" in output
        assert "missing" in output and "2" in output
        assert "ATBCombat" in output
        assert "DestructibleTerrain" in output


def test_render_stub_schema_emits_ts_union_lines():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "prop.md"; p.write_text(FIXTURE_PROPOSALS)
        s = Path(td) / "schema.ts"; s.write_text(FIXTURE_SCHEMA)
        rep = drift_report(p, s)
        stub = render_stub_schema(rep)
        assert "'ATBCombat'" in stub
        assert "'DestructibleTerrain'" in stub
        assert "| " in stub  # union syntax


def test_render_stub_catalog_has_todo_markers():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "prop.md"; p.write_text(FIXTURE_PROPOSALS)
        s = Path(td) / "schema.ts"; s.write_text(FIXTURE_SCHEMA)
        rep = drift_report(p, s)
        stub = render_stub_catalog(rep)
        assert "ATBCombat: {" in stub
        assert "TODO" in stub
        # Sources commented in
        assert "FF4" in stub


def test_real_corpus_reports_reasonable_drift():
    """Smoke test against actual repo files — confirms the real
    catalog_proposals.md parses and produces a drift report."""
    rep = drift_report()
    assert rep["promoted_count"] > 0
    assert rep["shipped_count"] > 0
    # We expect drift (many promoted mechanics not yet in schema).
    # Don't assert an exact number — corpus grows over time.
    assert rep["missing_count"] >= 50, (
        f"expected ≥50 missing mechanics, got {rep['missing_count']}. "
        f"Either the corpus shrunk or the parser broke."
    )


def main():
    tests = [
        test_parse_promoted_picks_up_three_cites_only,
        test_parse_shipped_union_literals,
        test_drift_report_identifies_missing,
        test_render_check_human_readable,
        test_render_stub_schema_emits_ts_union_lines,
        test_render_stub_catalog_has_todo_markers,
        test_real_corpus_reports_reasonable_drift,
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
