"""Canary — scaffolds/api-only (retrofit).

Express 5 + SQLite backend-only scaffold. No React tree; the canary
checks server shape + CRUD endpoint signatures instead of component
barrels.
"""
from __future__ import annotations

import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCAFFOLD = REPO_ROOT / "scaffolds" / "api-only"


def test_scaffold_tree_exists() -> None:
    assert SCAFFOLD.is_dir()
    for rel in ("package.json", "README.md", "server/index.js"):
        assert (SCAFFOLD / rel).exists(), rel


def test_package_has_backend_deps_not_react() -> None:
    pkg = json.loads((SCAFFOLD / "package.json").read_text())
    assert pkg["name"] == "api-only"
    deps = pkg.get("dependencies", {})
    assert "express" in deps, "api-only must depend on express"
    assert "better-sqlite3" in deps, "api-only must depend on better-sqlite3"
    # Critical: no React — this is the backend-only scaffold
    assert "react" not in deps, "api-only must NOT depend on react (wrong scaffold routing if so)"


def test_server_entrypoint_signals() -> None:
    src = (SCAFFOLD / "server" / "index.js").read_text()
    for marker in ("import express", "better-sqlite3", "app.listen", "CREATE TABLE"):
        assert marker in src, f"server/index.js missing: {marker!r}"


def test_server_exposes_crud_routes() -> None:
    src = (SCAFFOLD / "server" / "index.js").read_text()
    patterns = (
        r"\bapp\.get\(",
        r"\bapp\.post\(",
        r"\bapp\.put\(",
        r"\bapp\.delete\(",
    )
    for p in patterns:
        assert re.search(p, src), f"missing route method: {p}"


def test_dev_script_uses_node_watch() -> None:
    pkg = json.loads((SCAFFOLD / "package.json").read_text())
    assert "node --watch" in pkg["scripts"]["dev"], (
        "api-only dev script should use node --watch for auto-reload"
    )


def test_readme_documents_endpoints_and_health() -> None:
    readme = (SCAFFOLD / "README.md").read_text()
    assert "/health" in readme, "README should document the health endpoint"
    for verb in ("GET", "POST", "PUT", "DELETE"):
        assert verb in readme, f"README should document {verb} route"
