"""Docs-site delivery gate — SSG configs + markdown content.

The docs vertical covers documentation deliverables: static-site
generators (MkDocs, Docusaurus, VitePress, Hugo, Astro, Jekyll),
Sphinx/RTD projects, and bare markdown content trees. Probe is
offline — we don't build the site.

Supported shapes, fingerprinted in priority order:

  1. **MkDocs**     — mkdocs.yml with site_name + docs/
  2. **Docusaurus** — docusaurus.config.{js,ts} + docs/ or blog/
  3. **VitePress**  — .vitepress/config.{js,ts,mjs} + content .md
  4. **Sphinx**     — conf.py + index.rst (or index.md w/ myst)
  5. **Hugo**       — hugo.{toml,yaml,json} + content/
  6. **Astro**      — astro.config.{mjs,js,ts} + src/content/ or src/pages/
  7. **Jekyll**     — _config.yml + _posts/ or index.md
  8. **Bare**       — docs/ or content/ directory with ≥2 .md files

Acceptance (all shapes):
  - Config or docs-dir exists
  - At least one .md/.mdx/.rst page exists in the expected location
  - At least one page has meaningful content (>400 chars of prose,
    not counting frontmatter / heading-only pages)
  - Homepage / index exists (index.md, intro.mdx, README.md, etc.)

Not caught:
  - Whether the site actually builds (needs Node/Python + SSG CLI)
  - Whether cross-links resolve (would need link-checker)
  - Whether content is accurate
"""

from __future__ import annotations

import re
from pathlib import Path

from ._probe_common import result


_CONTENT_FRONTMATTER_RE = re.compile(r"^---\n.*?\n---\n", re.DOTALL)
_MIN_CONTENT_CHARS = 400


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _strip_frontmatter(text: str) -> str:
    return _CONTENT_FRONTMATTER_RE.sub("", text, count=1)


def _page_has_content(p: Path) -> bool:
    """A page has 'real' content if the non-frontmatter non-heading
    body runs at least _MIN_CONTENT_CHARS of prose."""
    text = _strip_frontmatter(_read(p))
    # Strip markdown headings (# line) and empty lines
    body = "\n".join(line for line in text.splitlines()
                     if line.strip() and not line.strip().startswith("#"))
    return len(body) >= _MIN_CONTENT_CHARS


def _first_content_candidates(project_dir: Path) -> list[Path]:
    """Directories where content pages typically live."""
    candidates: list[Path] = []
    for rel in ("docs", "content", "src/content", "src/pages",
                "_posts", "pages", "posts"):
        d = project_dir / rel
        if d.is_dir():
            candidates.append(d)
    return candidates


def _collect_pages(dirs: list[Path]) -> list[Path]:
    pages: list[Path] = []
    for d in dirs:
        pages.extend(d.rglob("*.md"))
        pages.extend(d.rglob("*.mdx"))
        pages.extend(d.rglob("*.rst"))
    return pages


def _detect_shape(project_dir: Path) -> tuple[str, Path | None] | None:
    """Return (shape_name, config_path_or_none). Priority order."""
    if (project_dir / "mkdocs.yml").is_file():
        return "mkdocs", project_dir / "mkdocs.yml"
    for rel in ("docusaurus.config.js", "docusaurus.config.ts"):
        if (project_dir / rel).is_file():
            return "docusaurus", project_dir / rel
    for rel in (".vitepress/config.js", ".vitepress/config.ts",
                ".vitepress/config.mjs"):
        if (project_dir / rel).is_file():
            return "vitepress", project_dir / rel
    if (project_dir / "conf.py").is_file():
        return "sphinx", project_dir / "conf.py"
    for rel in ("hugo.toml", "hugo.yaml", "hugo.json", "config.toml"):
        p = project_dir / rel
        if p.is_file() and (_read(p).find("baseURL") >= 0 or rel.startswith("hugo.")):
            return "hugo", p
    for rel in ("astro.config.mjs", "astro.config.js", "astro.config.ts"):
        if (project_dir / rel).is_file():
            return "astro", project_dir / rel
    if (project_dir / "_config.yml").is_file():
        cfg_text = _read(project_dir / "_config.yml")
        # Disambiguate jekyll from a generic _config.yml — jekyll sites
        # typically have _posts/ OR _config.yml with a theme/permalink.
        if ((project_dir / "_posts").is_dir()
                or "theme:" in cfg_text
                or "permalink:" in cfg_text
                or "jekyll" in cfg_text.lower()):
            return "jekyll", project_dir / "_config.yml"

    # Bare: docs/ with ≥2 .md files
    for d in _first_content_candidates(project_dir):
        mds = list(d.rglob("*.md")) + list(d.rglob("*.mdx"))
        if len(mds) >= 2:
            return "bare", None
    return None


def _sphinx_index(project_dir: Path) -> Path | None:
    """Sphinx allows index.rst (default) or index.md with myst parser."""
    for rel in ("index.rst", "docs/index.rst", "source/index.rst",
                "index.md", "docs/index.md"):
        p = project_dir / rel
        if p.is_file():
            return p
    return None


def _has_homepage(shape: str, project_dir: Path) -> Path | None:
    """Each shape has a conventional homepage; return its path or None."""
    if shape == "sphinx":
        return _sphinx_index(project_dir)
    # All other shapes accept an index.md / README.md / intro.md
    roots = _first_content_candidates(project_dir) + [project_dir]
    for root in roots:
        for stem in ("index.md", "index.mdx", "intro.md", "intro.mdx",
                     "README.md", "getting-started.md",
                     "getting-started.mdx", "home.md"):
            p = root / stem
            if p.is_file():
                return p
    return None


async def docs_probe(
    project_dir: Path,
    task_text: str = "",
) -> dict:
    project_dir = Path(project_dir)
    if not project_dir.is_dir():
        return result(False, f"project dir not found: {project_dir}")

    detected = _detect_shape(project_dir)
    if detected is None:
        return result(
            False,
            "docs: no SSG config or bare docs/ tree found. Checked "
            "mkdocs.yml, docusaurus.config.*, .vitepress/config.*, "
            "conf.py, hugo.*, astro.config.*, _config.yml, and "
            "docs/ / content/ / src/content/ directories with ≥2 .md.",
        )
    shape, config_path = detected

    # Collect pages
    content_dirs = _first_content_candidates(project_dir)
    pages = _collect_pages(content_dirs)
    if shape == "sphinx":
        # Sphinx-discoverable pages — include any .rst in common roots
        for rel in ("docs", "source", "."):
            d = project_dir / rel
            if d.is_dir():
                pages.extend(d.glob("*.rst"))
    pages = list(dict.fromkeys(p.resolve() for p in pages))  # dedupe

    if not pages:
        return result(
            False,
            f"docs ({shape}): config found at "
            f"{config_path.name if config_path else '—'} but no "
            ".md/.mdx/.rst pages discovered in docs/ / content/ / "
            "src/content/ / src/pages/.",
        )

    # Homepage exists?
    home = _has_homepage(shape, project_dir)
    if home is None:
        return result(
            False,
            f"docs ({shape}): {len(pages)} page(s) present but no "
            "homepage. Expected index.md / intro.md / README.md / "
            "getting-started.md in a content dir (or index.rst for sphinx).",
        )

    # At least one page has meaningful content?
    content_pages = [p for p in pages if _page_has_content(Path(p))]
    if not content_pages:
        return result(
            False,
            f"docs ({shape}): {len(pages)} page(s) but none have "
            f">{_MIN_CONTENT_CHARS} chars of body prose (excluding "
            "frontmatter and headings). Deliverable is stub-only.",
        )

    rel_home = Path(home).relative_to(project_dir) if Path(home).is_relative_to(project_dir) else home
    return result(
        True,
        "",
        raw=(f"shape={shape}\n"
             f"config={config_path.name if config_path else '(bare)'}\n"
             f"pages={len(pages)}\n"
             f"content_pages={len(content_pages)}\n"
             f"home={rel_home}"),
    )


__all__ = ["docs_probe"]
