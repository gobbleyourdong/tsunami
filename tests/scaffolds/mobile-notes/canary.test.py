"""Canary — scaffolds/mobile/notes."""
from __future__ import annotations

import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCAFFOLD = REPO_ROOT / "scaffolds" / "mobile" / "notes"


def test_scaffold_tree_exists() -> None:
    assert SCAFFOLD.is_dir()
    for rel in (
        "package.json",
        "tsconfig.json",
        "vite.config.ts",
        "index.html",
        "main.tsx",
        "README.md",
        "public/manifest.json",
        "src/App.tsx",
        "src/index.css",
        "src/sw.ts",
        "src/lib/sw-register.ts",
        "src/lib/notes-store.ts",
        "src/components/NoteList.tsx",
        "src/components/NoteEditor.tsx",
        "src/components/index.ts",
    ):
        assert (SCAFFOLD / rel).exists(), rel


def test_manifest_shape() -> None:
    m = json.loads((SCAFFOLD / "public" / "manifest.json").read_text())
    for k in ("name", "short_name", "start_url", "display", "icons"):
        assert k in m, k
    sizes = {i.get("sizes") for i in m["icons"]}
    assert {"192x192", "512x512"}.issubset(sizes)


def test_index_html_pwa_meta() -> None:
    html = (SCAFFOLD / "index.html").read_text()
    assert 'rel="manifest"' in html
    assert 'apple-mobile-web-app-capable' in html


def test_service_worker_cache_strategy() -> None:
    sw = (SCAFFOLD / "src" / "sw.ts").read_text()
    for token in ("CACHE_VERSION", "install", "activate", "fetch",
                  "/manifest.json", "fetch(req).catch"):
        assert token in sw, f"sw.ts missing: {token}"


def test_note_type_shape() -> None:
    store = (SCAFFOLD / "src" / "lib" / "notes-store.ts").read_text()
    for f in ("id:", "title:", "body:", "created_at:", "updated_at:"):
        assert f in store, f"Note should declare {f}"


def test_editor_autosave_debounced() -> None:
    editor = (SCAFFOLD / "src" / "components" / "NoteEditor.tsx").read_text()
    assert "setTimeout" in editor, "editor should debounce saves"
    assert "updateNote" in editor, "editor should call updateNote in the debounce"


def test_notes_sorted_newest_first_in_hook() -> None:
    """useNotes returns newest-first by updated_at."""
    store = (SCAFFOLD / "src" / "lib" / "notes-store.ts").read_text()
    assert "useNotes" in store
    # Look for a .sort call referencing updated_at (nested parens make
    # a bounded regex brittle — cheap line-adjacency check instead).
    lines = store.splitlines()
    sort_idx = next((i for i, l in enumerate(lines) if ".sort(" in l), -1)
    assert sort_idx >= 0, "useNotes should call .sort()"
    window = "\n".join(lines[sort_idx:sort_idx + 3])
    assert "updated_at" in window, "useNotes .sort should reference updated_at"


def test_components_barrel() -> None:
    barrel = (SCAFFOLD / "src" / "components" / "index.ts").read_text()
    for name in ("NoteList", "NoteEditor"):
        assert re.search(rf"\b{name}\b", barrel)


def test_safe_area_css() -> None:
    css = (SCAFFOLD / "src" / "index.css").read_text()
    assert "env(safe-area-inset-" in css
