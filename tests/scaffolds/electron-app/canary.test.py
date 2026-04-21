"""Canary — scaffolds/electron-app (retrofit)."""
from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCAFFOLD = REPO_ROOT / "scaffolds" / "electron-app"


def test_scaffold_tree_exists() -> None:
    for rel in ("package.json", "tsconfig.json", "tsconfig.electron.json",
                "vite.config.ts", "index.html", "main.ts", "preload.ts",
                "README.md", "src/App.tsx", "src/main.tsx"):
        assert (SCAFFOLD / rel).exists(), rel


def test_electron_separate_tsconfig() -> None:
    """Electron main-process code runs in Node, not the browser —
    the separate tsconfig.electron.json is what keeps the two target
    envs from stepping on each other. Drop it and the drone will hit
    weird DOM-missing errors at build time."""
    main_tsc = json.loads((SCAFFOLD / "tsconfig.json").read_text())
    elec_tsc = json.loads((SCAFFOLD / "tsconfig.electron.json").read_text())
    # They must be distinct configs (different lib / module settings)
    main_lib = main_tsc.get("compilerOptions", {}).get("lib", [])
    elec_lib = elec_tsc.get("compilerOptions", {}).get("lib", [])
    assert main_lib != elec_lib or main_tsc != elec_tsc, (
        "tsconfig.json and tsconfig.electron.json should have distinct target envs"
    )


def test_preload_script_exists_and_has_contextbridge() -> None:
    preload = (SCAFFOLD / "preload.ts").read_text()
    # Best-practice Electron preload uses contextBridge for the
    # renderer↔main boundary — a plain window.electron = {...} is
    # insecure (contextIsolation).
    assert "contextBridge" in preload or "ipcRenderer" in preload, (
        "preload should use contextBridge / ipcRenderer (context isolation)"
    )


def test_main_process_boots_browserwindow() -> None:
    main = (SCAFFOLD / "main.ts").read_text()
    assert "BrowserWindow" in main, "main.ts must create a BrowserWindow"
    assert "app" in main, "main.ts must reference the Electron app lifecycle"


def test_readme_documents_packaging() -> None:
    readme = (SCAFFOLD / "README.md").read_text().lower()
    assert "electron" in readme, "README should describe the Electron pattern"
