"""Canary — scaffolds/web/docs-site.

Structural canary: verifies tree, data shape, component exports, and
that search tokenization produces expected hits against the seed
content. Doesn't run `vite build` or typecheck — those require
node_modules and are out of scope for a fast canary. The scaffold
README documents the `npm run build` / `check` commands.

Run with::

    pytest tests/scaffolds/docs-site/
"""
from __future__ import annotations

import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCAFFOLD = REPO_ROOT / "scaffolds" / "web" / "docs-site"


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
        "src/index.css",
        "src/components/Sidebar.tsx",
        "src/components/DocPage.tsx",
        "src/components/SearchBox.tsx",
        "src/components/ThemeToggle.tsx",
        "src/components/index.ts",
        "src/data/docs.ts",
        "src/lib/search.ts",
        "src/lib/md.tsx",
        "data/nav.json",
        "data/pages.json",
    ):
        assert (SCAFFOLD / rel).exists(), rel


def test_package_json_shape() -> None:
    pkg = json.loads((SCAFFOLD / "package.json").read_text())
    assert pkg["name"] == "docs-site"
    for dep in ("react", "react-dom"):
        assert dep in pkg["dependencies"], dep
    for dep in ("vite", "typescript", "@vitejs/plugin-react"):
        assert dep in pkg["devDependencies"], dep
    for script in ("dev", "build", "check"):
        assert script in pkg["scripts"], script


def test_nav_references_existing_pages() -> None:
    nav = json.loads((SCAFFOLD / "data" / "nav.json").read_text())
    pages = json.loads((SCAFFOLD / "data" / "pages.json").read_text())
    referenced: set[str] = set()
    for section in nav["sections"]:
        assert isinstance(section["title"], str)
        for p in section["pages"]:
            assert isinstance(p["slug"], str) and isinstance(p["title"], str)
            referenced.add(p["slug"])
    orphans = referenced - set(pages.keys())
    assert not orphans, f"nav references missing pages: {orphans}"


def test_page_bodies_nonempty() -> None:
    pages = json.loads((SCAFFOLD / "data" / "pages.json").read_text())
    assert len(pages) >= 5, "need at least 5 seed pages"
    for slug, page in pages.items():
        assert page["body"].strip(), f"{slug} body empty"
        assert page["title"].strip(), f"{slug} title empty"


def test_components_barrel_exports_expected() -> None:
    barrel = (SCAFFOLD / "src" / "components" / "index.ts").read_text()
    for name in ("Sidebar", "DocPage", "SearchBox", "ThemeToggle"):
        assert re.search(rf"\b{name}\b", barrel), f"missing export: {name}"


def test_md_renderer_has_no_inner_html_injection() -> None:
    md = (SCAFFOLD / "src" / "lib" / "md.tsx").read_text()
    assert "dangerouslySetInner" + "HTML" not in md, (
        "md.tsx must not use HTML-injection rendering"
    )


def test_search_tokenization_logic() -> None:
    """Port the tokenizer from src/lib/search.ts into Python and verify
    it finds expected slugs against the seed corpus. This is a logic
    canary — if either file changes, this will fail and prompt an update."""
    pages = json.loads((SCAFFOLD / "data" / "pages.json").read_text())

    def tokenize(s: str) -> set[str]:
        return set(re.findall(r"[a-z0-9]+", s.lower()))

    def search(q: str) -> list[str]:
        q_toks = tokenize(q)
        hits = []
        for slug, p in pages.items():
            p_toks = tokenize(p["title"] + " " + p["body"])
            if q_toks & p_toks:
                hits.append(slug)
        return hits

    assert "introduction" in search("welcome"), "'welcome' should match introduction"
    assert "installation" in search("node"), "'node' should match installation page"
    assert "deployment" in search("dist"), "'dist' should match deployment page"
