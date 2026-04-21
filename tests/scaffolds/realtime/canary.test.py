"""Canary — scaffolds/realtime (retrofit)."""
from __future__ import annotations

import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCAFFOLD = REPO_ROOT / "scaffolds" / "realtime"


def test_scaffold_tree_exists() -> None:
    for rel in ("package.json", "tsconfig.json", "vite.config.ts", "index.html",
                "README.md", "src/App.tsx", "src/components/index.ts",
                "server/index.js"):
        assert (SCAFFOLD / rel).exists(), rel


def test_package_has_ws_and_concurrently() -> None:
    pkg = json.loads((SCAFFOLD / "package.json").read_text())
    deps = pkg.get("dependencies", {})
    assert "ws" in deps, "realtime must depend on ws (websocket server)"
    assert "express" in deps, "realtime must depend on express"
    # concurrently lets dev run vite + node side-by-side
    assert "concurrently" in pkg.get("devDependencies", {}), (
        "realtime dev script should use concurrently to run vite + node"
    )


def test_dev_script_runs_both_sides() -> None:
    pkg = json.loads((SCAFFOLD / "package.json").read_text())
    dev = pkg["scripts"]["dev"]
    assert "vite" in dev and "node" in dev, (
        "realtime dev script must start both the Vite client and Node server"
    )


def test_server_uses_websocket() -> None:
    src = (SCAFFOLD / "server" / "index.js").read_text()
    assert "ws" in src or "WebSocket" in src, "server must use websockets"


def test_chat_components_barrel() -> None:
    barrel = (SCAFFOLD / "src" / "components" / "index.ts").read_text()
    for name in ("ChatFeed", "ChatInput", "PresenceDot"):
        assert re.search(rf"\b{name}\b", barrel), f"missing export: {name}"


def test_useWebSocket_hook_exists() -> None:
    hook = SCAFFOLD / "src" / "components" / "useWebSocket.ts"
    # Either here or under hooks/ — accept either
    alt = SCAFFOLD / "src" / "hooks" / "useWebSocket.ts"
    assert hook.exists() or alt.exists(), "useWebSocket hook must exist"


def test_readme_documents_realtime_pattern() -> None:
    readme = (SCAFFOLD / "README.md").read_text().lower()
    assert "websocket" in readme or "ws" in readme, (
        "README should document the websocket transport"
    )
