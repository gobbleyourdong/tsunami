"""Unit tests for scripts/asset/extract_alpha_unmix.py's pure math.

All tests exercise unmix_magenta() directly on synthetic numpy arrays —
no Qwen, no server, no PIL disk I/O. Confirms the classical
un-premultiplication closed-form: P = α·F + (1-α)·M.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest


_REPO = Path(__file__).resolve().parent.parent.parent
_SCRIPT = _REPO / "scripts" / "asset" / "extract_alpha_unmix.py"


def _load_unmix_module():
    spec = importlib.util.spec_from_file_location("extract_alpha_unmix", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["extract_alpha_unmix"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def unmix():
    return _load_unmix_module()


def _single_pixel(r: int, g: int, b: int) -> np.ndarray:
    return np.array([[[r, g, b]]], dtype=np.uint8)


def test_pure_magenta_is_fully_transparent(unmix):
    out = unmix.unmix_magenta(_single_pixel(255, 0, 255))
    assert out[0, 0, 3] == 0, "pure magenta must map to α=0"


def test_pure_green_is_fully_opaque(unmix):
    out = unmix.unmix_magenta(_single_pixel(0, 255, 0))
    assert out[0, 0, 3] == 255
    # FG color preserves green
    assert tuple(out[0, 0, :3]) == (0, 255, 0)


def test_pure_white_is_fully_opaque(unmix):
    out = unmix.unmix_magenta(_single_pixel(255, 255, 255))
    assert out[0, 0, 3] == 255
    assert tuple(out[0, 0, :3]) == (255, 255, 255)


def test_pure_black_is_fully_opaque(unmix):
    """(0,0,0) has no magenta contribution — α should be 1, F=black."""
    out = unmix.unmix_magenta(_single_pixel(0, 0, 0))
    assert out[0, 0, 3] == 255
    assert tuple(out[0, 0, :3]) == (0, 0, 0)


def test_half_blue_over_magenta(unmix):
    """50% blue subject over magenta: P = 0.5·(0,0,255) + 0.5·(255,0,255) = (128, 0, 255).
    Un-premix should recover α≈0.5 and F≈blue."""
    # P = (128, 0, 255) is roughly 50/50 blue + magenta
    out = unmix.unmix_magenta(_single_pixel(128, 0, 255))
    alpha = out[0, 0, 3]
    # min(R, B) = 128, G = 0, → magenta_rb - G = 128/255 = 0.502 → α ≈ 0.498 * 255 ≈ 127
    assert 120 <= alpha <= 135, f"expected α≈127 for 50% blue, got {alpha}"
    # Un-premultiply: F.r = (128 - (1-α)·255) / α ≈ 0, F.b = (255 - (1-α)·255) / α ≈ 255
    fr, fg, fb = out[0, 0, :3]
    assert fr < 15, f"expected F.r≈0 (subject is blue), got {fr}"
    assert fg < 15, f"expected F.g≈0, got {fg}"
    assert fb > 240, f"expected F.b≈255, got {fb}"


def test_half_gray_over_magenta(unmix):
    """50% mid-gray subject + magenta: P = 0.5·(128,128,128) + 0.5·(255,0,255)
      = (191, 64, 191).
    Should give α ≈ 0.5 with F ≈ gray."""
    out = unmix.unmix_magenta(_single_pixel(191, 64, 191))
    alpha = out[0, 0, 3]
    # magenta_rb = 191/255 = 0.749, G = 64/255 = 0.251 → α = 1 - (0.749 - 0.251) = 0.502
    assert 120 <= alpha <= 135, f"expected α≈127, got {alpha}"
    # F should be ~(128, 128, 128)
    fr, fg, fb = out[0, 0, :3]
    for c, name in [(fr, "R"), (fg, "G"), (fb, "B")]:
        assert 100 <= c <= 160, f"expected F.{name}≈128, got {c}"


def test_output_shape_and_dtype(unmix):
    rgb = np.zeros((4, 7, 3), dtype=np.uint8)
    out = unmix.unmix_magenta(rgb)
    assert out.shape == (4, 7, 4), "must be HxWx4"
    assert out.dtype == np.uint8, "must preserve uint8"


def test_accepts_rgba_input(unmix):
    """Passing in RGBA should work (incoming alpha is ignored; we compute fresh)."""
    rgba = np.zeros((2, 2, 4), dtype=np.uint8)
    rgba[..., :] = [255, 0, 255, 255]  # pure magenta, even with α=255 input
    out = unmix.unmix_magenta(rgba)
    assert out.shape == (2, 2, 4)
    # Output alpha should be 0 (pure magenta) regardless of input alpha
    assert np.all(out[..., 3] == 0)


def test_rejects_wrong_channels(unmix):
    with pytest.raises(ValueError):
        unmix.unmix_magenta(np.zeros((2, 2, 5), dtype=np.uint8))
    with pytest.raises(ValueError):
        unmix.unmix_magenta(np.zeros((2, 2), dtype=np.uint8))


def test_vectorizes_across_frame(unmix):
    """Random 32x32 RGB should process without error and stay in [0, 255]."""
    rng = np.random.default_rng(42)
    rgb = rng.integers(0, 256, (32, 32, 3), dtype=np.uint8)
    out = unmix.unmix_magenta(rgb)
    assert out.shape == (32, 32, 4)
    assert out.min() >= 0
    assert out.max() <= 255
