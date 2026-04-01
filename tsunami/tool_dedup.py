"""Tool call deduplication — skip identical repeated calls.


When the model calls the same tool with the same arguments within
a short window, return the cached result instead of re-executing.

This prevents:
- Reading the same file twice in a row
- Running the same shell command repeatedly
- Wasting cycles on identical glob/grep searches

Some tools are excluded (message_*, shell_exec with side effects).
"""

from __future__ import annotations

import hashlib
import json
import logging
import time

log = logging.getLogger("tsunami.tool_dedup")

# How long cached results stay valid (seconds)
CACHE_TTL = 30

# Tools that should NEVER be cached (side effects or stateful)
NO_CACHE_TOOLS = frozenset({
    "shell_exec", "shell_send", "shell_kill",
    "file_write", "file_edit", "file_append",
    "message_info", "message_ask", "message_result",
    "plan_update", "plan_advance",
    "python_exec",
    "swell", "swell_analyze",
    "search_web",
})


def _cache_key(tool_name: str, args: dict) -> str:
    """Generate a stable cache key from tool name + args."""
    raw = json.dumps({"tool": tool_name, "args": args}, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


class ToolDedup:
    """Cache layer for tool call deduplication."""

    def __init__(self, ttl: int = CACHE_TTL):
        self.ttl = ttl
        self._cache: dict[str, tuple[str, float, bool]] = {}  # key → (content, timestamp, is_error)
        self._hits = 0
        self._misses = 0

    def lookup(self, tool_name: str, args: dict) -> tuple[str, bool] | None:
        """Check if a cached result exists for this tool call.

        Returns (content, is_error) if cached, None if miss.
        """
        if tool_name in NO_CACHE_TOOLS:
            return None

        key = _cache_key(tool_name, args)
        entry = self._cache.get(key)
        if entry is None:
            self._misses += 1
            return None

        content, ts, is_error = entry
        if time.time() - ts > self.ttl:
            # Expired
            del self._cache[key]
            self._misses += 1
            return None

        self._hits += 1
        log.debug(f"Dedup hit: {tool_name} (key={key[:8]})")
        return content, is_error

    def store(self, tool_name: str, args: dict, content: str, is_error: bool = False):
        """Store a tool result in the cache."""
        if tool_name in NO_CACHE_TOOLS:
            return

        key = _cache_key(tool_name, args)
        self._cache[key] = (content, time.time(), is_error)

    def invalidate(self, tool_name: str | None = None):
        """Invalidate cache entries.

        If tool_name given, only invalidate that tool's entries.
        Otherwise, clear everything.
        """
        if tool_name is None:
            self._cache.clear()
            return

        # Invalidate by tool name (need to check all entries)
        to_remove = [
            k for k, (content, ts, _) in self._cache.items()
            # We can't recover the tool name from the hash, so clear all on write
        ]
        # Actually, after a file_write/edit, all file_read caches could be stale
        # So we just clear everything on any write operation
        self._cache.clear()

    def invalidate_on_write(self):
        """Called after any write operation (file_write, file_edit, shell_exec).

        Clears all cached reads since the filesystem state changed.
        """
        self._cache.clear()

    @property
    def stats(self) -> dict:
        return {
            "hits": self._hits,
            "misses": self._misses,
            "cached": len(self._cache),
            "hit_rate": f"{self._hits / max(self._hits + self._misses, 1) * 100:.0f}%",
        }
