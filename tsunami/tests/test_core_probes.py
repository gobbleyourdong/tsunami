"""Tests for tsunami.core.* delivery-gate probes.

Covers the probes that can run without a node/electron/chrome install:
  - extension_probe (static file check)
  - sse_probe (self-contained stub server + consumer)
  - _probe_common helpers (free_port, result, skip)

Spawn-based probes (server, openapi, ws, electron) are verified
manually against a node stub because each needs a running node
process which CI may not guarantee.

Convention: test functions are sync and invoke `asyncio.run()` on a
local coroutine — matches `test_agent_loop.py` and friends. No
pytest-asyncio dependency.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from tsunami.core import _probe_common as pc
from tsunami.core.extension_probe import extension_probe
from tsunami.core.sse_probe import sse_probe, DEFAULT_TOKENS


# ─────────────────────── probe_common helpers ──────────────────────

def test_result_shape():
    r = pc.result(True, "x", "y")
    assert r == {"passed": True, "issues": "x", "raw": "y"}


def test_skip_is_passed():
    r = pc.skip("no tool")
    assert r["passed"] is True
    assert "no tool" in r["raw"]


def test_free_port_in_range():
    p = pc.free_port()
    assert 1024 <= p <= 65535


# ─────────────────────── extension_probe ───────────────────────────

def _write_manifest(dist: Path, manifest: dict) -> None:
    dist.mkdir(parents=True, exist_ok=True)
    (dist / "manifest.json").write_text(json.dumps(manifest))


def test_extension_no_dist_fails(tmp_path: Path):
    r = asyncio.run(extension_probe(tmp_path))
    assert not r["passed"]
    assert "missing" in r["issues"]


def test_extension_missing_manifest(tmp_path: Path):
    (tmp_path / "dist").mkdir()
    r = asyncio.run(extension_probe(tmp_path))
    assert not r["passed"]
    assert "manifest.json" in r["issues"]


def test_extension_valid_v3(tmp_path: Path):
    dist = tmp_path / "dist"
    _write_manifest(dist, {
        "manifest_version": 3,
        "name": "Test",
        "version": "1.0",
        "action": {"default_popup": "popup.html"},
        "background": {"service_worker": "sw.js"},
    })
    (dist / "popup.html").write_text("<html></html>")
    (dist / "sw.js").write_text("// sw\n" + "x" * 64)
    r = asyncio.run(extension_probe(tmp_path))
    assert r["passed"], r["issues"]


def test_extension_v2_rejected(tmp_path: Path):
    dist = tmp_path / "dist"
    _write_manifest(dist, {
        "manifest_version": 2,
        "name": "Test",
        "version": "1.0",
        "browser_action": {"default_popup": "p.html"},
        "background": {"scripts": ["bg.js"], "persistent": True},
    })
    r = asyncio.run(extension_probe(tmp_path))
    assert not r["passed"]
    assert "manifest_version must be 3" in r["issues"]
    assert "v2-only" in r["issues"]


def test_extension_missing_ref_file(tmp_path: Path):
    dist = tmp_path / "dist"
    _write_manifest(dist, {
        "manifest_version": 3,
        "name": "Test",
        "version": "1.0",
        "background": {"service_worker": "missing.js"},
    })
    r = asyncio.run(extension_probe(tmp_path))
    assert not r["passed"]
    assert "missing.js" in r["issues"]


def test_extension_empty_bundle_flagged(tmp_path: Path):
    dist = tmp_path / "dist"
    _write_manifest(dist, {
        "manifest_version": 3,
        "name": "Test",
        "version": "1.0",
        "background": {"service_worker": "sw.js"},
    })
    (dist / "sw.js").write_text("")
    r = asyncio.run(extension_probe(tmp_path))
    assert not r["passed"]
    # Either "empty" (when <32 B) or "small" keyword.
    assert "empty" in r["issues"] or "small" in r["issues"]


def test_extension_invalid_json(tmp_path: Path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "manifest.json").write_text("{ not valid")
    r = asyncio.run(extension_probe(tmp_path))
    assert not r["passed"]
    assert "not valid JSON" in r["issues"]


# ─────────────────────── sse_probe ─────────────────────────────────

def test_sse_happy_path():
    r = asyncio.run(sse_probe())
    assert r["passed"], r["issues"]
    out = json.loads(r["raw"])
    assert out["chunks"] == len(DEFAULT_TOKENS)
    assert out["saw_done"] is True


def test_sse_insufficient_tokens_skips():
    # Caller-configuration error → skip (don't block delivery on our bug).
    r = asyncio.run(sse_probe(tokens=["only"], min_chunks=3))
    assert r["passed"]
    assert "skip" in r["raw"]


def test_sse_fast_chunks_ok():
    r = asyncio.run(sse_probe(tokens=["a", "b", "c", "d", "e"],
                              chunk_interval_s=0.001))
    assert r["passed"]
