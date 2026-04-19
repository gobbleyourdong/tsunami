"""Tests for tsunami.core.dispatch — scaffold fingerprint + probe routing."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from tsunami.core.dispatch import detect_scaffold, probe_for_delivery


def _write_pkg(root: Path, deps: dict[str, str] | None = None,
               main: str | None = None, scripts: dict[str, str] | None = None):
    pkg: dict = {"name": "test", "version": "1.0.0"}
    if deps is not None:
        pkg["dependencies"] = deps
    if main is not None:
        pkg["main"] = main
    if scripts is not None:
        pkg["scripts"] = scripts
    (root / "package.json").write_text(json.dumps(pkg))


# ───────────────── detect_scaffold ─────────────────

def test_detect_chrome_extension_from_public(tmp_path: Path):
    (tmp_path / "public").mkdir()
    (tmp_path / "public" / "manifest.json").write_text(json.dumps({
        "manifest_version": 3, "name": "x", "version": "1.0",
    }))
    assert detect_scaffold(tmp_path) == "chrome-extension"


def test_detect_chrome_extension_from_dist(tmp_path: Path):
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist" / "manifest.json").write_text(json.dumps({
        "manifest_version": 3, "name": "x", "version": "1.0",
    }))
    assert detect_scaffold(tmp_path) == "chrome-extension"


def test_detect_electron(tmp_path: Path):
    _write_pkg(tmp_path, deps={"electron": "^30"}, main="dist/main.js")
    assert detect_scaffold(tmp_path) == "electron-app"


def test_detect_api_only_from_openapi_source(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "openapi.ts").write_text("export const spec = {};")
    _write_pkg(tmp_path, deps={"fastify": "^5"})
    assert detect_scaffold(tmp_path) == "api-only"


def test_detect_realtime_from_ws_dep(tmp_path: Path):
    _write_pkg(tmp_path, deps={"ws": "^8"})
    assert detect_scaffold(tmp_path) == "realtime"


def test_detect_auth_app_from_server_code(tmp_path: Path):
    _write_pkg(tmp_path, deps={})
    (tmp_path / "server").mkdir()
    (tmp_path / "server" / "login.ts").write_text(
        "import jwt from 'jsonwebtoken';\nconst x = bcrypt.hash(...);"
    )
    assert detect_scaffold(tmp_path) == "auth-app"


def test_detect_fullstack_from_server_without_auth(tmp_path: Path):
    _write_pkg(tmp_path, deps={})
    (tmp_path / "server").mkdir()
    (tmp_path / "server" / "routes.ts").write_text("// plain crud handlers only")
    assert detect_scaffold(tmp_path) == "fullstack"


def test_detect_ai_app_from_env(tmp_path: Path):
    _write_pkg(tmp_path, deps={"react": "^19"})
    (tmp_path / ".env").write_text("VITE_MODEL_ENDPOINT=http://localhost:8090\n")
    assert detect_scaffold(tmp_path) == "ai-app"


def test_detect_plain_react_returns_none(tmp_path: Path):
    _write_pkg(tmp_path, deps={"react": "^19"})
    assert detect_scaffold(tmp_path) is None


def test_detect_no_package_json_returns_none(tmp_path: Path):
    assert detect_scaffold(tmp_path) is None


# ─────────────────── probe_for_delivery ───────────────────

def test_dispatch_missing_project_skips(tmp_path: Path):
    r = asyncio.run(probe_for_delivery(tmp_path / "does-not-exist"))
    assert r["passed"] is True
    assert "no project dir" in r["raw"]


def test_dispatch_no_fingerprint_skips(tmp_path: Path):
    # Plain react-app — not in our probe set.
    _write_pkg(tmp_path, deps={"react": "^19"})
    r = asyncio.run(probe_for_delivery(tmp_path))
    assert r["passed"] is True
    assert "no scaffold fingerprint" in r["raw"]


def test_dispatch_explicit_scaffold_overrides_fingerprint(tmp_path: Path):
    # Empty dir → extension_probe will fail (no dist/), not skip —
    # confirms the explicit kwarg bypasses detection.
    r = asyncio.run(probe_for_delivery(tmp_path, scaffold="chrome-extension"))
    assert r["passed"] is False
    assert "dist" in r["issues"].lower()


def test_dispatch_unknown_scaffold_skips(tmp_path: Path):
    r = asyncio.run(probe_for_delivery(tmp_path, scaffold="data-viz"))
    assert r["passed"] is True
    assert "no probe registered" in r["raw"]
