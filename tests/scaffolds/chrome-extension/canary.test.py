"""Canary — scaffolds/chrome-extension (retrofit)."""
from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCAFFOLD = REPO_ROOT / "scaffolds" / "chrome-extension"


def test_scaffold_tree_exists() -> None:
    for rel in ("package.json", "tsconfig.json", "vite.config.ts",
                "popup.html", "README.md",
                "public/manifest.json", "src/popup", "src/content", "src/background"):
        assert (SCAFFOLD / rel).exists(), rel


def test_manifest_v3_shape() -> None:
    m = json.loads((SCAFFOLD / "public" / "manifest.json").read_text())
    # Chrome extensions v3 required fields
    assert m.get("manifest_version") == 3, (
        "chrome-extension must ship manifest v3 (v2 deprecated 2024)"
    )
    assert "name" in m and "version" in m
    # Should have at least one of: action/popup, background, content_scripts
    entry_surfaces = [
        "action" in m,
        "background" in m,
        "content_scripts" in m,
    ]
    assert any(entry_surfaces), "manifest must declare at least one entry surface"


def test_popup_background_content_dirs_populated() -> None:
    for sub in ("popup", "background", "content"):
        d = SCAFFOLD / "src" / sub
        files = list(d.iterdir())
        assert files, f"src/{sub}/ is empty"


def test_vite_config_handles_multi_entry() -> None:
    """Chrome extensions need multiple entry points (popup, background,
    content) — vite must be configured with rollupOptions.input or a
    multi-target build."""
    vc = (SCAFFOLD / "vite.config.ts").read_text()
    has_rollup = "rollupOptions" in vc or "rollupoptions" in vc.lower()
    has_inputs = "input:" in vc or "inputs" in vc.lower()
    has_build = "build" in vc.lower()
    assert has_rollup or has_inputs or has_build, (
        "vite.config must configure a multi-entry build for popup/background/content"
    )


def test_readme_documents_extension_loading() -> None:
    readme = (SCAFFOLD / "README.md").read_text().lower()
    assert any(t in readme for t in ("chrome", "extension", "unpacked", "manifest")), (
        "README should explain how to load the extension"
    )
