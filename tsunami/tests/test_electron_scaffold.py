"""Tests for Chunk 7: Electron App Scaffold.

Verifies:
- Scaffold directory structure exists
- Key files present (main.ts, preload.ts, App.tsx, useIPC.ts)
- Package.json has Electron deps
- Classifier picks electron-app correctly
"""

import json
from pathlib import Path

from tsunami.tools.project_init import _pick_scaffold

SCAFFOLD_DIR = Path(__file__).parent.parent.parent / "scaffolds" / "electron-app"


class TestScaffoldExists:
    """Electron app scaffold directory structure."""

    def test_scaffold_dir_exists(self):
        assert SCAFFOLD_DIR.exists()

    def test_package_json_exists(self):
        assert (SCAFFOLD_DIR / "package.json").exists()

    def test_main_ts_exists(self):
        assert (SCAFFOLD_DIR / "main.ts").exists()

    def test_preload_ts_exists(self):
        assert (SCAFFOLD_DIR / "preload.ts").exists()

    def test_app_tsx_exists(self):
        assert (SCAFFOLD_DIR / "src" / "App.tsx").exists()

    def test_use_ipc_hook_exists(self):
        assert (SCAFFOLD_DIR / "src" / "hooks" / "useIPC.ts").exists()

    def test_main_tsx_exists(self):
        assert (SCAFFOLD_DIR / "src" / "main.tsx").exists()

    def test_index_html_exists(self):
        assert (SCAFFOLD_DIR / "index.html").exists()

    def test_vite_config_exists(self):
        assert (SCAFFOLD_DIR / "vite.config.ts").exists()

    def test_tsconfig_exists(self):
        assert (SCAFFOLD_DIR / "tsconfig.json").exists()

    def test_tsconfig_electron_exists(self):
        assert (SCAFFOLD_DIR / "tsconfig.electron.json").exists()

    def test_index_css_exists(self):
        assert (SCAFFOLD_DIR / "src" / "index.css").exists()


class TestPackageJson:
    """Package.json has correct Electron dependencies."""

    def test_has_electron(self):
        pkg = json.loads((SCAFFOLD_DIR / "package.json").read_text())
        assert "electron" in pkg["devDependencies"]

    def test_has_electron_builder(self):
        pkg = json.loads((SCAFFOLD_DIR / "package.json").read_text())
        assert "electron-builder" in pkg["devDependencies"]

    def test_has_react(self):
        pkg = json.loads((SCAFFOLD_DIR / "package.json").read_text())
        assert "react" in pkg["dependencies"]

    def test_has_main_field(self):
        pkg = json.loads((SCAFFOLD_DIR / "package.json").read_text())
        assert "main" in pkg
        assert "dist-electron" in pkg["main"]

    def test_has_build_config(self):
        pkg = json.loads((SCAFFOLD_DIR / "package.json").read_text())
        assert "build" in pkg
        assert "appId" in pkg["build"]

    def test_has_electron_dev_script(self):
        pkg = json.loads((SCAFFOLD_DIR / "package.json").read_text())
        assert "electron:dev" in pkg["scripts"]


class TestMainProcess:
    """Main process file structure."""

    def test_main_has_browser_window(self):
        content = (SCAFFOLD_DIR / "main.ts").read_text()
        assert "BrowserWindow" in content

    def test_main_has_ipc_handlers(self):
        content = (SCAFFOLD_DIR / "main.ts").read_text()
        assert "ipcMain.handle" in content

    def test_preload_has_context_bridge(self):
        content = (SCAFFOLD_DIR / "preload.ts").read_text()
        assert "contextBridge" in content
        assert "exposeInMainWorld" in content


class TestUseIPCHook:
    """useIPC hook for React renderer."""

    def test_has_invoke(self):
        content = (SCAFFOLD_DIR / "src" / "hooks" / "useIPC.ts").read_text()
        assert "invoke" in content

    def test_has_electron_api_type(self):
        content = (SCAFFOLD_DIR / "src" / "hooks" / "useIPC.ts").read_text()
        assert "ElectronAPI" in content

    def test_has_browser_fallback(self):
        content = (SCAFFOLD_DIR / "src" / "hooks" / "useIPC.ts").read_text()
        assert "isElectron" in content


class TestClassifier:
    """Scaffold classifier picks electron-app correctly."""

    def test_electron_keyword(self):
        assert _pick_scaffold("electron app", []) == "electron-app"

    def test_desktop_app_keyword(self):
        assert _pick_scaffold("desktop app", []) == "electron-app"

    def test_desktop_keyword(self):
        assert _pick_scaffold("build a desktop markdown editor", []) == "electron-app"

    def test_native_app_keyword(self):
        assert _pick_scaffold("native app with file access", []) == "electron-app"

    def test_tray_keyword(self):
        assert _pick_scaffold("system tray application", []) == "electron-app"

    def test_does_not_match_web_app(self):
        result = _pick_scaffold("weather web app", [])
        assert result != "electron-app"
