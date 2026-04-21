"""Canary — scaffolds/react-app (retrofit).

react-app is the default-fallback scaffold — anything that doesn't
match a more specific rule in project_init._pick_scaffold lands
here. Canary is deliberately minimal; the scaffold's whole job is
to be a clean blank slate.
"""
from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCAFFOLD = REPO_ROOT / "scaffolds" / "react-app"


def test_scaffold_tree_exists() -> None:
    for rel in ("package.json", "tsconfig.json", "vite.config.ts", "index.html",
                "README.md", "src/App.tsx", "src/main.tsx"):
        assert (SCAFFOLD / rel).exists(), rel


def test_package_shape_minimal_react() -> None:
    pkg = json.loads((SCAFFOLD / "package.json").read_text())
    assert pkg["name"] == "react-app"
    deps = pkg.get("dependencies", {})
    assert deps.get("react", "").startswith("^19"), "react must be ^19"
    assert deps.get("react-dom", "").startswith("^19"), "react-dom must be ^19"


def test_no_backend_deps_sneaking_in() -> None:
    """react-app is the minimal fallback. If express/sqlite/ws creep
    in, something is misrouted and the scaffold is no longer
    acceptable as the generic fallback."""
    pkg = json.loads((SCAFFOLD / "package.json").read_text())
    deps = pkg.get("dependencies", {})
    forbidden = ("express", "better-sqlite3", "ws", "bcryptjs", "jsonwebtoken")
    present = [d for d in forbidden if d in deps]
    assert not present, (
        f"react-app (default fallback) must stay minimal — "
        f"these deps belong in specialized scaffolds: {present}"
    )


def test_app_tsx_is_non_empty() -> None:
    """project_init stubs App.tsx to a Loading... stub on copy —
    but the source-of-truth App.tsx in scaffolds/react-app/ should
    have something more interesting than literally empty. The stub
    rewrite happens at project-init time, not here."""
    src = (SCAFFOLD / "src" / "App.tsx").read_text()
    assert src.strip(), "App.tsx is empty"
    assert "export default" in src, "App.tsx must export a default component"


def test_readme_explains_it_is_the_default() -> None:
    readme = (SCAFFOLD / "README.md").read_text().lower()
    assert "react" in readme, "README should describe the React baseline"
