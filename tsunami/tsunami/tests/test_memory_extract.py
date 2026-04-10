"""Tests for session memory extraction — durable cross-session learnings."""

import os
import tempfile
import pytest

from tsunami.memory_extract import (
    MemoryEntry,
    MemoryStore,
    should_extract_memory,
    VALID_TYPES,
    INDEX_FILE,
)


class TestMemoryEntry:
    """Individual memory entry serialization."""

    def test_to_markdown(self):
        entry = MemoryEntry(
            name="user prefers terse",
            description="User wants short responses",
            memory_type="feedback",
            content="Don't summarize at the end of responses.\n\n**Why:** User can read diffs.",
        )
        md = entry.to_markdown()
        assert "---" in md
        assert "name: user prefers terse" in md
        assert "type: feedback" in md
        assert "Don't summarize" in md

    def test_from_markdown(self):
        md = (
            "---\n"
            "name: test memory\n"
            "description: a test\n"
            "type: user\n"
            "---\n\n"
            "Content here.\n"
        )
        entry = MemoryEntry.from_markdown(md)
        assert entry is not None
        assert entry.name == "test memory"
        assert entry.memory_type == "user"
        assert entry.content == "Content here."

    def test_round_trip(self):
        original = MemoryEntry(
            name="round trip",
            description="test",
            memory_type="project",
            content="Line 1\nLine 2\n\nParagraph 2.",
        )
        md = original.to_markdown()
        loaded = MemoryEntry.from_markdown(md)
        assert loaded.name == original.name
        assert loaded.memory_type == original.memory_type
        assert loaded.content == original.content

    def test_from_invalid_markdown(self):
        assert MemoryEntry.from_markdown("no frontmatter") is None
        assert MemoryEntry.from_markdown("---\nonly one fence") is None


class TestMemoryStore:
    """Persistent memory storage."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.store = MemoryStore(self.tmpdir)

    def test_save_creates_file(self):
        entry = MemoryEntry(name="test", description="d", memory_type="user", content="c")
        path = self.store.save(entry)
        assert os.path.exists(path)

    def test_save_creates_index(self):
        entry = MemoryEntry(name="test", description="d", memory_type="user", content="c")
        self.store.save(entry)
        index_path = os.path.join(self.tmpdir, ".memory", INDEX_FILE)
        assert os.path.exists(index_path)

    def test_load_all(self):
        self.store.save(MemoryEntry(name="a", description="d", memory_type="user", content="1"))
        self.store.save(MemoryEntry(name="b", description="d", memory_type="feedback", content="2"))
        entries = self.store.load_all()
        assert len(entries) == 2

    def test_load_by_type(self):
        self.store.save(MemoryEntry(name="u1", description="d", memory_type="user", content="1"))
        self.store.save(MemoryEntry(name="f1", description="d", memory_type="feedback", content="2"))
        self.store.save(MemoryEntry(name="u2", description="d", memory_type="user", content="3"))
        users = self.store.load_by_type("user")
        assert len(users) == 2

    def test_remove(self):
        self.store.save(MemoryEntry(name="removeme", description="d", memory_type="user", content="c"))
        assert self.store.count == 1
        removed = self.store.remove("removeme")
        assert removed is True
        assert self.store.count == 0

    def test_remove_nonexistent(self):
        assert self.store.remove("nope") is False

    def test_update_existing(self):
        self.store.save(MemoryEntry(name="evolving", description="v1", memory_type="user", content="old"))
        self.store.save(MemoryEntry(name="evolving", description="v2", memory_type="user", content="new"))
        entries = self.store.load_all()
        assert len(entries) == 1
        assert entries[0].content == "new"

    def test_count(self):
        assert self.store.count == 0
        self.store.save(MemoryEntry(name="a", description="d", memory_type="user", content="c"))
        assert self.store.count == 1

    def test_format_for_prompt_empty(self):
        assert self.store.format_for_prompt() == ""

    def test_format_for_prompt_with_entries(self):
        self.store.save(MemoryEntry(
            name="pref", description="user pref",
            memory_type="feedback", content="Terse responses preferred.",
        ))
        prompt = self.store.format_for_prompt()
        assert "Persistent Memory" in prompt
        assert "Terse responses" in prompt

    def test_format_respects_token_budget(self):
        for i in range(20):
            self.store.save(MemoryEntry(
                name=f"big_{i}", description="d",
                memory_type="user", content="x" * 2000,
            ))
        prompt = self.store.format_for_prompt(max_tokens=500)
        # Should be truncated
        assert len(prompt) < 500 * 4 + 200  # rough budget

    def test_feedback_prioritized(self):
        self.store.save(MemoryEntry(name="proj", description="d", memory_type="project", content="project stuff"))
        self.store.save(MemoryEntry(name="feed", description="d", memory_type="feedback", content="feedback stuff"))
        prompt = self.store.format_for_prompt()
        # Feedback should appear before project
        fb_idx = prompt.index("feedback stuff")
        pj_idx = prompt.index("project stuff")
        assert fb_idx < pj_idx


class TestShouldExtractMemory:
    """Extraction trigger conditions."""

    def test_too_few_tokens(self):
        assert should_extract_memory(5000, tool_call_count=10) is False

    def test_enough_tokens_and_growth(self):
        assert should_extract_memory(
            token_count=15000,
            tool_call_count=5,
            last_extraction_tokens=0,
        ) is True

    def test_not_enough_growth(self):
        assert should_extract_memory(
            token_count=15000,
            tool_call_count=5,
            last_extraction_tokens=14000,  # only 1K growth
        ) is False

    def test_not_enough_tool_calls(self):
        assert should_extract_memory(
            token_count=15000,
            tool_call_count=1,
            last_extraction_tokens=0,
        ) is False

    def test_all_conditions_met(self):
        assert should_extract_memory(
            token_count=20000,
            tool_call_count=10,
            last_extraction_tokens=10000,
        ) is True

    def test_custom_thresholds(self):
        assert should_extract_memory(
            token_count=500,
            tool_call_count=1,
            last_extraction_tokens=0,
            min_tokens=100,
            growth_threshold=100,
            min_tool_calls=1,
        ) is True


class TestMemoryIndex:
    """MEMORY.md index file."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.store = MemoryStore(self.tmpdir)

    def test_index_updated_on_save(self):
        self.store.save(MemoryEntry(name="indexed", description="appears in index", memory_type="user", content="c"))
        index_path = os.path.join(self.tmpdir, ".memory", INDEX_FILE)
        index = open(index_path).read()
        assert "indexed" in index
        assert "appears in index" in index

    def test_index_updated_on_remove(self):
        self.store.save(MemoryEntry(name="temp", description="d", memory_type="user", content="c"))
        self.store.remove("temp")
        index_path = os.path.join(self.tmpdir, ".memory", INDEX_FILE)
        index = open(index_path).read()
        assert "temp" not in index

    def test_index_has_header(self):
        self.store.save(MemoryEntry(name="x", description="d", memory_type="user", content="c"))
        index_path = os.path.join(self.tmpdir, ".memory", INDEX_FILE)
        index = open(index_path).read()
        assert "# Memory Index" in index
