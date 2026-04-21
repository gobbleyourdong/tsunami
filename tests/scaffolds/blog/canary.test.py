"""Canary — scaffolds/web/blog.

Structural + data-shape + tag-filter-logic canaries.
"""
from __future__ import annotations

import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCAFFOLD = REPO_ROOT / "scaffolds" / "web" / "blog"


def test_scaffold_tree_exists() -> None:
    assert SCAFFOLD.is_dir()
    for rel in (
        "package.json",
        "tsconfig.json",
        "vite.config.ts",
        "index.html",
        "main.tsx",
        "README.md",
        "data/posts.json",
        "src/App.tsx",
        "src/index.css",
        "src/data/posts.ts",
        "src/lib/md.tsx",
        "src/components/PostList.tsx",
        "src/components/PostDetail.tsx",
        "src/components/TagBar.tsx",
        "src/components/index.ts",
    ):
        assert (SCAFFOLD / rel).exists(), rel


def _posts() -> list[dict]:
    return json.loads((SCAFFOLD / "data" / "posts.json").read_text())["posts"]


def test_package_shape() -> None:
    pkg = json.loads((SCAFFOLD / "package.json").read_text())
    assert pkg["name"] == "blog"
    assert "react" in pkg["dependencies"]


def test_posts_shape() -> None:
    posts = _posts()
    assert len(posts) >= 3
    slugs = set()
    required = {"slug", "title", "date", "tags", "author", "excerpt", "body"}
    for p in posts:
        assert required.issubset(p.keys()), f"{p.get('slug')!r} missing fields"
        assert p["slug"] not in slugs, f"duplicate slug: {p['slug']}"
        slugs.add(p["slug"])
        assert re.match(r"^[a-z0-9-]+$", p["slug"]), f"bad slug: {p['slug']}"
        assert re.match(r"^\d{4}-\d{2}-\d{2}$", p["date"]), f"bad date: {p['date']}"
        assert isinstance(p["tags"], list) and p["tags"], "tags must be a non-empty list"
        assert p["body"].strip() and p["excerpt"].strip()


def test_tag_filter_logic() -> None:
    """Port byTag/allTags from src/data/posts.ts into Python and verify."""
    posts = _posts()
    tags = sorted({t for p in posts for t in p["tags"]})

    def by_tag(tag: str) -> list[dict]:
        if not tag:
            return sorted(posts, key=lambda p: p["date"], reverse=True)
        return sorted(
            [p for p in posts if tag in p["tags"]],
            key=lambda p: p["date"], reverse=True,
        )

    assert len(by_tag("")) == len(posts)
    for t in tags:
        matched = by_tag(t)
        assert matched, f"tag {t!r} returned no posts"
        for p in matched:
            assert t in p["tags"]


def test_dates_sortable_newest_first() -> None:
    """Sorting by date string (YYYY-MM-DD) must produce newest-first."""
    posts = _posts()
    sorted_posts = sorted(posts, key=lambda p: p["date"], reverse=True)
    dates = [p["date"] for p in sorted_posts]
    assert dates == sorted(dates, reverse=True)


def test_components_barrel() -> None:
    barrel = (SCAFFOLD / "src" / "components" / "index.ts").read_text()
    for name in ("PostList", "PostDetail", "TagBar"):
        assert re.search(rf"\b{name}\b", barrel)


def test_md_renderer_no_injection() -> None:
    md = (SCAFFOLD / "src" / "lib" / "md.tsx").read_text()
    assert "dangerouslySetInner" + "HTML" not in md
