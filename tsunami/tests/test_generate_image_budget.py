"""Budget-hint on GenerateImage's tool-response path.

The drone's most reliable feedback channel is the tool result text it sees
immediately after each call. Phase-machine nudges and agent.py image-ceiling
nudges are additional system-notes, but the drone can miss them if it's
already decoding its next message. The budget hint rides on the result
itself so the drone reads it before producing the next tool call.

Rules under test:
  - First 2 images: no hint (no count mention in the baseline result)
  - 3rd image: "[budget: 3 images..." hint appended
  - 4th image: no hint at 4 (budget not yet exceeded)
  - 5th image and beyond: "[budget exceeded..." hint
"""

import asyncio
from unittest.mock import patch

import pytest

from tsunami.tools.generate import GenerateImage
from tsunami.tools.base import ToolResult


def _mk_tool() -> GenerateImage:
    """Construct a GenerateImage without going through the config-driven path."""
    return GenerateImage.__new__(GenerateImage)


async def _fake_backend_ok(self, prompt, path, w, h, style):
    # Write a tiny PNG so _extract_alpha / sprite-downscale / existence
    # checks pass. We avoid the alpha branch by using mode="opaque" in
    # the caller below.
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x89PNG\r\n\x1a\n")  # PNG header sentinel; no real image decode needed.
    return ToolResult(f"Image generated and saved to {path} (ERNIE-Image-Turbo {w}x{h}, 8 steps)")


async def _run_n(tool: GenerateImage, n: int, tmp_path) -> list[ToolResult]:
    """Call execute() N times with mode='opaque' so we skip alpha extraction
    (which requires PIL + real image bytes)."""
    results = []
    for i in range(n):
        save = str(tmp_path / f"img_{i}.png")
        with patch.object(GenerateImage, "_try_ernie_server", _fake_backend_ok):
            r = await tool.execute(
                prompt="a cat",
                save_path=save,
                width=1024,
                height=1024,
                style="photo",
                mode="opaque",
            )
        results.append(r)
    return results


class TestBudgetHint:
    def test_first_two_have_no_hint(self, tmp_path):
        tool = _mk_tool()
        results = asyncio.run(_run_n(tool, 2, tmp_path))
        for r in results:
            assert "[budget" not in r.content
            assert "[budget exceeded" not in r.content

    def test_third_image_gets_core_set_hint(self, tmp_path):
        tool = _mk_tool()
        results = asyncio.run(_run_n(tool, 3, tmp_path))
        assert "[budget: 3 images" in results[-1].content
        assert "core set" in results[-1].content
        assert "file_write" in results[-1].content
        # Earlier results still clean.
        assert "[budget" not in results[0].content
        assert "[budget" not in results[1].content

    def test_fourth_image_is_quiet_again(self, tmp_path):
        """Only 3 and 5+ speak; 4 is silent — avoid nagging on every call."""
        tool = _mk_tool()
        results = asyncio.run(_run_n(tool, 4, tmp_path))
        assert "[budget" not in results[3].content

    def test_fifth_image_triggers_exceeded(self, tmp_path):
        tool = _mk_tool()
        results = asyncio.run(_run_n(tool, 5, tmp_path))
        assert "[budget exceeded" in results[-1].content
        assert "STOP" in results[-1].content
        assert "broken" in results[-1].content.lower() or "missing" in results[-1].content.lower()

    def test_subsequent_images_keep_firing_exceeded(self, tmp_path):
        """Beyond 5 the hint keeps repeating — drone has repeatedly ignored it."""
        tool = _mk_tool()
        results = asyncio.run(_run_n(tool, 7, tmp_path))
        for r in results[4:]:  # indexes 4, 5, 6 — counts 5, 6, 7
            assert "[budget exceeded" in r.content

    def test_counter_persists_on_the_instance(self, tmp_path):
        """The budget tracker is instance state (registry reuses the tool)."""
        tool = _mk_tool()
        asyncio.run(_run_n(tool, 3, tmp_path))
        assert tool._call_count == 3
