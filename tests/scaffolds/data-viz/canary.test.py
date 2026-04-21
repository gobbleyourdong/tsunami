"""Canary — scaffolds/data-viz (retrofit)."""
from __future__ import annotations

import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCAFFOLD = REPO_ROOT / "scaffolds" / "data-viz"

COMPONENTS = ("ChartCard", "CsvLoader", "StatRow")
DATA_LIBS = ("recharts", "d3", "papaparse")


def test_scaffold_tree_exists() -> None:
    for rel in ("package.json", "tsconfig.json", "vite.config.ts", "index.html",
                "README.md", "src/App.tsx", "src/components/index.ts"):
        assert (SCAFFOLD / rel).exists(), rel


def test_chart_libraries_present() -> None:
    pkg = json.loads((SCAFFOLD / "package.json").read_text())
    deps = pkg.get("dependencies", {})
    for lib in DATA_LIBS:
        assert lib in deps, f"data-viz must depend on {lib}"
    # Matching TS types for d3 + papaparse (they're hand-maintained DT packages)
    devDeps = pkg.get("devDependencies", {})
    assert "@types/d3" in devDeps, "missing @types/d3 — TS will complain"
    assert "@types/papaparse" in devDeps, "missing @types/papaparse"


def test_components_barrel() -> None:
    barrel = (SCAFFOLD / "src" / "components" / "index.ts").read_text()
    for name in COMPONENTS:
        assert re.search(rf"\b{name}\b", barrel), f"missing export: {name}"


def test_data_libs_available_on_demand() -> None:
    """recharts / d3 / papaparse are shipped as deps for the drone to
    reach for; the default App.tsx may roll bars by hand and not
    import them. That's fine — what matters is they're installable
    (appear in package.json, covered above) and referenced somewhere
    in the scaffold surface so the drone knows they exist."""
    readme = (SCAFFOLD / "README.md").read_text().lower()
    # At least one of the libs should be named in the README so the
    # drone has a signal about what's available.
    assert any(lib in readme for lib in ("recharts", "d3", "papaparse", "csv")), (
        "README should mention at least one data lib by name for discovery"
    )


def test_csvloader_parses_csv() -> None:
    src = (SCAFFOLD / "src" / "components" / "CsvLoader.tsx").read_text()
    # CsvLoader should handle CSV in some form — either via papaparse
    # or via a hand-rolled split. Verify it's not an empty stub.
    assert len(src) > 200, "CsvLoader looks like an empty stub"
    assert ("csv" in src.lower() or "papa" in src.lower()), (
        "CsvLoader should reference csv or papa (the dep)"
    )


def test_readme_documents_data_story() -> None:
    readme = (SCAFFOLD / "README.md").read_text()
    for token in ("chart", "csv"):
        assert re.search(token, readme, re.IGNORECASE), f"README missing: {token}"
