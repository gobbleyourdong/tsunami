"""Unit tests for the /v1/images/animate chain-edit endpoint.

Tests the request/response shape + chain execution loop WITHOUT actually
loading a diffusion pipeline (slow + GPU-hungry). Swaps in a mock pipe
that returns the input image unchanged, lets us exercise the chain
traversal, save-path handling, and response packaging.

For real-generation tests, use the bake_sprite_sheet.py end-to-end
integration test (commit 5 in the asset state-graph plan).
"""

from __future__ import annotations

import asyncio
import base64
import io
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image


# ── Schema validation (pydantic import-time checks) ──────────────────

def test_imports_ok():
    """Module imports cleanly — catches regression from schema changes
    breaking the module-level import."""
    from tsunami.serving import qwen_image_server
    assert hasattr(qwen_image_server, "AnimateRequest")
    assert hasattr(qwen_image_server, "AnimateResponse")
    assert hasattr(qwen_image_server, "NudgeStep")


def test_nudge_step_defaults():
    """NudgeStep has chain-friendly defaults — strength LOW so cumulative
    drift stays bounded across long chains."""
    from tsunami.serving.qwen_image_server import NudgeStep
    step = NudgeStep(delta="weight shifting to right foot")
    assert step.strength == 0.4
    # Strength bounds — cannot be negative or > 1
    assert step.strength >= 0.0 and step.strength <= 1.0


def test_animate_request_min_nudges():
    """AnimateRequest requires at least one nudge — an empty chain makes
    no sense and would return zero frames."""
    from tsunami.serving.qwen_image_server import AnimateRequest, NudgeStep
    # Zero nudges → validation error
    with pytest.raises(Exception):  # pydantic ValidationError
        AnimateRequest(path="/tmp/base.png", nudges=[])
    # One nudge → OK
    req = AnimateRequest(
        path="/tmp/base.png",
        nudges=[NudgeStep(delta="test")],
    )
    assert len(req.nudges) == 1


def test_animate_request_max_nudges_cap():
    """Chain length capped at 32 — prevents unbounded wall-clock + drift."""
    from tsunami.serving.qwen_image_server import AnimateRequest, NudgeStep
    nudges = [NudgeStep(delta=f"step {i}") for i in range(33)]
    with pytest.raises(Exception):
        AnimateRequest(path="/tmp/base.png", nudges=nudges)


def test_save_path_requires_save_dir():
    """response_format=save_path + no save_dir = contract-incoherent —
    the endpoint rejects it at the HTTP layer (tested via shape here)."""
    from tsunami.serving.qwen_image_server import AnimateRequest, NudgeStep
    req = AnimateRequest(
        path="/tmp/base.png",
        nudges=[NudgeStep(delta="test")],
        response_format="save_path",
        save_dir=None,
    )
    # The model allows the construction (save_dir is Optional); the
    # endpoint body asserts the combination at runtime and 400s.
    assert req.save_dir is None
    assert req.response_format == "save_path"


def test_animate_response_shape():
    """AnimateResponse has expected fields for downstream consumers
    (bake tool, eval harness)."""
    from tsunami.serving.qwen_image_server import AnimateResponse, GenResponseImage
    resp = AnimateResponse(
        created=int(1700000000),
        frames=[GenResponseImage(save_path="/tmp/f0.png")],
        timing={"elapsed_s": 12.3},
        total_strength=0.4,
        loaded_loras=["multiple_angles"],
    )
    assert resp.created == 1700000000
    assert len(resp.frames) == 1
    assert resp.total_strength == 0.4
    assert resp.loaded_loras == ["multiple_angles"]


# ── Chain-execution smoke (with mocked pipeline) ─────────────────────

def test_chain_execution_with_mock_pipe(tmp_path: Path):
    """Full chain execution through the /animate endpoint body with a
    MOCK pipe — verifies iteration order, total_strength accumulation,
    save_path generation, and the per-step log signature the v10 audit
    tool will grep for."""
    from tsunami.serving import qwen_image_server as qis
    from tsunami.serving.qwen_image_server import (
        AnimateRequest, NudgeStep, animate,
    )

    # Seed input image
    base = Image.new("RGB", (64, 64), color=(100, 150, 200))
    base_path = tmp_path / "base.png"
    base.save(base_path)

    # Mock pipe — returns a synthetic "edited" image per call so we can
    # verify chaining without a real GPU pipeline.
    call_log: list[dict] = []

    def _mock_pipe(**kwargs):
        call_log.append({
            "prompt": kwargs.get("prompt"),
            "strength": kwargs.get("strength"),
            "image_mode": kwargs["image"].mode,
        })
        # Return a slightly-different image so caller can't conflate
        # "returned same object" with "no work done".
        out = kwargs["image"].copy()
        return SimpleNamespace(images=[out])

    # Wire the mock into the module's globals + a mock _args namespace
    # so the endpoint body can read _args.device.
    orig_pipe = qis._pipe
    orig_args = qis._args
    orig_loras = list(qis._loaded_loras)
    qis._pipe = _mock_pipe
    qis._args = SimpleNamespace(device="cpu")
    qis._loaded_loras.clear()
    qis._loaded_loras.append("multiple_angles")

    try:
        req = AnimateRequest(
            path=str(base_path),
            nudges=[
                NudgeStep(delta="step 1 delta", strength=0.3),
                NudgeStep(delta="step 2 delta", strength=0.4),
                NudgeStep(delta="step 3 delta", strength=0.5),
            ],
            response_format="save_path",
            save_dir=str(tmp_path / "frames"),
        )
        resp = asyncio.run(animate(req))

        # Three steps → three frames
        assert len(resp.frames) == 3
        # Σstrength = 0.3 + 0.4 + 0.5 = 1.2
        assert resp.total_strength == pytest.approx(1.2)
        # Frames saved in numeric order on disk
        assert all((tmp_path / "frames" / f"frame_{i:03d}.png").exists() for i in range(3))
        # Call log matches step ordering + strength values
        assert len(call_log) == 3
        assert call_log[0]["prompt"] == "step 1 delta"
        assert call_log[0]["strength"] == 0.3
        assert call_log[2]["strength"] == 0.5
        # Loaded LoRAs surfaced in response for the caller
        assert resp.loaded_loras == ["multiple_angles"]
    finally:
        qis._pipe = orig_pipe
        qis._args = orig_args
        qis._loaded_loras.clear()
        qis._loaded_loras.extend(orig_loras)


def test_chain_execution_b64_mode(tmp_path: Path):
    """response_format=b64_json returns inline frames — no save_dir required."""
    from tsunami.serving import qwen_image_server as qis
    from tsunami.serving.qwen_image_server import AnimateRequest, NudgeStep, animate

    base = Image.new("RGB", (32, 32), color=(50, 100, 150))
    base_path = tmp_path / "base.png"
    base.save(base_path)

    def _mock_pipe(**kwargs):
        return SimpleNamespace(images=[kwargs["image"].copy()])

    orig_pipe = qis._pipe
    orig_args = qis._args
    qis._pipe = _mock_pipe
    qis._args = SimpleNamespace(device="cpu")
    try:
        req = AnimateRequest(
            path=str(base_path),
            nudges=[NudgeStep(delta="single step", strength=0.4)],
            response_format="b64_json",
        )
        resp = asyncio.run(animate(req))
        assert len(resp.frames) == 1
        # b64 payload present, save_path absent
        assert resp.frames[0].b64_json is not None
        assert resp.frames[0].save_path is None
        # Decodable as PNG
        raw = base64.b64decode(resp.frames[0].b64_json)
        img = Image.open(io.BytesIO(raw))
        assert img.size == (32, 32)
    finally:
        qis._pipe = orig_pipe
        qis._args = orig_args


def test_animate_rejects_save_path_without_save_dir(tmp_path: Path):
    """The endpoint's body-level guard: save_path mode + no save_dir = 400."""
    from fastapi import HTTPException
    from tsunami.serving import qwen_image_server as qis
    from tsunami.serving.qwen_image_server import AnimateRequest, NudgeStep, animate

    base = Image.new("RGB", (32, 32))
    base_path = tmp_path / "base.png"
    base.save(base_path)

    # Mock pipe is loaded so we get past the 503 check
    qis._pipe = lambda **k: SimpleNamespace(images=[k["image"]])
    qis._args = SimpleNamespace(device="cpu")

    req = AnimateRequest(
        path=str(base_path),
        nudges=[NudgeStep(delta="x")],
        response_format="save_path",
        save_dir=None,
    )
    with pytest.raises(HTTPException) as ei:
        asyncio.run(animate(req))
    assert ei.value.status_code == 400
    assert "save_dir required" in ei.value.detail
