"""Tests for JSONL transcript storage."""

import json
import os
import tempfile
import pytest

from tsunami.transcript import (
    TranscriptEntry,
    write_transcript,
    read_transcript,
    find_leaf_messages,
    write_compact_boundary,
    write_metadata,
    message_to_entry,
    get_transcript_stats,
)


class TestWriteAndRead:
    """Basic JSONL round-trip."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.path = os.path.join(self.tmpdir, "session.jsonl")

    def test_write_and_read(self):
        entries = [
            TranscriptEntry(type="message", session_id="s1", data={"role": "user", "content": "hello"}),
            TranscriptEntry(type="message", session_id="s1", data={"role": "assistant", "content": "hi"}),
        ]
        write_transcript(entries, self.path)
        loaded = read_transcript(self.path, after_boundary=False)
        assert len(loaded) == 2
        assert loaded[0]["content"] == "hello"

    def test_append_mode(self):
        e1 = [TranscriptEntry(type="message", data={"content": "first"})]
        e2 = [TranscriptEntry(type="message", data={"content": "second"})]
        write_transcript(e1, self.path)
        write_transcript(e2, self.path)
        loaded = read_transcript(self.path, after_boundary=False)
        assert len(loaded) == 2

    def test_read_nonexistent(self):
        assert read_transcript("/nonexistent.jsonl") == []

    def test_valid_jsonl_format(self):
        entries = [TranscriptEntry(type="test", data={"x": 1})]
        write_transcript(entries, self.path)
        with open(self.path) as f:
            for line in f:
                json.loads(line)  # should not raise

    def test_preserves_uuid(self):
        entry = TranscriptEntry(type="message", uuid="abc123", data={})
        write_transcript([entry], self.path)
        loaded = read_transcript(self.path, after_boundary=False)
        assert loaded[0]["uuid"] == "abc123"


class TestCompactBoundary:
    """Lazy loading from compact boundary."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.path = os.path.join(self.tmpdir, "session.jsonl")

    def test_boundary_filters_old(self):
        # Write old messages
        old = [TranscriptEntry(type="message", data={"content": "old"})]
        write_transcript(old, self.path)

        # Write boundary
        write_compact_boundary(self.path, "s1", summary="compressed old stuff")

        # Write new messages
        new = [TranscriptEntry(type="message", data={"content": "new"})]
        write_transcript(new, self.path)

        # Read with after_boundary=True (default)
        loaded = read_transcript(self.path, after_boundary=True)
        assert len(loaded) == 2  # boundary + new message
        contents = [e.get("content", "") for e in loaded]
        assert "old" not in contents
        assert "new" in contents

    def test_no_boundary_returns_all(self):
        entries = [TranscriptEntry(type="message", data={"content": f"msg{i}"}) for i in range(5)]
        write_transcript(entries, self.path)
        loaded = read_transcript(self.path, after_boundary=True)
        assert len(loaded) == 5  # no boundary → return everything


class TestFindLeafMessages:
    """Resume point detection."""

    def test_linear_conversation(self):
        entries = [
            {"type": "message", "uuid": "a", "data": {"role": "user"}},
            {"type": "message", "uuid": "b", "parent_uuid": "a", "data": {"role": "assistant"}},
            {"type": "message", "uuid": "c", "parent_uuid": "b", "data": {"role": "user"}},
        ]
        leaves = find_leaf_messages(entries)
        assert len(leaves) == 1
        assert leaves[0]["uuid"] == "c"

    def test_branched_conversation(self):
        entries = [
            {"type": "message", "uuid": "root", "data": {"role": "user"}},
            {"type": "message", "uuid": "b1", "parent_uuid": "root", "data": {"role": "assistant"}},
            {"type": "message", "uuid": "b2", "parent_uuid": "root", "data": {"role": "assistant"}},
        ]
        leaves = find_leaf_messages(entries)
        assert len(leaves) == 2  # two branches

    def test_skips_metadata(self):
        entries = [
            {"type": "message", "uuid": "a", "data": {"role": "user"}},
            {"type": "metadata", "uuid": "m1", "data": {"key": "title"}},
            {"type": "message", "uuid": "b", "parent_uuid": "a", "data": {"role": "assistant"}},
        ]
        leaves = find_leaf_messages(entries)
        assert len(leaves) == 1
        assert leaves[0]["uuid"] == "b"

    def test_empty(self):
        assert find_leaf_messages([]) == []


class TestMessageToEntry:
    """Convert messages to transcript entries."""

    def test_basic_message(self):
        entry = message_to_entry("user", "hello", "s1")
        assert entry.type == "message"
        assert entry.data["role"] == "user"
        assert entry.data["content"] == "hello"
        assert entry.session_id == "s1"

    def test_with_tool_call(self):
        tc = {"function": {"name": "file_read", "arguments": {"path": "/tmp/test"}}}
        entry = message_to_entry("assistant", "", "s1", tool_call=tc)
        assert entry.data["tool_call"] == tc

    def test_with_parent(self):
        entry = message_to_entry("user", "follow-up", "s1", parent_uuid="abc")
        assert entry.data["parent_uuid"] == "abc"


class TestWriteMetadata:
    """Metadata entry writing."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.path = os.path.join(self.tmpdir, "session.jsonl")

    def test_write_title(self):
        write_metadata(self.path, "s1", "title", "My Session")
        loaded = read_transcript(self.path, after_boundary=False)
        assert loaded[0]["key"] == "title"
        assert loaded[0]["value"] == "My Session"

    def test_write_tag(self):
        write_metadata(self.path, "s1", "tag", "bugfix")
        loaded = read_transcript(self.path, after_boundary=False)
        assert loaded[0]["value"] == "bugfix"


class TestGetTranscriptStats:
    """Transcript file stats without full load."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_nonexistent(self):
        stats = get_transcript_stats("/nonexistent.jsonl")
        assert stats["exists"] is False

    def test_with_entries(self):
        path = os.path.join(self.tmpdir, "session.jsonl")
        entries = [TranscriptEntry(type="message", data={"content": f"msg{i}"}) for i in range(10)]
        write_transcript(entries, path)
        stats = get_transcript_stats(path)
        assert stats["exists"] is True
        assert stats["entries"] == 10
        assert stats["size_bytes"] > 0
