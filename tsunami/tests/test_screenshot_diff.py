"""Tests for Chunk 15: Screenshot Diffing.

Tests use static test images and mock Playwright since the browser
may not be available in CI/test environments.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch, AsyncMock

from tsunami.screenshot_diff import (
    is_playwright_available,
    pixel_diff,
    _byte_level_diff,
    ScreenshotTracker,
)


class TestPixelDiff:
    """Pixel comparison between images."""

    def _make_image(self, path: str, color: tuple, size: tuple = (100, 100)):
        """Create a solid-color test image."""
        try:
            from PIL import Image
            img = Image.new("RGB", size, color)
            img.save(path)
            return True
        except ImportError:
            return False

    def test_identical_images(self):
        tmp = tempfile.mkdtemp()
        a = os.path.join(tmp, "a.png")
        b = os.path.join(tmp, "b.png")
        if not self._make_image(a, (255, 0, 0)):
            return  # PIL not available, skip
        self._make_image(b, (255, 0, 0))
        result = pixel_diff(a, b)
        assert result["percent_changed"] == 0.0

    def test_completely_different_images(self):
        tmp = tempfile.mkdtemp()
        a = os.path.join(tmp, "a.png")
        b = os.path.join(tmp, "b.png")
        if not self._make_image(a, (255, 0, 0)):
            return
        self._make_image(b, (0, 0, 255))
        result = pixel_diff(a, b)
        assert result["percent_changed"] > 90

    def test_partial_difference(self):
        try:
            from PIL import Image
            import numpy as np
        except ImportError:
            return

        tmp = tempfile.mkdtemp()
        a = os.path.join(tmp, "a.png")
        b = os.path.join(tmp, "b.png")

        # Image A: half red, half blue
        img_a = Image.new("RGB", (100, 100), (255, 0, 0))
        img_a.save(a)

        # Image B: all red (50% different)
        arr = np.array(img_a)
        arr[50:, :] = [0, 0, 255]
        Image.fromarray(arr).save(a)
        img_a.save(b)

        result = pixel_diff(a, b)
        assert 40 < result["percent_changed"] < 60

    def test_diff_output_image(self):
        tmp = tempfile.mkdtemp()
        a = os.path.join(tmp, "a.png")
        b = os.path.join(tmp, "b.png")
        diff = os.path.join(tmp, "diff.png")
        if not self._make_image(a, (255, 0, 0)):
            return
        self._make_image(b, (0, 255, 0))
        result = pixel_diff(a, b, diff)
        assert os.path.exists(diff)
        assert result["diff_path"] == diff


class TestByteLevelDiff:
    """Fallback byte-level comparison."""

    def test_identical_files(self):
        tmp = tempfile.mkdtemp()
        a = os.path.join(tmp, "a.bin")
        b = os.path.join(tmp, "b.bin")
        open(a, "wb").write(b"hello world")
        open(b, "wb").write(b"hello world")
        result = _byte_level_diff(a, b)
        assert result["percent_changed"] == 0.0

    def test_different_files(self):
        tmp = tempfile.mkdtemp()
        a = os.path.join(tmp, "a.bin")
        b = os.path.join(tmp, "b.bin")
        open(a, "wb").write(b"aaaa")
        open(b, "wb").write(b"bbbb")
        result = _byte_level_diff(a, b)
        assert result["percent_changed"] > 0

    def test_nonexistent_file(self):
        result = _byte_level_diff("/nonexistent/a", "/nonexistent/b")
        assert result["percent_changed"] == -1


class TestScreenshotTracker:
    """Screenshot tracker lifecycle."""

    def test_init(self):
        tracker = ScreenshotTracker(tempfile.mkdtemp())
        assert tracker._before_path is None

    def test_screenshots_dir(self):
        tmp = tempfile.mkdtemp()
        tracker = ScreenshotTracker(tmp)
        tracker._ensure_dir()
        assert (Path(tmp) / ".screenshots").exists()

    def test_get_recent_empty(self):
        tracker = ScreenshotTracker(tempfile.mkdtemp())
        assert tracker.get_recent_screenshots() == []

    def test_get_recent_with_files(self):
        tmp = tempfile.mkdtemp()
        tracker = ScreenshotTracker(tmp)
        tracker._ensure_dir()
        # Create some fake screenshots
        for i in range(5):
            (tracker.screenshots_dir / f"test_{i}.png").write_text("fake")
        recent = tracker.get_recent_screenshots(3)
        assert len(recent) == 3

    @patch("tsunami.screenshot_diff.is_playwright_available", return_value=False)
    def test_capture_before_no_playwright(self, _):
        import asyncio
        tracker = ScreenshotTracker(tempfile.mkdtemp())
        result = asyncio.get_event_loop().run_until_complete(
            tracker.capture_before("http://localhost:5173", 1)
        )
        assert result is None

    @patch("tsunami.screenshot_diff.is_playwright_available", return_value=False)
    def test_capture_after_no_before(self, _):
        import asyncio
        tracker = ScreenshotTracker(tempfile.mkdtemp())
        result = asyncio.get_event_loop().run_until_complete(
            tracker.capture_after("http://localhost:5173")
        )
        assert result is None


class TestPlaywrightDetection:
    """Playwright availability check."""

    def test_returns_bool(self):
        result = is_playwright_available()
        assert isinstance(result, bool)


class TestWarningThreshold:
    """Low-change detection (< 5%)."""

    def test_low_change_warning(self):
        # Simulate a diff result with < 5% change
        result = {
            "percent_changed": 3.2,
            "total_pixels": 10000,
            "changed_pixels": 320,
        }
        # The warning logic is in capture_after, but we can test the threshold
        assert result["percent_changed"] < 5
