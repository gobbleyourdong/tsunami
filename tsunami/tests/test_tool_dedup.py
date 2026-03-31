"""Tests for tool call deduplication."""

import time
import pytest

from tsunami.tool_dedup import ToolDedup, NO_CACHE_TOOLS, _cache_key


class TestCacheKey:
    """Stable cache key generation."""

    def test_same_args_same_key(self):
        k1 = _cache_key("file_read", {"path": "/tmp/test.py"})
        k2 = _cache_key("file_read", {"path": "/tmp/test.py"})
        assert k1 == k2

    def test_different_args_different_key(self):
        k1 = _cache_key("file_read", {"path": "/tmp/a.py"})
        k2 = _cache_key("file_read", {"path": "/tmp/b.py"})
        assert k1 != k2

    def test_different_tool_different_key(self):
        k1 = _cache_key("file_read", {"path": "/tmp/test.py"})
        k2 = _cache_key("match_grep", {"path": "/tmp/test.py"})
        assert k1 != k2

    def test_arg_order_independent(self):
        k1 = _cache_key("test", {"a": 1, "b": 2})
        k2 = _cache_key("test", {"b": 2, "a": 1})
        assert k1 == k2  # sort_keys=True in json.dumps


class TestToolDedup:
    """Dedup lookup and store."""

    def test_miss_on_empty_cache(self):
        d = ToolDedup()
        assert d.lookup("file_read", {"path": "/tmp/test.py"}) is None

    def test_hit_after_store(self):
        d = ToolDedup()
        d.store("file_read", {"path": "/tmp/test.py"}, "content here")
        result = d.lookup("file_read", {"path": "/tmp/test.py"})
        assert result is not None
        content, is_error = result
        assert content == "content here"
        assert is_error is False

    def test_stores_error_state(self):
        d = ToolDedup()
        d.store("file_read", {"path": "/bad"}, "not found", is_error=True)
        result = d.lookup("file_read", {"path": "/bad"})
        assert result is not None
        _, is_error = result
        assert is_error is True

    def test_ttl_expiry(self):
        d = ToolDedup(ttl=0)  # instant expiry
        d.store("file_read", {"path": "/tmp/test.py"}, "content")
        time.sleep(0.01)
        assert d.lookup("file_read", {"path": "/tmp/test.py"}) is None

    def test_no_cache_tools_skipped_on_store(self):
        d = ToolDedup()
        for tool in ("shell_exec", "file_write", "message_info", "python_exec"):
            d.store(tool, {"x": 1}, "output")
            assert d.lookup(tool, {"x": 1}) is None

    def test_no_cache_tools_skipped_on_lookup(self):
        d = ToolDedup()
        # Manually inject into cache (bypassing store guard)
        d._cache["fake"] = ("content", time.time(), False)
        # shell_exec should still return None even if somehow cached
        assert d.lookup("shell_exec", {}) is None

    def test_invalidate_clears_all(self):
        d = ToolDedup()
        d.store("file_read", {"path": "/a"}, "a")
        d.store("match_grep", {"pattern": "x"}, "b")
        d.invalidate()
        assert d.lookup("file_read", {"path": "/a"}) is None
        assert d.lookup("match_grep", {"pattern": "x"}) is None

    def test_invalidate_on_write(self):
        d = ToolDedup()
        d.store("file_read", {"path": "/a"}, "a")
        d.invalidate_on_write()
        assert d.lookup("file_read", {"path": "/a"}) is None

    def test_different_args_independent(self):
        d = ToolDedup()
        d.store("file_read", {"path": "/a"}, "content_a")
        d.store("file_read", {"path": "/b"}, "content_b")
        r1 = d.lookup("file_read", {"path": "/a"})
        r2 = d.lookup("file_read", {"path": "/b"})
        assert r1[0] == "content_a"
        assert r2[0] == "content_b"


class TestToolDedupStats:
    """Hit/miss statistics."""

    def test_stats_initial(self):
        d = ToolDedup()
        assert d.stats["hits"] == 0
        assert d.stats["misses"] == 0

    def test_stats_track_hits_and_misses(self):
        d = ToolDedup()
        d.lookup("file_read", {"path": "/a"})  # miss
        d.store("file_read", {"path": "/a"}, "content")
        d.lookup("file_read", {"path": "/a"})  # hit
        d.lookup("file_read", {"path": "/a"})  # hit
        assert d.stats["hits"] == 2
        assert d.stats["misses"] == 1
        assert d.stats["hit_rate"] == "67%"

    def test_stats_cached_count(self):
        d = ToolDedup()
        d.store("file_read", {"path": "/a"}, "a")
        d.store("file_read", {"path": "/b"}, "b")
        assert d.stats["cached"] == 2


class TestNoCacheToolsList:
    """Verify the no-cache list covers all write/stateful tools."""

    def test_write_tools_excluded(self):
        for tool in ("file_write", "file_edit", "file_append"):
            assert tool in NO_CACHE_TOOLS

    def test_shell_tools_excluded(self):
        for tool in ("shell_exec", "shell_send", "shell_kill"):
            assert tool in NO_CACHE_TOOLS

    def test_message_tools_excluded(self):
        for tool in ("message_info", "message_ask", "message_result"):
            assert tool in NO_CACHE_TOOLS

    def test_read_tools_cacheable(self):
        for tool in ("file_read", "match_glob", "match_grep", "summarize_file"):
            assert tool not in NO_CACHE_TOOLS
