"""Tests for webdev tool helpers."""

from tsunami.tools.webdev import normalize_screenshot_output_path


def test_normalize_screenshot_output_path_keeps_image_suffix():
    path, note = normalize_screenshot_output_path("shots/homepage.png")
    assert path == "shots/homepage.png"
    assert note is None


def test_normalize_screenshot_output_path_rewrites_markdown_suffix():
    path, note = normalize_screenshot_output_path("screenshot.md")
    assert path == "screenshot.png"
    assert note is not None
    assert "Adjusted screenshot output path" in note


def test_normalize_screenshot_output_path_adds_png_when_missing():
    path, note = normalize_screenshot_output_path("shots/homepage")
    assert path == "shots/homepage.png"
    assert note is not None
