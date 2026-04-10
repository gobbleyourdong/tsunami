"""Tests for Chunk 6: Chrome Extension Scaffold.

Verifies:
- Scaffold directory structure exists
- Key files present (manifest.json, App.tsx, content.ts, service-worker.ts)
- Manifest V3 format valid
- Classifier picks chrome-extension for relevant prompts
"""

import json
from pathlib import Path

from tsunami.tools.project_init import _pick_scaffold

SCAFFOLD_DIR = Path(__file__).parent.parent.parent / "scaffolds" / "chrome-extension"


class TestScaffoldExists:
    """Chrome extension scaffold directory structure."""

    def test_scaffold_dir_exists(self):
        assert SCAFFOLD_DIR.exists()

    def test_package_json_exists(self):
        assert (SCAFFOLD_DIR / "package.json").exists()

    def test_manifest_exists(self):
        assert (SCAFFOLD_DIR / "public" / "manifest.json").exists()

    def test_popup_app_exists(self):
        assert (SCAFFOLD_DIR / "src" / "popup" / "App.tsx").exists()

    def test_popup_main_exists(self):
        assert (SCAFFOLD_DIR / "src" / "popup" / "main.tsx").exists()

    def test_content_script_exists(self):
        assert (SCAFFOLD_DIR / "src" / "content" / "content.ts").exists()

    def test_service_worker_exists(self):
        assert (SCAFFOLD_DIR / "src" / "background" / "service-worker.ts").exists()

    def test_vite_config_exists(self):
        assert (SCAFFOLD_DIR / "vite.config.ts").exists()

    def test_tsconfig_exists(self):
        assert (SCAFFOLD_DIR / "tsconfig.json").exists()

    def test_popup_html_exists(self):
        assert (SCAFFOLD_DIR / "popup.html").exists()

    def test_index_css_exists(self):
        assert (SCAFFOLD_DIR / "src" / "index.css").exists()


class TestManifest:
    """Manifest V3 format validation."""

    def test_valid_json(self):
        manifest = json.loads((SCAFFOLD_DIR / "public" / "manifest.json").read_text())
        assert isinstance(manifest, dict)

    def test_manifest_version_3(self):
        manifest = json.loads((SCAFFOLD_DIR / "public" / "manifest.json").read_text())
        assert manifest["manifest_version"] == 3

    def test_has_action(self):
        manifest = json.loads((SCAFFOLD_DIR / "public" / "manifest.json").read_text())
        assert "action" in manifest
        assert "default_popup" in manifest["action"]

    def test_has_background(self):
        manifest = json.loads((SCAFFOLD_DIR / "public" / "manifest.json").read_text())
        assert "background" in manifest
        assert "service_worker" in manifest["background"]

    def test_has_content_scripts(self):
        manifest = json.loads((SCAFFOLD_DIR / "public" / "manifest.json").read_text())
        assert "content_scripts" in manifest
        assert len(manifest["content_scripts"]) > 0

    def test_has_permissions(self):
        manifest = json.loads((SCAFFOLD_DIR / "public" / "manifest.json").read_text())
        assert "permissions" in manifest
        assert "activeTab" in manifest["permissions"]


class TestPackageJson:
    """Package.json has correct dependencies."""

    def test_has_react(self):
        pkg = json.loads((SCAFFOLD_DIR / "package.json").read_text())
        assert "react" in pkg["dependencies"]

    def test_has_crxjs(self):
        pkg = json.loads((SCAFFOLD_DIR / "package.json").read_text())
        assert "@crxjs/vite-plugin" in pkg["devDependencies"]

    def test_has_chrome_types(self):
        pkg = json.loads((SCAFFOLD_DIR / "package.json").read_text())
        assert "@types/chrome" in pkg["devDependencies"]

    def test_has_build_script(self):
        pkg = json.loads((SCAFFOLD_DIR / "package.json").read_text())
        assert "build" in pkg["scripts"]


class TestClassifier:
    """Scaffold classifier picks chrome-extension correctly."""

    def test_chrome_extension_keyword(self):
        assert _pick_scaffold("chrome extension", []) == "chrome-extension"

    def test_browser_extension_keyword(self):
        assert _pick_scaffold("browser extension", []) == "chrome-extension"

    def test_extension_keyword(self):
        assert _pick_scaffold("build an extension that highlights links", []) == "chrome-extension"

    def test_content_script_keyword(self):
        assert _pick_scaffold("content script", []) == "chrome-extension"

    def test_popup_keyword(self):
        assert _pick_scaffold("popup for my extension", []) == "chrome-extension"

    def test_does_not_match_unrelated(self):
        result = _pick_scaffold("weather dashboard", [])
        assert result != "chrome-extension"
