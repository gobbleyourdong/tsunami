"""Undertow VLM-describe wiring — source-invariant checks.

The screenshot lever feeds its output to the eddy comparator for a
semantic PASS/FAIL judgment. Pixel-stat summaries ("171 unique colors,
avg brightness 18/255") never match content-level expectations ("note-
taking app with textarea"), so the screenshot lever must pass the image
to a multimodal model for a content description first. Gemma-4 on :8090
is multimodal — _vlm_describe_screenshot() uses it.

No live inference here — covering wiring. Live smoke tests sit in
/tmp/undertow_smoke.py during manual validation.
"""

from __future__ import annotations

from pathlib import Path


def test_vlm_describe_function_exists():
    """The async helper is defined and importable."""
    from tsunami import undertow
    assert callable(undertow._vlm_describe_screenshot)


def test_screenshot_lever_uses_vlm_before_eddy_compare():
    """Source-invariant: _lever_screenshot must call _vlm_describe_screenshot
    and prefer its output for _eddy_compare — NOT the pixel-stat pixel_desc."""
    src = (Path(__file__).resolve().parent.parent / "undertow.py").read_text()
    # The fn must call _vlm_describe_screenshot
    assert "_vlm_describe_screenshot(screenshot_bytes)" in src
    # And compose desc = vlm_desc or pixel_desc
    assert "vlm_desc or pixel_desc" in src or "vlm_desc if vlm_desc else pixel_desc" in src


def test_vlm_request_uses_image_url_content_format():
    """VLM call uses OpenAI-style `{type:'image_url', image_url:{url:'data:image/png;base64,...'}}` format."""
    src = (Path(__file__).resolve().parent.parent / "undertow.py").read_text()
    assert "image_url" in src
    assert "data:image/png;base64," in src
    # Adapter must be "none" so the describe doesn't run through a specialized LoRA
    assert '"adapter": "none"' in src or "'adapter': 'none'" in src


def test_vlm_has_generous_timeout():
    """Under QA load the gpu_sem queue can delay multimodal calls 2-3 min.
    Timeout must be ≥120s so we wait through the queue instead of failing
    back to pixel stats (which then fail the semantic compare)."""
    src = (Path(__file__).resolve().parent.parent / "undertow.py").read_text()
    assert "timeout=120" in src or "timeout=180" in src


def test_eddy_compare_unchanged():
    """_eddy_compare signature + return contract untouched — still returns
    'PASS: ...' / 'FAIL: ...' / 'UNCLEAR: eddy unavailable'."""
    src = (Path(__file__).resolve().parent.parent / "undertow.py").read_text()
    assert "UNCLEAR: eddy unavailable" in src
    assert "async def _eddy_compare" in src
