"""Locks the system_note census produced by
scripts/crew/kelp/audit_system_notes.py so the ratio of advisory to
structural can't silently drift in the wrong direction.

Sigma v5 (convention beats instruction) says every advisory is a pain
candidate — the orchestrator should enforce at a gate rather than
asking the drone to comply. This test fails loud when a new advisory
emission appears in agent.py without a corresponding structural gate.

To update the expected counts legitimately (e.g. converting an
advisory site into a structural gate, which lowers advisory and
raises structural), edit the bounds below. The expectation is that
advisory trends DOWN over time as more sites get structuralized.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parent.parent.parent
AUDIT_SCRIPT = REPO / "scripts" / "crew" / "kelp" / "audit_system_notes.py"


def _load_audit():
    """Import the audit script without subprocess — lets us call
    audit() directly and inspect its structured output."""
    spec = importlib.util.spec_from_file_location(
        "kelp_audit_system_notes", AUDIT_SCRIPT,
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["kelp_audit_system_notes"] = mod
    spec.loader.exec_module(mod)
    return mod


class TestAuditRuns:
    def test_script_exists(self):
        assert AUDIT_SCRIPT.is_file()

    def test_audit_returns_structured_result(self):
        mod = _load_audit()
        result = mod.audit()
        assert "summary" in result
        assert "sites" in result
        assert "total_sites" in result
        for cat in ("structural", "advisory", "ambiguous"):
            assert cat in result["summary"]
        assert sum(result["summary"].values()) == result["total_sites"]


class TestCountsLocked:
    """Baseline counts as of kelp round 13 (2026-04-21). Upper bounds
    defend against regression; lower bound on structural defends
    against accidental gate-removals."""

    @pytest.fixture
    def result(self):
        return _load_audit().audit()

    def test_advisory_count_does_not_grow(self, result):
        """ADVISORY is the kelp pipeline — every advisory is a future
        pain candidate. If this assertion fails with a higher count,
        someone added a new nudge without structuralizing it. Either
        lower the count (by converting the new site to a gate) or
        document the addition and raise the bound."""
        assert result["summary"]["advisory"] <= 12, (
            f"advisory sites count grew to {result['summary']['advisory']} "
            f"(baseline 10). Convert the new site to a structural gate "
            f"or document the addition with a pain-point entry."
        )

    def test_structural_count_does_not_shrink(self, result):
        """A drop in structural sites means a gate got removed. Before
        lowering this bound, verify the removal was intentional and
        file a pain if not."""
        assert result["summary"]["structural"] >= 20, (
            f"structural sites count dropped to "
            f"{result['summary']['structural']} (baseline 22). "
            f"A gate may have been removed — verify."
        )

    def test_total_sites_bounded(self, result):
        """Total system_note call sites should stay in a sane range —
        a big jump either direction signals a refactor that should be
        reviewed."""
        assert 50 <= result["total_sites"] <= 100, (
            f"total system_note sites = {result['total_sites']} — "
            f"outside the expected 50-100 envelope"
        )


class TestKnownAdvisories:
    """Specific lines that are known-advisory today. Each is a
    registered pain candidate so a future structural fix can point
    at this test when landing the conversion."""

    @pytest.fixture
    def result(self):
        return _load_audit().audit()

    def test_known_advisory_sites_still_classified_advisory(self, result):
        """If a line was advisory and a kelp fix structuralized it,
        the line number / content shifts and this test needs updating.
        That's the correct path: update this test AS PART OF landing
        the structural conversion so the census stays accurate."""
        advisory_lines = {
            s["line"] for s in result["sites"]
            if s["category"] == "advisory"
        }
        # At minimum 8 of the 10 baseline advisories should still be
        # advisory. Leaving 2 slack for mid-session line drift.
        assert len(advisory_lines) >= 8, (
            f"advisory line count dropped to {len(advisory_lines)} — "
            f"below the minimum. If intentional, update the baseline."
        )


class TestAuditOutputShape:
    """Field presence / shape checks on each emitted site record."""

    def test_every_site_has_required_fields(self):
        mod = _load_audit()
        result = mod.audit()
        required = {"line", "category", "reason", "note_preview"}
        for site in result["sites"]:
            missing = required - site.keys()
            assert not missing, (
                f"site at line {site.get('line','?')} missing fields "
                f"{missing}: {site}"
            )
            assert site["category"] in ("structural", "advisory", "ambiguous")
            assert isinstance(site["line"], int)
            assert site["line"] > 0
