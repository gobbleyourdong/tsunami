"""Composable system prompt sections with lazy caching.

The system prompt is split into sections that are independently
cacheable. Static sections (identity, rules) compute once per session.
Dynamic sections (environment, plan, projects) recompute every turn.

This pattern:
1. Reduces prompt build time (cached sections skip computation)
2. Enables cache-key optimization (static prefix is identical across turns)
3. Lets tools inject their own context dynamically

The DYNAMIC_BOUNDARY marker separates static from dynamic content.
Everything before it can be cached globally; everything after is per-turn.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Callable

log = logging.getLogger("tsunami.prompt_sections")

# Marker that separates cacheable from dynamic content
# Model never sees this — it's for cache key splitting
DYNAMIC_BOUNDARY = "__PROMPT_DYNAMIC_BOUNDARY__"


@dataclass
class PromptSection:
    """A single section of the system prompt."""
    name: str
    compute: Callable[[], str]
    cacheable: bool = True  # if True, computed once and cached
    _cache: str | None = field(default=None, repr=False)
    _cache_time: float = 0

    def resolve(self, force: bool = False) -> str:
        """Resolve the section content, using cache if available."""
        if self.cacheable and self._cache is not None and not force:
            return self._cache
        value = self.compute()
        if self.cacheable:
            self._cache = value
            self._cache_time = time.time()
        return value

    def invalidate(self):
        """Clear the cached value."""
        self._cache = None
        self._cache_time = 0


class PromptBuilder:
    """Composable system prompt builder with section caching.

    Sections are added in order. Static sections are cached after
    first computation. Dynamic sections recompute every resolve().
    Tool-injected sections can be added/removed at runtime.
    """

    def __init__(self):
        self._static_sections: list[PromptSection] = []
        self._dynamic_sections: list[PromptSection] = []
        self._tool_sections: dict[str, PromptSection] = {}

    def add_static(self, name: str, compute: Callable[[], str]):
        """Add a cacheable section (identity, rules, etc.)."""
        self._static_sections.append(
            PromptSection(name=name, compute=compute, cacheable=True)
        )

    def add_dynamic(self, name: str, compute: Callable[[], str]):
        """Add a per-turn section (environment, plan, etc.)."""
        self._dynamic_sections.append(
            PromptSection(name=name, compute=compute, cacheable=False)
        )

    def inject_tool_section(self, tool_name: str, compute: Callable[[], str]):
        """Let a tool inject its own prompt context.

        Tool sections are dynamic (recomputed per turn) and live
        after the dynamic boundary.
        """
        self._tool_sections[tool_name] = PromptSection(
            name=f"tool:{tool_name}",
            compute=compute,
            cacheable=False,
        )

    def remove_tool_section(self, tool_name: str):
        """Remove a tool's injected section."""
        self._tool_sections.pop(tool_name, None)

    def resolve(self) -> str:
        """Build the complete system prompt.

        Order: static sections → BOUNDARY → dynamic sections → tool sections
        """
        parts = []

        # Static prefix (cacheable across turns)
        for section in self._static_sections:
            content = section.resolve()
            if content:
                parts.append(content)

        # Dynamic suffix (changes per turn)
        dynamic_parts = []
        for section in self._dynamic_sections:
            content = section.resolve()
            if content:
                dynamic_parts.append(content)

        # Tool-injected sections
        for section in self._tool_sections.values():
            content = section.resolve()
            if content:
                dynamic_parts.append(content)

        if dynamic_parts:
            parts.extend(dynamic_parts)

        return "\n\n---\n\n".join(parts)

    def resolve_split(self) -> tuple[str, str]:
        """Build prompt split into static prefix and dynamic suffix.

        Returns (static_prefix, dynamic_suffix).
        Useful for cache-key optimization.
        """
        static_parts = []
        for section in self._static_sections:
            content = section.resolve()
            if content:
                static_parts.append(content)

        dynamic_parts = []
        for section in self._dynamic_sections:
            content = section.resolve()
            if content:
                dynamic_parts.append(content)
        for section in self._tool_sections.values():
            content = section.resolve()
            if content:
                dynamic_parts.append(content)

        return (
            "\n\n---\n\n".join(static_parts),
            "\n\n---\n\n".join(dynamic_parts),
        )

    def invalidate_all(self):
        """Clear all caches (e.g., on /clear or session restart)."""
        for section in self._static_sections:
            section.invalidate()

    def invalidate_section(self, name: str):
        """Clear cache for a specific section."""
        for section in self._static_sections + self._dynamic_sections:
            if section.name == name:
                section.invalidate()
                return

    @property
    def section_names(self) -> list[str]:
        """List all section names."""
        names = [s.name for s in self._static_sections]
        names.extend(s.name for s in self._dynamic_sections)
        names.extend(f"tool:{k}" for k in self._tool_sections)
        return names

    @property
    def static_section_count(self) -> int:
        return len(self._static_sections)

    @property
    def dynamic_section_count(self) -> int:
        return len(self._dynamic_sections) + len(self._tool_sections)

    def estimate_tokens(self) -> dict:
        """Estimate tokens per section for context analysis."""
        result = {}
        for section in self._static_sections + self._dynamic_sections:
            content = section.resolve()
            result[section.name] = len(content) // 4
        for name, section in self._tool_sections.items():
            content = section.resolve()
            result[f"tool:{name}"] = len(content) // 4
        return result
