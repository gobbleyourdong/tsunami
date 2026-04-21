"""Canary — scaffolds/dashboard (retrofit)."""
from __future__ import annotations

import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCAFFOLD = REPO_ROOT / "scaffolds" / "dashboard"


EXPECTED_COMPONENTS = (
    "Layout", "Card", "StatCard", "DataTable", "ChartCard",
    "Modal", "ToastContainer", "Badge", "EmptyState",
)


def test_scaffold_tree_exists() -> None:
    assert SCAFFOLD.is_dir()
    for rel in (
        "package.json",
        "tsconfig.json",
        "vite.config.ts",
        "index.html",
        "README.md",
        "src/App.tsx",
        "src/main.tsx",
        "src/index.css",
        "src/components/index.ts",
        "src/tokens_light.css",
        "src/tokens_neutral.css",
    ):
        assert (SCAFFOLD / rel).exists(), rel


def test_package_shape() -> None:
    pkg = json.loads((SCAFFOLD / "package.json").read_text())
    assert pkg["name"] == "dashboard"
    assert pkg["dependencies"]["react"].startswith("^19")
    assert "vite" in pkg["devDependencies"]


def test_components_barrel_exports_full_set() -> None:
    barrel = (SCAFFOLD / "src" / "components" / "index.ts").read_text()
    for name in EXPECTED_COMPONENTS:
        assert re.search(rf"\b{name}\b", barrel), f"missing export: {name}"
    # Additional: ToastContainer co-exports the `toast` imperative API
    assert "toast" in barrel, "toast function should be exported alongside ToastContainer"


def test_each_component_file_exists() -> None:
    for name in ("Layout", "Card", "StatCard", "DataTable", "ChartCard",
                 "Modal", "Toast", "Badge", "EmptyState"):
        path = SCAFFOLD / "src" / "components" / f"{name}.tsx"
        assert path.exists(), f"missing component: {name}.tsx"


def test_tokens_css_present() -> None:
    for name in ("tokens_light.css", "tokens_neutral.css"):
        css = (SCAFFOLD / "src" / name).read_text()
        assert "--" in css, f"{name} defines no CSS vars"


def test_readme_documents_component_catalog() -> None:
    readme = (SCAFFOLD / "README.md").read_text()
    missing = [c for c in EXPECTED_COMPONENTS if c not in readme]
    # ToastContainer may be documented as just "Toast" — accept either
    if "ToastContainer" in missing and "Toast" in readme:
        missing.remove("ToastContainer")
    assert not missing, f"README missing: {missing}"
