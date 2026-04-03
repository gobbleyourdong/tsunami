"""Screenshot diffing — visual change detection between iterations.

Before an iteration: capture current state as a screenshot.
After an iteration: capture new state, pixel-diff against before.
If < 5% changed and user asked for changes, warn "changes may not be visible."

Uses Playwright for browser screenshot capture. Falls back gracefully
when Playwright is not installed.

Storage: workspace/.screenshots/<timestamp>_before.png, _after.png, _diff.png
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

log = logging.getLogger("tsunami.screenshot_diff")


def is_playwright_available() -> bool:
    """Check if Playwright is installed and usable."""
    try:
        from playwright.sync_api import sync_playwright
        return True
    except ImportError:
        return False


async def capture_screenshot(
    url: str,
    output_path: str,
    width: int = 1280,
    height: int = 720,
    wait_ms: int = 2000,
) -> bool:
    """Capture a screenshot of a URL using Playwright.

    Returns True if screenshot was captured, False on failure.
    """
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(viewport={"width": width, "height": height})
            await page.goto(url, wait_until="networkidle", timeout=10000)
            await page.wait_for_timeout(wait_ms)
            await page.screenshot(path=output_path, full_page=False)
            await browser.close()

        log.info(f"Screenshot saved: {output_path}")
        return True
    except Exception as e:
        log.warning(f"Screenshot failed: {e}")
        return False


def pixel_diff(image_a_path: str, image_b_path: str, diff_output_path: str = "") -> dict:
    """Compare two screenshots pixel-by-pixel.

    Returns {
        percent_changed: float (0-100),
        total_pixels: int,
        changed_pixels: int,
        diff_path: str (if diff_output_path provided),
    }

    Uses PIL if available, falls back to a byte-level comparison.
    """
    try:
        from PIL import Image
        import numpy as np

        img_a = np.array(Image.open(image_a_path).convert("RGB"))
        img_b = np.array(Image.open(image_b_path).convert("RGB"))

        # Resize if different dimensions
        if img_a.shape != img_b.shape:
            min_h = min(img_a.shape[0], img_b.shape[0])
            min_w = min(img_a.shape[1], img_b.shape[1])
            img_a = img_a[:min_h, :min_w]
            img_b = img_b[:min_h, :min_w]

        # Per-pixel difference (threshold to ignore anti-aliasing noise)
        diff = np.abs(img_a.astype(int) - img_b.astype(int))
        pixel_changed = np.any(diff > 20, axis=2)  # 20 = noise threshold
        changed_count = int(np.sum(pixel_changed))
        total = pixel_changed.size

        # Save diff image if requested
        if diff_output_path:
            diff_img = np.zeros_like(img_a)
            diff_img[pixel_changed] = [255, 0, 0]  # red for changed
            diff_img[~pixel_changed] = img_b[~pixel_changed] // 3  # dim unchanged
            Image.fromarray(diff_img.astype(np.uint8)).save(diff_output_path)

        return {
            "percent_changed": round((changed_count / total) * 100, 2) if total > 0 else 0,
            "total_pixels": total,
            "changed_pixels": changed_count,
            "diff_path": diff_output_path,
        }
    except ImportError:
        return _byte_level_diff(image_a_path, image_b_path)


def _byte_level_diff(path_a: str, path_b: str) -> dict:
    """Fallback: compare file bytes when PIL/numpy not available."""
    try:
        bytes_a = open(path_a, "rb").read()
        bytes_b = open(path_b, "rb").read()
        if bytes_a == bytes_b:
            return {"percent_changed": 0.0, "total_pixels": 0, "changed_pixels": 0, "diff_path": ""}
        # Rough estimate from byte difference
        min_len = min(len(bytes_a), len(bytes_b))
        diff_count = sum(1 for a, b in zip(bytes_a[:min_len], bytes_b[:min_len]) if a != b)
        pct = (diff_count / min_len) * 100 if min_len > 0 else 100
        return {"percent_changed": round(pct, 2), "total_pixels": 0, "changed_pixels": diff_count, "diff_path": ""}
    except Exception:
        return {"percent_changed": -1, "total_pixels": 0, "changed_pixels": 0, "diff_path": ""}


class ScreenshotTracker:
    """Track before/after screenshots across iterations."""

    def __init__(self, workspace_dir: str | Path):
        self.workspace = Path(workspace_dir)
        self.screenshots_dir = self.workspace / ".screenshots"
        self._before_path: str | None = None
        self._iteration: int = 0

    def _ensure_dir(self):
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)

    async def capture_before(self, url: str, iteration: int) -> str | None:
        """Capture the 'before' screenshot."""
        if not is_playwright_available():
            return None
        self._ensure_dir()
        self._iteration = iteration
        ts = int(time.time())
        path = str(self.screenshots_dir / f"{ts}_iter{iteration}_before.png")
        ok = await capture_screenshot(url, path)
        if ok:
            self._before_path = path
            return path
        return None

    async def capture_after(self, url: str) -> dict | None:
        """Capture the 'after' screenshot and compute diff.

        Returns the diff result dict, or None if no before screenshot.
        """
        if not self._before_path or not is_playwright_available():
            return None
        self._ensure_dir()
        ts = int(time.time())
        after_path = str(self.screenshots_dir / f"{ts}_iter{self._iteration}_after.png")
        diff_path = str(self.screenshots_dir / f"{ts}_iter{self._iteration}_diff.png")

        ok = await capture_screenshot(url, after_path)
        if not ok:
            return None

        result = pixel_diff(self._before_path, after_path, diff_path)
        result["before_path"] = self._before_path
        result["after_path"] = after_path

        # Warn if changes are minimal
        if result["percent_changed"] < 5 and result["percent_changed"] >= 0:
            result["warning"] = "Changes may not be visible (< 5% pixel difference)"
            log.warning(f"Screenshot diff: only {result['percent_changed']}% changed")

        self._before_path = None  # reset for next iteration
        return result

    def get_recent_screenshots(self, n: int = 10) -> list[str]:
        """Get paths of the N most recent screenshots."""
        if not self.screenshots_dir.exists():
            return []
        files = sorted(self.screenshots_dir.glob("*.png"), key=os.path.getmtime, reverse=True)
        return [str(f) for f in files[:n]]
