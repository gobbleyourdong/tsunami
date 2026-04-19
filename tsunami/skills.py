"""Waveforms — the extensibility mechanism.

Waveforms are modular capability extensions stored as directories
with a WAVEFORM.md instruction file. They allow the agent to learn
new capabilities without changing source code.

Users drop a folder into waveforms/ with a WAVEFORM.md and the agent
picks it up automatically on next run.
"""

from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger("tsunami.skills")

# Support both old "SKILL.md" and new "WAVEFORM.md"
SKILL_FILES = ["WAVEFORM.md", "SKILL.md"]


class SkillsManager:
    """Discovers and loads waveforms from the waveforms directory."""

    def __init__(self, skills_dir: str | Path):
        self.skills_dir = Path(skills_dir)

    def _find_skill_md(self, skill_dir: Path) -> Path | None:
        for name in SKILL_FILES:
            p = skill_dir / name
            if p.exists():
                return p
        return None

    def list_skills(self) -> list[dict]:
        """List all available waveforms with their descriptions."""
        skills = []
        if not self.skills_dir.exists():
            return skills

        for skill_dir in sorted(self.skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_md = self._find_skill_md(skill_dir)
            if not skill_md:
                continue

            content = skill_md.read_text()
            lines = content.strip().splitlines()
            title = lines[0].lstrip("# ").strip() if lines else skill_dir.name
            desc = ""
            for line in lines[1:]:
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line
                    break

            skills.append({
                "name": skill_dir.name,
                "title": title,
                "description": desc,
                "path": str(skill_dir),
            })

        return skills

    def load_skill(self, name: str) -> str | None:
        """Load a waveform's full instructions."""
        skill_dir = self.skills_dir / name
        skill_md = self._find_skill_md(skill_dir)
        if not skill_md:
            return None
        return skill_md.read_text()

    def load_all_skill_content(self) -> str:
        """Inject a one-line index of available skills, not their full content.

        Prior impl inlined up to 32K chars (~8K tokens) of skill bodies into
        every system prompt — dominating prefill cost even when the task
        didn't need any of them. Now we inject a short index; the agent
        file_reads the relevant SKILL.md when a task matches.
        """
        skills = self.list_skills()
        if not skills:
            return ""
        lines = ["Skills (file_read the path for full instructions):"]
        for s in skills:
            desc = s["description"] or s["title"]
            lines.append(f"- {s['name']}: {desc} ({s['path']}/SKILL.md)")
        return "\n".join(lines)

    def skills_summary(self) -> str:
        """Generate a summary for injection into the system prompt."""
        skills = self.list_skills()
        if not skills:
            return "No skills installed."

        lines = ["Available waveforms:"]
        for s in skills:
            lines.append(f"  - {s['name']}: {s['description']}")
        lines.append(f"\nWaveforms directory: {self.skills_dir}")
        return "\n".join(lines)
