"""Tests for Chunk 5: Inter-Eddy Communication.

Verifies:
- SharedSwellContext persistence (save/load)
- EddyFinding extraction from results
- Prompt injection formatting
- Cleanup after swell
- Finding dedup and limits
"""

import json
import tempfile
import os

from tsunami.eddy_communication import (
    SharedSwellContext,
    EddyFinding,
)


class TestSharedSwellContext:
    """Persistence and lifecycle."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_save_and_load(self):
        ctx = SharedSwellContext(self.tmpdir)
        ctx.add_finding(EddyFinding(
            eddy_id="eddy_0",
            task="search for React patterns",
            key_files=["src/App.tsx"],
            decisions=["Using React 18"],
            output_summary="Found component patterns",
        ))
        # New instance loads from disk
        ctx2 = SharedSwellContext(self.tmpdir)
        ctx2.load()
        assert len(ctx2.findings) == 1
        assert ctx2.findings[0].eddy_id == "eddy_0"

    def test_multiple_findings(self):
        ctx = SharedSwellContext(self.tmpdir)
        ctx.add_finding(EddyFinding(eddy_id="e0", task="task0"))
        ctx.add_finding(EddyFinding(eddy_id="e1", task="task1"))
        ctx.add_finding(EddyFinding(eddy_id="e2", task="task2"))

        ctx2 = SharedSwellContext(self.tmpdir)
        ctx2.load()
        assert len(ctx2.findings) == 3

    def test_cleanup_removes_file(self):
        ctx = SharedSwellContext(self.tmpdir)
        ctx.add_finding(EddyFinding(eddy_id="e0", task="task"))
        assert os.path.exists(os.path.join(self.tmpdir, ".swell", "shared_context.json"))
        ctx.cleanup()
        assert not os.path.exists(os.path.join(self.tmpdir, ".swell", "shared_context.json"))

    def test_load_empty(self):
        ctx = SharedSwellContext(self.tmpdir)
        findings = ctx.load()
        assert findings == []

    def test_load_corrupted_json(self):
        """Corrupted file should not crash."""
        swell_dir = os.path.join(self.tmpdir, ".swell")
        os.makedirs(swell_dir)
        with open(os.path.join(swell_dir, "shared_context.json"), "w") as f:
            f.write("{invalid json")
        ctx = SharedSwellContext(self.tmpdir)
        ctx.load()
        assert ctx.findings == []


class TestPromptInjection:
    """Format findings for eddy system prompt."""

    def test_no_findings_returns_none(self):
        ctx = SharedSwellContext(tempfile.mkdtemp())
        assert ctx.to_prompt_injection() is None

    def test_single_finding_formatted(self):
        ctx = SharedSwellContext(tempfile.mkdtemp())
        ctx.findings = [EddyFinding(
            eddy_id="eddy_0",
            task="search for charts",
            key_files=["src/Chart.tsx", "src/types.ts"],
            decisions=["Using recharts library"],
            output_summary="Found recharts is best for dashboards",
        )]
        prompt = ctx.to_prompt_injection()
        assert prompt is not None
        assert "OTHER WORKERS" in prompt
        assert "eddy_0" in prompt
        assert "Chart.tsx" in prompt
        assert "recharts" in prompt

    def test_multiple_findings_all_included(self):
        ctx = SharedSwellContext(tempfile.mkdtemp())
        ctx.findings = [
            EddyFinding(eddy_id="e0", task="task A", output_summary="found A"),
            EddyFinding(eddy_id="e1", task="task B", output_summary="found B"),
        ]
        prompt = ctx.to_prompt_injection()
        assert "e0" in prompt
        assert "e1" in prompt
        assert "found A" in prompt
        assert "found B" in prompt


class TestExtractFinding:
    """Extract findings from eddy result output."""

    def setup_method(self):
        self.ctx = SharedSwellContext(tempfile.mkdtemp())

    def test_extracts_file_paths(self):
        output = "I found relevant code in src/components/Chart.tsx and src/types.ts"
        finding = self.ctx.extract_finding_from_result("e0", "search", output, True)
        assert "src/components/Chart.tsx" in finding.key_files
        assert "src/types.ts" in finding.key_files

    def test_extracts_decisions(self):
        output = "Using recharts for the chart library\nSelected dark mode theme"
        finding = self.ctx.extract_finding_from_result("e0", "search", output, True)
        assert any("recharts" in d for d in finding.decisions)
        assert any("dark mode" in d for d in finding.decisions)

    def test_extracts_summary(self):
        output = "The best approach is to use a grid layout\n# Details\nMore info..."
        finding = self.ctx.extract_finding_from_result("e0", "task", output, True)
        assert "grid layout" in finding.output_summary

    def test_failed_result(self):
        output = "Some error happened"
        finding = self.ctx.extract_finding_from_result("e0", "task", output, False)
        assert "FAILED" in finding.output_summary

    def test_empty_output(self):
        finding = self.ctx.extract_finding_from_result("e0", "task", "", True)
        assert finding.output_summary == ""
        assert finding.key_files == []

    def test_caps_files_at_10(self):
        paths = [f"src/components/File{i}.tsx" for i in range(20)]
        output = " ".join(paths)
        finding = self.ctx.extract_finding_from_result("e0", "task", output, True)
        assert len(finding.key_files) <= 10

    def test_caps_decisions_at_5(self):
        lines = [f"Using library_{i}" for i in range(10)]
        output = "\n".join(lines)
        finding = self.ctx.extract_finding_from_result("e0", "task", output, True)
        assert len(finding.decisions) <= 5


class TestEddyFinding:
    """EddyFinding dataclass."""

    def test_default_values(self):
        f = EddyFinding(eddy_id="e0", task="test")
        assert f.key_files == []
        assert f.decisions == []
        assert f.output_summary == ""
        assert f.timestamp > 0

    def test_serialization(self):
        from dataclasses import asdict
        f = EddyFinding(
            eddy_id="e0", task="test",
            key_files=["a.ts"], decisions=["use X"],
        )
        d = asdict(f)
        assert d["eddy_id"] == "e0"
        assert "a.ts" in d["key_files"]
        # Round-trip
        f2 = EddyFinding(**d)
        assert f2.eddy_id == f.eddy_id
