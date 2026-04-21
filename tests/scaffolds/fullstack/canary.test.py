"""Canary — scaffolds/fullstack (retrofit)."""
from __future__ import annotations

import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCAFFOLD = REPO_ROOT / "scaffolds" / "fullstack"


def test_scaffold_tree_exists() -> None:
    for rel in ("package.json", "tsconfig.json", "vite.config.ts", "index.html",
                "README.md", "src/App.tsx", "server/index.js"):
        assert (SCAFFOLD / rel).exists(), rel


def test_frontend_and_backend_deps_both_present() -> None:
    pkg = json.loads((SCAFFOLD / "package.json").read_text())
    deps = pkg.get("dependencies", {})
    # Frontend half
    assert "react" in deps, "fullstack must ship React"
    # Backend half
    assert "express" in deps, "fullstack must ship express"
    assert "better-sqlite3" in deps, "fullstack must ship better-sqlite3"


def test_server_index_wires_sqlite() -> None:
    src = (SCAFFOLD / "server" / "index.js").read_text()
    assert "better-sqlite3" in src or "Database" in src, (
        "fullstack server must wire SQLite"
    )
    assert "express" in src, "fullstack server must use express"


def test_dev_runs_concurrent_client_server() -> None:
    pkg = json.loads((SCAFFOLD / "package.json").read_text())
    dev = pkg["scripts"]["dev"]
    # Either concurrently or npm-run-all, OR separate start scripts
    has_conc = "vite" in dev and "node" in dev
    assert has_conc, "fullstack dev script should run vite + node together"


def test_readme_mentions_api_contract() -> None:
    readme = (SCAFFOLD / "README.md").read_text().lower()
    # Fullstack scaffold needs to tell the drone how the two halves
    # talk — whether proxy config, vite server options, or CORS
    assert any(t in readme for t in ("api", "proxy", "backend", "/api/", "server")), (
        "README should describe client↔server communication"
    )
