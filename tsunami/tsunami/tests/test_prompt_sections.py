"""Tests for composable prompt sections with lazy caching."""

import pytest

from tsunami.prompt_sections import PromptBuilder, PromptSection, DYNAMIC_BOUNDARY


class TestPromptSection:
    """Individual section caching."""

    def test_cacheable_computes_once(self):
        call_count = 0
        def compute():
            nonlocal call_count
            call_count += 1
            return "static content"

        section = PromptSection(name="test", compute=compute, cacheable=True)
        section.resolve()
        section.resolve()
        section.resolve()
        assert call_count == 1

    def test_non_cacheable_recomputes(self):
        call_count = 0
        def compute():
            nonlocal call_count
            call_count += 1
            return f"dynamic {call_count}"

        section = PromptSection(name="test", compute=compute, cacheable=False)
        r1 = section.resolve()
        r2 = section.resolve()
        assert r1 != r2
        assert call_count == 2

    def test_invalidate_clears_cache(self):
        call_count = 0
        def compute():
            nonlocal call_count
            call_count += 1
            return "content"

        section = PromptSection(name="test", compute=compute, cacheable=True)
        section.resolve()
        section.invalidate()
        section.resolve()
        assert call_count == 2

    def test_force_recompute(self):
        call_count = 0
        def compute():
            nonlocal call_count
            call_count += 1
            return "content"

        section = PromptSection(name="test", compute=compute, cacheable=True)
        section.resolve()
        section.resolve(force=True)
        assert call_count == 2


class TestPromptBuilder:
    """Full prompt assembly."""

    def test_static_and_dynamic(self):
        builder = PromptBuilder()
        builder.add_static("identity", lambda: "I am Tsunami")
        builder.add_dynamic("env", lambda: "Linux x86_64")
        prompt = builder.resolve()
        assert "Tsunami" in prompt
        assert "Linux" in prompt

    def test_static_cached_dynamic_recomputed(self):
        static_count = 0
        dynamic_count = 0

        def static_fn():
            nonlocal static_count
            static_count += 1
            return "static"

        def dynamic_fn():
            nonlocal dynamic_count
            dynamic_count += 1
            return "dynamic"

        builder = PromptBuilder()
        builder.add_static("s", static_fn)
        builder.add_dynamic("d", dynamic_fn)

        builder.resolve()
        builder.resolve()
        builder.resolve()

        assert static_count == 1  # cached
        assert dynamic_count == 3  # recomputed each time

    def test_tool_section_injection(self):
        builder = PromptBuilder()
        builder.add_static("base", lambda: "base prompt")
        builder.inject_tool_section("shell_exec", lambda: "Shell: use bash")
        prompt = builder.resolve()
        assert "base prompt" in prompt
        assert "Shell: use bash" in prompt

    def test_tool_section_removal(self):
        builder = PromptBuilder()
        builder.inject_tool_section("test", lambda: "tool context")
        assert "tool context" in builder.resolve()
        builder.remove_tool_section("test")
        assert "tool context" not in builder.resolve()

    def test_resolve_split(self):
        builder = PromptBuilder()
        builder.add_static("identity", lambda: "I am Tsunami")
        builder.add_dynamic("env", lambda: "Linux")
        static, dynamic = builder.resolve_split()
        assert "Tsunami" in static
        assert "Linux" in dynamic
        assert "Linux" not in static
        assert "Tsunami" not in dynamic

    def test_invalidate_all(self):
        count = 0
        def fn():
            nonlocal count
            count += 1
            return "x"

        builder = PromptBuilder()
        builder.add_static("s", fn)
        builder.resolve()
        builder.invalidate_all()
        builder.resolve()
        assert count == 2

    def test_section_names(self):
        builder = PromptBuilder()
        builder.add_static("identity", lambda: "")
        builder.add_dynamic("env", lambda: "")
        builder.inject_tool_section("bash", lambda: "")
        names = builder.section_names
        assert "identity" in names
        assert "env" in names
        assert "tool:bash" in names

    def test_estimate_tokens(self):
        builder = PromptBuilder()
        builder.add_static("big", lambda: "x" * 400)  # ~100 tokens
        builder.add_static("small", lambda: "y" * 40)  # ~10 tokens
        tokens = builder.estimate_tokens()
        assert tokens["big"] > tokens["small"]

    def test_empty_sections_skipped(self):
        builder = PromptBuilder()
        builder.add_static("empty", lambda: "")
        builder.add_static("full", lambda: "content")
        prompt = builder.resolve()
        assert prompt == "content"  # empty section not included

    def test_section_counts(self):
        builder = PromptBuilder()
        builder.add_static("a", lambda: "")
        builder.add_static("b", lambda: "")
        builder.add_dynamic("c", lambda: "")
        builder.inject_tool_section("d", lambda: "")
        assert builder.static_section_count == 2
        assert builder.dynamic_section_count == 2  # 1 dynamic + 1 tool
