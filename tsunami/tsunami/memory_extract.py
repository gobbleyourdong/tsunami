"""Session memory extraction — durable learnings across sessions.

At the end of a session (or periodically during long sessions),
extracts key learnings into persistent memory files that get
injected into future sessions' system prompts.

Four memory types:
- user: role, expertise, preferences
- feedback: corrections and confirmed approaches
- project: goals, deadlines, constraints
- reference: pointers to external systems

Memory is stored as markdown files with YAML frontmatter in
workspace/.memory/. An index file (MEMORY.md) tracks all entries.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger("tsunami.memory_extract")

MEMORY_DIR_NAME = ".memory"
INDEX_FILE = "MEMORY.md"
MAX_INDEX_LINES = 200
MAX_INDEX_BYTES = 25_000

# Memory types
VALID_TYPES = frozenset({"user", "feedback", "project", "reference"})

# What should NOT be saved (from Claude Code's memoryTypes.ts)
EXCLUSIONS = [
    "code patterns",
    "architecture",
    "file paths",
    "git history",
    "debugging solutions",
    "ephemeral task state",
]


@dataclass
class MemoryEntry:
    """A single memory entry."""
    name: str
    description: str
    memory_type: str  # user, feedback, project, reference
    content: str
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_markdown(self) -> str:
        """Serialize as markdown with YAML frontmatter."""
        return (
            f"---\n"
            f"name: {self.name}\n"
            f"description: {self.description}\n"
            f"type: {self.memory_type}\n"
            f"---\n\n"
            f"{self.content}\n"
        )

    @classmethod
    def from_markdown(cls, text: str, filepath: str = "") -> MemoryEntry | None:
        """Parse from markdown with YAML frontmatter."""
        if not text.startswith("---"):
            return None
        parts = text.split("---", 2)
        if len(parts) < 3:
            return None

        # Parse frontmatter
        meta = {}
        for line in parts[1].strip().split("\n"):
            if ":" in line:
                key, _, value = line.partition(":")
                meta[key.strip()] = value.strip()

        content = parts[2].strip()
        return cls(
            name=meta.get("name", ""),
            description=meta.get("description", ""),
            memory_type=meta.get("type", "project"),
            content=content,
        )


class MemoryStore:
    """Persistent memory store for cross-session learnings."""

    def __init__(self, workspace_dir: str):
        self.memory_dir = Path(workspace_dir) / MEMORY_DIR_NAME
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.memory_dir / INDEX_FILE

    def save(self, entry: MemoryEntry) -> str:
        """Save a memory entry to disk. Returns the file path."""
        # Generate safe filename
        safe_name = entry.name.lower().replace(" ", "_").replace("/", "_")
        safe_name = "".join(c for c in safe_name if c.isalnum() or c == "_")
        filename = f"{entry.memory_type}_{safe_name}.md"
        filepath = self.memory_dir / filename

        # Check for existing entry to update
        existing = self._find_by_name(entry.name)
        if existing:
            filepath = Path(existing)
            entry.updated_at = time.time()

        filepath.write_text(entry.to_markdown())
        self._update_index()

        log.info(f"Memory saved: {entry.name} ({entry.memory_type}) → {filepath.name}")
        return str(filepath)

    def load_all(self) -> list[MemoryEntry]:
        """Load all memory entries."""
        entries = []
        for f in sorted(self.memory_dir.glob("*.md")):
            if f.name == INDEX_FILE:
                continue
            try:
                entry = MemoryEntry.from_markdown(f.read_text(), str(f))
                if entry:
                    entries.append(entry)
            except Exception:
                continue
        return entries

    def load_by_type(self, memory_type: str) -> list[MemoryEntry]:
        """Load entries of a specific type."""
        return [e for e in self.load_all() if e.memory_type == memory_type]

    def remove(self, name: str) -> bool:
        """Remove a memory entry by name."""
        path = self._find_by_name(name)
        if path:
            os.unlink(path)
            self._update_index()
            log.info(f"Memory removed: {name}")
            return True
        return False

    def format_for_prompt(self, max_tokens: int = 2000) -> str:
        """Format memories for injection into system prompt.

        Prioritizes: feedback > user > project > reference.
        Stays within token budget.
        """
        entries = self.load_all()
        if not entries:
            return ""

        # Priority order
        priority = {"feedback": 0, "user": 1, "project": 2, "reference": 3}
        entries.sort(key=lambda e: priority.get(e.memory_type, 4))

        lines = ["# Persistent Memory (from previous sessions)"]
        chars = 0
        for entry in entries:
            line = f"\n## [{entry.memory_type}] {entry.name}\n{entry.content}"
            if chars + len(line) > max_tokens * 4:
                break
            lines.append(line)
            chars += len(line)

        return "\n".join(lines) if len(lines) > 1 else ""

    def _find_by_name(self, name: str) -> str | None:
        """Find an existing memory file by entry name."""
        for f in self.memory_dir.glob("*.md"):
            if f.name == INDEX_FILE:
                continue
            try:
                text = f.read_text()
                if f"name: {name}" in text[:200]:
                    return str(f)
            except Exception:
                continue
        return None

    def _update_index(self):
        """Rebuild the MEMORY.md index file."""
        entries = self.load_all()
        lines = ["# Memory Index", ""]
        for entry in entries:
            safe_name = entry.name.lower().replace(" ", "_").replace("/", "_")
            safe_name = "".join(c for c in safe_name if c.isalnum() or c == "_")
            filename = f"{entry.memory_type}_{safe_name}.md"
            line = f"- [{entry.name}]({filename}) — {entry.description}"
            if len(line) > 150:
                line = line[:147] + "..."
            lines.append(line)

        # Respect limits
        text = "\n".join(lines[:MAX_INDEX_LINES])
        if len(text.encode()) > MAX_INDEX_BYTES:
            text = text[:MAX_INDEX_BYTES]

        self.index_path.write_text(text)

    @property
    def count(self) -> int:
        return len([f for f in self.memory_dir.glob("*.md") if f.name != INDEX_FILE])


def should_extract_memory(
    token_count: int,
    tool_call_count: int,
    last_extraction_tokens: int = 0,
    min_tokens: int = 10_000,
    growth_threshold: int = 5_000,
    min_tool_calls: int = 3,
) -> bool:
    """Decide if memory extraction should run.

    Triggers when:
    1. Session has enough content (>= min_tokens)
    2. AND enough new content since last extraction (>= growth_threshold)
    3. AND enough tool activity (>= min_tool_calls)
    """
    if token_count < min_tokens:
        return False
    growth = token_count - last_extraction_tokens
    if growth < growth_threshold:
        return False
    if tool_call_count < min_tool_calls:
        return False
    return True
