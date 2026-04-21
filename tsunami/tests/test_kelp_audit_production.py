"""Tests for scripts/crew/kelp/audit_production.py.

The audit script is the protocol tool that filed Round 10's finding —
that Rounds 1/2/6 were dead code on real deliverables. These tests
lock down its registry format + classification logic so future kelp
rounds can rely on it.

Note on live-vs-DEAD classification: the absolute classification
depends on which session JSONL files exist in workspace/.history.
On a pristine / pre-deployment tree every signature shows DEAD
(nothing has fired yet). That's correct, not a bug. The tests here
use a tmp history dir with hand-crafted sessions so the classifier
runs against a known input.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parent.parent.parent
AUDIT = REPO / "scripts" / "crew" / "kelp" / "audit_production.py"
REGISTRY = REPO / "scripts" / "crew" / "kelp" / "fix_registry.jsonl"


class TestRegistryFormat:
    def test_registry_exists(self):
        assert REGISTRY.is_file(), \
            f"fix_registry.jsonl missing at {REGISTRY}"

    def test_every_line_valid_json_with_required_fields(self):
        required = {"slug", "sha", "signature", "expect_nonzero", "note"}
        with REGISTRY.open() as f:
            for ln, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                missing = required - entry.keys()
                assert not missing, \
                    f"line {ln}: missing fields {missing}. entry={entry}"
                assert isinstance(entry["expect_nonzero"], bool), \
                    f"line {ln}: expect_nonzero must be bool"

    def test_registry_covers_all_shipped_rounds(self):
        """Every slug in completed.jsonl (under ~/.tsunami/crew/kelp/)
        should have a registry entry, so the audit surface matches the
        shipped surface. Skip if completed.jsonl isn't accessible."""
        completed_path = Path.home() / ".tsunami" / "crew" / "kelp" / "completed.jsonl"
        if not completed_path.is_file():
            pytest.skip("completed.jsonl not found")
        shipped = set()
        with completed_path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except Exception:
                    continue
                if "slug" in entry:
                    shipped.add(entry["slug"])
        registry = set()
        with REGISTRY.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                registry.add(entry["slug"])
        missing = shipped - registry
        assert not missing, (
            f"Fix-registry missing entries for shipped slugs: "
            f"{sorted(missing)}. Every kelp commit should add a "
            f"registry line so the production audit can classify it."
        )


class TestAuditRunOnTmpHistory:
    """Run audit_production.py against a controlled session history
    so live / DEAD / refactor classifications can be pinned."""

    @pytest.fixture
    def tmp_history(self):
        """Create a fake workspace/.history populated with sessions
        that contain specific signatures. Returns (repo_root, env)."""
        root = Path(tempfile.mkdtemp(prefix="kelp_audit_"))
        (root / "workspace" / ".history").mkdir(parents=True)
        (root / "scripts" / "crew" / "kelp").mkdir(parents=True)
        # Copy the audit script into the fake repo root.
        audit_dst = root / "scripts" / "crew" / "kelp" / "audit_production.py"
        audit_dst.write_text(AUDIT.read_text())
        audit_dst.chmod(0o755)
        # Write a minimal registry with one live and one DEAD fix.
        reg = root / "scripts" / "crew" / "kelp" / "fix_registry.jsonl"
        reg.write_text(
            json.dumps({
                "slug": "live_fix",
                "sha": "abc1234",
                "signature": "LIVE_SIGNATURE_MARKER",
                "expect_nonzero": True,
                "note": "should fire",
            }) + "\n" +
            json.dumps({
                "slug": "dead_fix",
                "sha": "def5678",
                "signature": "UNFIRED_SIGNATURE_MARKER",
                "expect_nonzero": True,
                "note": "should be DEAD",
            }) + "\n" +
            json.dumps({
                "slug": "refactor_only",
                "sha": "ghi9012",
                "signature": "",
                "expect_nonzero": False,
                "note": "no runtime signature",
            }) + "\n"
        )
        # Write one session that contains the LIVE marker, zero containing
        # the UNFIRED marker.
        (root / "workspace" / ".history" / "session_1.jsonl").write_text(
            json.dumps({"role": "tool_result",
                        "content": "some output LIVE_SIGNATURE_MARKER more output"}) + "\n"
        )
        (root / "workspace" / ".history" / "session_2.jsonl").write_text(
            json.dumps({"role": "user", "content": "unrelated event"}) + "\n"
        )
        return root, audit_dst

    def test_audit_classifies_live_and_dead_correctly(self, tmp_history):
        root, script = tmp_history
        result = subprocess.run(
            ["python3", str(script), "--json"],
            capture_output=True, text=True, timeout=30,
        )
        # Exit code is 1 when at least one DEAD fix exists (the
        # post-push hook can key on this).
        assert result.returncode == 1, (
            f"expected exit=1 for DEAD fix present; got {result.returncode}. "
            f"stderr={result.stderr!r}"
        )
        payload = json.loads(result.stdout)
        by_slug = {p["slug"]: p for p in payload}
        assert by_slug["live_fix"]["sessions_hit"] == 1, \
            f"live_fix didn't classify as live: {by_slug['live_fix']}"
        assert by_slug["dead_fix"]["sessions_hit"] == 0, \
            f"dead_fix mis-classified: {by_slug['dead_fix']}"
        # refactor_only has no signature → hits stay zero but the exit
        # code should count it differently (it's not DEAD).
        assert by_slug["refactor_only"]["sessions_hit"] == 0
        assert by_slug["refactor_only"]["expect_nonzero"] is False

    def test_audit_no_dead_returns_zero(self, tmp_history):
        """If every expect_nonzero fix fires, exit code is 0."""
        root, script = tmp_history
        # Rewrite session_2.jsonl so it also contains UNFIRED marker.
        (root / "workspace" / ".history" / "session_2.jsonl").write_text(
            json.dumps({"role": "tool_result",
                        "content": "it fires UNFIRED_SIGNATURE_MARKER"}) + "\n"
        )
        result = subprocess.run(
            ["python3", str(script)],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, (
            f"expected exit=0 when no fix is DEAD; got {result.returncode}. "
            f"stdout={result.stdout!r}"
        )

    def test_slug_filter_narrows_audit(self, tmp_history):
        root, script = tmp_history
        result = subprocess.run(
            ["python3", str(script), "--slug", "live_fix", "--json"],
            capture_output=True, text=True, timeout=30,
        )
        payload = json.loads(result.stdout)
        assert len(payload) == 1
        assert payload[0]["slug"] == "live_fix"


class TestAuditReportRendering:
    """Render-path sanity — the human-readable report must include
    the DEAD section when DEAD fixes exist."""

    def test_dead_section_present_when_dead_fixes_exist(self, tmp_path: Path):
        (tmp_path / "workspace" / ".history").mkdir(parents=True)
        (tmp_path / "scripts" / "crew" / "kelp").mkdir(parents=True)
        script = tmp_path / "scripts" / "crew" / "kelp" / "audit_production.py"
        script.write_text(AUDIT.read_text())
        script.chmod(0o755)
        reg = tmp_path / "scripts" / "crew" / "kelp" / "fix_registry.jsonl"
        reg.write_text(json.dumps({
            "slug": "x", "sha": "abc", "signature": "never_fires_zzz",
            "expect_nonzero": True, "note": "",
        }) + "\n")
        result = subprocess.run(
            ["python3", str(script)],
            capture_output=True, text=True, timeout=30,
        )
        assert "DEAD FIXES" in result.stdout
        assert "never_fires_zzz" in result.stdout
