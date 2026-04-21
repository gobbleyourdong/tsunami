"""Canary — scaffolds/ai-app (retrofit)."""
from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCAFFOLD = REPO_ROOT / "scaffolds" / "ai-app"


def test_scaffold_tree_exists() -> None:
    for rel in ("package.json", "tsconfig.json", "vite.config.ts", "index.html",
                "README.md", "src/App.tsx", "src/main.tsx",
                "server/index.js"):
        assert (SCAFFOLD / rel).exists(), rel


def test_ai_transport_deps_present() -> None:
    pkg = json.loads((SCAFFOLD / "package.json").read_text())
    deps = pkg.get("dependencies", {})
    # Streaming chat proxy needs a backend for API-key safety → express + cors
    for lib in ("express", "cors", "dotenv"):
        assert lib in deps, f"ai-app must depend on {lib}"


def test_dotenv_for_api_keys() -> None:
    """API keys must be server-side — dotenv + server/ split is the
    pattern; if the drone moves keys into the client, auth is leaked."""
    pkg = json.loads((SCAFFOLD / "package.json").read_text())
    assert "dotenv" in pkg["dependencies"], (
        "ai-app must ship dotenv so the drone knows keys go server-side"
    )
    # README should reinforce the boundary
    readme = (SCAFFOLD / "README.md").read_text().lower()
    assert "env" in readme or ".env" in readme, (
        "README should document env-var pattern for API keys"
    )


def test_dev_runs_both_client_and_server() -> None:
    pkg = json.loads((SCAFFOLD / "package.json").read_text())
    dev = pkg["scripts"]["dev"]
    assert "vite" in dev and "node" in dev, (
        "ai-app dev script must run vite (client) + node (proxy) concurrently"
    )


def test_server_has_chat_proxy_hook() -> None:
    """The backend is the place the drone wires up OpenAI/Anthropic/etc.
    — scaffold just ships a streaming-ready proxy shape."""
    src = (SCAFFOLD / "server" / "index.js").read_text()
    # Must set up express + a streaming-capable response
    assert "express" in src, "server must use express"
    assert "app.post" in src or "app.get" in src, (
        "server must expose at least one HTTP route"
    )


def test_readme_mentions_streaming_or_sse() -> None:
    readme = (SCAFFOLD / "README.md").read_text().lower()
    # Streaming response is the scaffold's reason to exist; must be documented
    assert any(token in readme for token in ("stream", "sse", "server-sent", "chat")), (
        "README should describe the streaming / chat pattern"
    )
