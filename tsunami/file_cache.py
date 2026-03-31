"""LRU file read cache with mtime invalidation.

Caches file contents keyed by path, invalidated when the file's
mtime changes. Prevents redundant disk reads when the agent reads
the same file multiple times in a session.

Size-bounded: evicts oldest entries when max_entries or max_bytes exceeded.
"""

from __future__ import annotations

import logging
import os
import time
from collections import OrderedDict
from dataclasses import dataclass

log = logging.getLogger("tsunami.file_cache")

DEFAULT_MAX_ENTRIES = 100
DEFAULT_MAX_BYTES = 25 * 1024 * 1024  # 25 MB


@dataclass
class CachedFile:
    """A cached file entry."""
    path: str
    content: str
    mtime: float
    size: int
    cached_at: float


class FileCache:
    """LRU file cache with mtime invalidation and size bounds.

    ts:
    - Max entries limit (default 100)
    - Size-based eviction (default 25MB)
    - Validates by mtime (stale entries auto-evicted)
    """

    def __init__(self, max_entries: int = DEFAULT_MAX_ENTRIES,
                 max_bytes: int = DEFAULT_MAX_BYTES):
        self.max_entries = max_entries
        self.max_bytes = max_bytes
        self._cache: OrderedDict[str, CachedFile] = OrderedDict()
        self._total_bytes = 0
        self._hits = 0
        self._misses = 0

    def get(self, path: str) -> str | None:
        """Get file content from cache, or None if miss/stale.

        Validates mtime — returns None if file changed on disk.
        """
        norm = os.path.realpath(path)
        entry = self._cache.get(norm)

        if entry is None:
            self._misses += 1
            return None

        # Check mtime — invalidate if file changed
        try:
            current_mtime = os.path.getmtime(norm)
        except OSError:
            # File deleted — evict
            self._evict(norm)
            self._misses += 1
            return None

        if current_mtime != entry.mtime:
            # File changed — evict stale entry
            self._evict(norm)
            self._misses += 1
            return None

        # Hit — move to end (most recently used)
        self._cache.move_to_end(norm)
        self._hits += 1
        return entry.content

    def put(self, path: str, content: str):
        """Cache file content with current mtime."""
        norm = os.path.realpath(path)

        # Evict old entry if exists
        if norm in self._cache:
            self._evict(norm)

        try:
            mtime = os.path.getmtime(norm)
        except OSError:
            return  # Can't cache a file we can't stat

        size = len(content.encode("utf-8"))

        # Evict until we have room
        while (
            self._cache
            and (len(self._cache) >= self.max_entries or self._total_bytes + size > self.max_bytes)
        ):
            self._evict_oldest()

        # Don't cache files larger than the entire budget
        if size > self.max_bytes:
            return

        self._cache[norm] = CachedFile(
            path=norm,
            content=content,
            mtime=mtime,
            size=size,
            cached_at=time.time(),
        )
        self._total_bytes += size

    def invalidate(self, path: str):
        """Manually invalidate a cached entry (e.g., after file_write)."""
        norm = os.path.realpath(path)
        if norm in self._cache:
            self._evict(norm)

    def invalidate_all(self):
        """Clear the entire cache."""
        self._cache.clear()
        self._total_bytes = 0

    def _evict(self, norm_path: str):
        """Remove a specific entry."""
        entry = self._cache.pop(norm_path, None)
        if entry:
            self._total_bytes -= entry.size

    def _evict_oldest(self):
        """Remove the least recently used entry."""
        if self._cache:
            _, entry = self._cache.popitem(last=False)
            self._total_bytes -= entry.size

    @property
    def size(self) -> int:
        return len(self._cache)

    @property
    def total_bytes(self) -> int:
        return self._total_bytes

    @property
    def stats(self) -> dict:
        total = self._hits + self._misses
        return {
            "entries": self.size,
            "bytes": self._total_bytes,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{self._hits / max(total, 1) * 100:.0f}%",
        }
