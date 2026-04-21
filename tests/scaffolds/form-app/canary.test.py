"""Canary — scaffolds/form-app (retrofit)."""
from __future__ import annotations

import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCAFFOLD = REPO_ROOT / "scaffolds" / "form-app"


def test_scaffold_tree_exists() -> None:
    for rel in ("package.json", "tsconfig.json", "vite.config.ts", "index.html",
                "README.md", "src/App.tsx", "src/components/index.ts"):
        assert (SCAFFOLD / rel).exists(), rel


def test_file_handling_libs_present() -> None:
    pkg = json.loads((SCAFFOLD / "package.json").read_text())
    deps = pkg.get("dependencies", {})
    # form-app exists to handle xlsx + csv — those libs must be present
    assert "xlsx" in deps, "form-app must depend on xlsx"
    assert "papaparse" in deps, "form-app must depend on papaparse"


def test_components_barrel_exports() -> None:
    barrel = (SCAFFOLD / "src" / "components" / "index.ts").read_text()
    for name in ("FileDropzone", "DataTable", "parseFile", "exportCsv"):
        assert re.search(rf"\b{name}\b", barrel), f"missing export: {name}"


def test_parsefile_handles_both_formats() -> None:
    src = (SCAFFOLD / "src" / "components" / "parseFile.ts").read_text()
    # The parser should branch on extension / mime and route to
    # papaparse for csv, xlsx for excel
    assert "papa" in src.lower() or "papaparse" in src.lower(), (
        "parseFile should use papaparse for CSV"
    )
    assert "xlsx" in src.lower(), "parseFile should use xlsx for spreadsheets"


def test_dropzone_accepts_files() -> None:
    src = (SCAFFOLD / "src" / "components" / "FileDropzone.tsx").read_text()
    # Must wire up drag/drop OR file input
    has_drop = "onDrop" in src or "drop" in src.lower()
    has_input = 'type="file"' in src or "input" in src.lower()
    assert has_drop or has_input, "FileDropzone should accept file input"


def test_readme_documents_supported_formats() -> None:
    readme = (SCAFFOLD / "README.md").read_text().lower()
    # At least CSV must be documented; xlsx is a plus
    assert "csv" in readme, "README should mention csv support"
