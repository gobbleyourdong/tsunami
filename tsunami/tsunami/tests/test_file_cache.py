"""Tests for LRU file cache with mtime invalidation."""

import os
import tempfile
import time
import pytest

from tsunami.file_cache import FileCache, DEFAULT_MAX_ENTRIES, DEFAULT_MAX_BYTES


class TestFileCacheBasic:
    """Cache hit/miss/invalidation."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.cache = FileCache()

    def _write_file(self, name: str, content: str) -> str:
        path = os.path.join(self.tmpdir, name)
        with open(path, "w") as f:
            f.write(content)
        return path

    def test_miss_on_empty(self):
        path = self._write_file("test.py", "hello")
        assert self.cache.get(path) is None

    def test_hit_after_put(self):
        path = self._write_file("test.py", "hello")
        self.cache.put(path, "hello")
        assert self.cache.get(path) == "hello"

    def test_invalidate_on_mtime_change(self):
        path = self._write_file("test.py", "hello")
        self.cache.put(path, "hello")
        assert self.cache.get(path) == "hello"
        # Modify file
        time.sleep(0.02)
        with open(path, "w") as f:
            f.write("world")
        assert self.cache.get(path) is None  # stale

    def test_invalidate_on_delete(self):
        path = self._write_file("test.py", "hello")
        self.cache.put(path, "hello")
        os.unlink(path)
        assert self.cache.get(path) is None

    def test_manual_invalidate(self):
        path = self._write_file("test.py", "hello")
        self.cache.put(path, "hello")
        self.cache.invalidate(path)
        assert self.cache.get(path) is None

    def test_invalidate_all(self):
        p1 = self._write_file("a.py", "a")
        p2 = self._write_file("b.py", "b")
        self.cache.put(p1, "a")
        self.cache.put(p2, "b")
        self.cache.invalidate_all()
        assert self.cache.get(p1) is None
        assert self.cache.get(p2) is None

    def test_stats_tracking(self):
        path = self._write_file("test.py", "hello")
        self.cache.get(path)  # miss
        self.cache.put(path, "hello")
        self.cache.get(path)  # hit
        self.cache.get(path)  # hit
        stats = self.cache.stats
        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["entries"] == 1


class TestFileCacheEviction:
    """LRU eviction by count and size."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def _write_file(self, name: str, content: str) -> str:
        path = os.path.join(self.tmpdir, name)
        with open(path, "w") as f:
            f.write(content)
        return path

    def test_evicts_on_max_entries(self):
        cache = FileCache(max_entries=3, max_bytes=10_000_000)
        paths = []
        for i in range(5):
            p = self._write_file(f"f{i}.py", f"content {i}")
            cache.put(p, f"content {i}")
            paths.append(p)
        assert cache.size <= 3
        # Most recent should still be cached
        assert cache.get(paths[-1]) is not None

    def test_evicts_on_max_bytes(self):
        cache = FileCache(max_entries=1000, max_bytes=100)
        paths = []
        for i in range(10):
            p = self._write_file(f"f{i}.py", "x" * 30)
            cache.put(p, "x" * 30)
            paths.append(p)
        assert cache.total_bytes <= 100

    def test_oversized_file_skipped(self):
        cache = FileCache(max_entries=100, max_bytes=50)
        p = self._write_file("huge.py", "x" * 100)
        cache.put(p, "x" * 100)
        assert cache.size == 0  # too big for cache

    def test_lru_order(self):
        cache = FileCache(max_entries=2, max_bytes=10_000_000)
        p1 = self._write_file("a.py", "a")
        p2 = self._write_file("b.py", "b")
        p3 = self._write_file("c.py", "c")
        cache.put(p1, "a")
        cache.put(p2, "b")
        cache.get(p1)  # access p1 — makes it recently used
        cache.put(p3, "c")  # should evict p2 (least recently used)
        assert cache.get(p1) is not None  # still cached
        assert cache.get(p2) is None  # evicted
        assert cache.get(p3) is not None  # just added


class TestFileCachePathNormalization:
    """Paths are normalized to handle ../  and symlinks."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.cache = FileCache()

    def test_relative_and_absolute_same_key(self):
        path = os.path.join(self.tmpdir, "test.py")
        with open(path, "w") as f:
            f.write("hello")
        self.cache.put(path, "hello")
        # Access via different path form
        alt_path = os.path.join(self.tmpdir, ".", "test.py")
        assert self.cache.get(os.path.realpath(alt_path)) == "hello"
