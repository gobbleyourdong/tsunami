"""Inter-eddy communication — shared context across swell batches.

When multiple eddies run in parallel (a swell), they're blind to each other.
Eddy 2 re-researches what eddy 1 already found. This module provides a
shared store so eddies can read each other's findings.

Flow:
1. Before swell batch: load shared context (prior eddy findings)
2. Each eddy gets prior findings injected into its system prompt
3. After each eddy completes: append its findings to shared context
4. After swell batch completes: cleanup shared context

Storage: workspace/.swell/shared_context.json
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path

log = logging.getLogger("tsunami.eddy_communication")


@dataclass
class EddyFinding:
    """What an eddy discovered during its work."""
    eddy_id: str
    task: str
    key_files: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    output_summary: str = ""
    timestamp: float = field(default_factory=time.time)


class SharedSwellContext:
    """Shared context store for a swell batch."""

    def __init__(self, workspace_dir: str | Path):
        self.workspace = Path(workspace_dir)
        self._store_dir = self.workspace / ".swell"
        self._store_path = self._store_dir / "shared_context.json"
        self.findings: list[EddyFinding] = []

    def load(self) -> list[EddyFinding]:
        """Load existing findings from disk."""
        if self._store_path.exists():
            try:
                data = json.loads(self._store_path.read_text())
                self.findings = [
                    EddyFinding(**f) for f in data.get("findings", [])
                ]
            except (json.JSONDecodeError, TypeError) as e:
                log.warning(f"Failed to load shared context: {e}")
                self.findings = []
        return self.findings

    def save(self):
        """Save findings to disk."""
        self._store_dir.mkdir(parents=True, exist_ok=True)
        data = {"findings": [asdict(f) for f in self.findings]}
        self._store_path.write_text(json.dumps(data, indent=2))

    def add_finding(self, finding: EddyFinding):
        """Add a finding and persist."""
        self.findings.append(finding)
        self.save()

    def to_prompt_injection(self) -> str | None:
        """Format findings as a prompt injection for the next eddy.

        Returns None if there are no findings to share.
        """
        if not self.findings:
            return None

        lines = ["[OTHER WORKERS' FINDINGS — use this to avoid duplicate work]"]
        for f in self.findings:
            parts = [f"- Eddy {f.eddy_id} ({f.task[:60]})"]
            if f.key_files:
                parts.append(f"  Files: {', '.join(f.key_files[:10])}")
            if f.decisions:
                parts.append(f"  Decisions: {'; '.join(f.decisions[:5])}")
            if f.output_summary:
                parts.append(f"  Output: {f.output_summary[:100]}")
            lines.append("\n".join(parts))

        return "\n".join(lines)

    def cleanup(self):
        """Delete shared context after swell batch completes."""
        if self._store_path.exists():
            self._store_path.unlink()
            log.info("Cleaned up shared swell context")

    def extract_finding_from_result(self, eddy_id: str, task: str, output: str, success: bool) -> EddyFinding:
        """Extract a finding from an eddy's result output.

        Parses the output for file paths, decisions, and creates a summary.
        """
        import re

        key_files = []
        decisions = []

        # Extract file paths mentioned in output
        for match in re.finditer(r'(?:src/|public/|components/|pages/)[\w/.-]+\.\w+', output):
            path = match.group(0)
            if path not in key_files:
                key_files.append(path)

        # Extract decisions (lines starting with common decision markers)
        for line in output.split("\n"):
            line = line.strip()
            if line.startswith(("Using ", "Chose ", "Selected ", "Going with ", "Decision: ")):
                decisions.append(line[:100])
            elif "should use" in line.lower() or "recommend" in line.lower():
                decisions.append(line[:100])

        # Summary = first 150 chars of non-empty output
        summary = ""
        for line in output.split("\n"):
            line = line.strip()
            if line and not line.startswith(("#", "```", "---")):
                summary = line[:150]
                break

        return EddyFinding(
            eddy_id=eddy_id,
            task=task,
            key_files=key_files[:10],
            decisions=decisions[:5],
            output_summary=summary if success else f"FAILED: {output[:100]}",
        )
