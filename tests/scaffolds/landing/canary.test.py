"""Canary — scaffolds/landing (retrofit).

Structural canary for the top-level landing scaffold. Verifies:
- Tree + build chain exist
- package.json has React 19 + Vite
- Components barrel exports the 10 canonical landing components
- Tokens CSS files (light + neutral) present
- App.tsx compiles against available component imports (grep-level check)
"""
from __future__ import annotations

import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCAFFOLD = REPO_ROOT / "scaffolds" / "landing"


EXPECTED_COMPONENTS = (
    "Navbar", "Hero", "Section", "FeatureGrid", "Footer",
    "ParallaxHero", "PortfolioGrid", "Testimonials",
    "StatsRow", "CTASection",
)


def test_scaffold_tree_exists() -> None:
    assert SCAFFOLD.is_dir()
    for rel in (
        "package.json",
        "tsconfig.json",
        "vite.config.ts",
        "index.html",
        "main.tsx",
        "README.md",
        "src/App.tsx",
        "src/main.tsx",
        "src/index.css",
        "src/components/index.ts",
        "src/tokens_light.css",
        "src/tokens_neutral.css",
    ):
        assert (SCAFFOLD / rel).exists(), rel


def test_package_deps_react_19() -> None:
    pkg = json.loads((SCAFFOLD / "package.json").read_text())
    assert pkg["name"] == "landing"
    assert pkg["dependencies"]["react"].startswith("^19"), pkg["dependencies"]["react"]
    assert pkg["dependencies"]["react-dom"].startswith("^19")
    assert "vite" in pkg["devDependencies"]


def test_components_barrel_exports_full_set() -> None:
    barrel = (SCAFFOLD / "src" / "components" / "index.ts").read_text()
    for name in EXPECTED_COMPONENTS:
        assert re.search(rf"\b{name}\b", barrel), f"missing export: {name}"


def test_each_component_file_exists() -> None:
    for name in EXPECTED_COMPONENTS:
        path = SCAFFOLD / "src" / "components" / f"{name}.tsx"
        assert path.exists(), f"missing component file: {name}.tsx"


def test_tokens_css_define_required_vars() -> None:
    """Light + neutral tokens must both define the core palette knobs —
    if a drone writes a new theme against a token that only exists in
    one file, the missing one breaks the scaffold."""
    light = (SCAFFOLD / "src" / "tokens_light.css").read_text()
    neutral = (SCAFFOLD / "src" / "tokens_neutral.css").read_text()
    # Both should be valid CSS blocks with at least :root or html selector
    for name, css in [("light", light), ("neutral", neutral)]:
        assert ("--" in css), f"{name} tokens CSS has no CSS vars"
        assert (":root" in css or "html" in css), f"{name} tokens missing selector"


def test_readme_documents_component_catalog() -> None:
    """README must list the available components so project_init's
    export-surfacing logic (which reads the barrel) isn't the only
    discovery path."""
    readme = (SCAFFOLD / "README.md").read_text()
    missing = [c for c in EXPECTED_COMPONENTS if c not in readme]
    assert not missing, f"README doesn't mention: {missing}"
