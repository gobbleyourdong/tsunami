"""Post-delivery probe (F-B1 mechanic + F-I4 content adoption).

Runs AFTER a tsunami worker finishes a row. Scans the delivered
`src/` directory for:

  - MechanicType imports from @engine/design/catalog  → mechanic adoption
  - Content-catalog-name references                   → content adoption
  - Placeholder names ("Enemy 1", "Boss A")           → generic_bleed
  - Non-catalog ad-hoc game logic markers             → vanilla_bleed

Writes JSON report to a caller-provided path. No model calls.
Inference-free — identical shape to tsunami/tests/test_game_content.py's
`_probe_app_tsx` but operating on a real deliverable.

Usage:
    python scripts/overnight/probe.py \
        --src <deliverable>/src \
        --content-essence 1986_legend_of_zelda \
        --out <telemetry>/probes/<run_id>.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Make tsunami importable.
REPO = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO))

from tsunami.game_content import (  # noqa: E402
    load_content_catalog, extract_content_names,
)


_MECHANIC_IMPORT_RE = re.compile(
    r"""import\s*\{([^}]+)\}\s*from\s*['"](?:@engine/design/catalog|[^'"]+engine/src/design/catalog)['"]""",
    re.DOTALL,
)


def _read_src_tree(src_dir: Path) -> str:
    """Concatenate every .ts/.tsx/.js/.jsx file body. Used for grep."""
    parts: list[str] = []
    if not src_dir.is_dir():
        return ""
    for ext in ("*.ts", "*.tsx", "*.js", "*.jsx"):
        for p in src_dir.rglob(ext):
            try:
                parts.append(p.read_text(errors="ignore"))
            except Exception:
                continue
    return "\n\n".join(parts)


def _read_gamedev_deliverable(project_dir: Path) -> str:
    """For gamedev scaffolds, the deliverable is public/game_definition.json
    (the DesignScript JSON emitted by emit_design). Include its text in
    the probe's content-adoption + mechanic-import scan.

    Round F revealed `probe: {'skipped': 'no src dir'}` for gamedev
    deliveries because the probe only looked at src/. For gamedev,
    content names like "Octorok" live INSIDE the design JSON's
    entities[].name field, not in TSX source. This function broadens
    the probe's surface area to catch those.
    """
    parts: list[str] = []
    for candidate in (
        project_dir / "public" / "game_definition.json",
        project_dir / "game_definition.json",
        project_dir / "public" / "assets.manifest.json",
    ):
        if candidate.is_file():
            try:
                parts.append(candidate.read_text(errors="ignore"))
            except Exception:
                continue
    return "\n\n".join(parts)


def scan_mechanic_imports(src_blob: str) -> list[str]:
    """Extract MechanicType names imported from @engine/design/catalog
    OR referenced via `"type": "<MechanicType>"` inside a compiled
    game_definition.json (Gap #27, 2026-04-20). Both sources count
    toward mechanic adoption — gamedev-only deliveries have no TSX
    imports, only JSON mechanic objects."""
    names: list[str] = []
    # TSX import pattern (React overlay or hybrid deliveries).
    for m in _MECHANIC_IMPORT_RE.finditer(src_blob):
        raw = m.group(1)
        for piece in raw.split(","):
            piece = piece.strip()
            if not piece:
                continue
            piece = piece.split(" as ")[0].strip()
            if piece and piece not in names:
                names.append(piece)
    # JSON "type": "X" pattern (compiled game_definition.json mechanics).
    # Only count CapitalCamelCase tokens — matches the MechanicType naming
    # convention in schema.ts and filters out common words that happen
    # to follow "type":.
    _JSON_MECH_RE = re.compile(r'"type"\s*:\s*"([A-Z][A-Za-z0-9_]+)"')
    # Pull the known set to filter — avoids counting "Player", "Enemy",
    # "Character" etc. which aren't MechanicType values.
    try:
        from tsunami.engine_catalog import KNOWN_MECHANIC_TYPES as _known
    except Exception:
        _known = None
    for m in _JSON_MECH_RE.finditer(src_blob):
        name = m.group(1)
        if _known is not None and name not in _known:
            continue
        if name not in names:
            names.append(name)
    return names


def scan_generic_bleed(src_blob: str) -> list[str]:
    """Return placeholder hits: Enemy N / Boss X / Monster1 / Level 2 ..."""
    patterns = [
        r"\bEnemy\s*[0-9A-Z]+\b",
        r"\benemy[0-9]+\b",
        r"\bBoss\s*[0-9A-Z]\b",
        r"\bMonster[0-9]+\b",
        r"\bItem[0-9]+\b",
        r"\bLevel\s*\d+\b",
        r"'monster'",
        r'"placeholder"',
    ]
    hits: list[str] = []
    for pat in patterns:
        hits.extend(re.findall(pat, src_blob))
    return hits


def scan_content_adoption(src_blob: str, essence_stem: str) -> dict:
    """Given a content-essence stem, grep for its named content.

    Gap #29 (Round R 2026-04-20): wave emits content names as
    `"link"`, `"old_man"` (lowercase snake_case) while catalog has
    `"Link"`, `"Old Man"` (CapitalCamelCase + spaces). Case-sensitive
    exact match missed 11 hits in Round R. Fix: also match normalized
    variants — lowercase-with-underscores, case-insensitive exact,
    and camelCase boundary scan."""
    body = load_content_catalog(essence_stem)
    if not body:
        return {
            "essence": essence_stem,
            "catalog_names": {},
            "adopted": {},
            "named_distinct": 0,
            "named_total": 0,
            "adoption_rate": 0.0,
        }
    catalog = extract_content_names(body)
    adopted: dict[str, dict[str, int]] = {}
    distinct_seen = 0
    total_count = 0
    total_known = 0
    for cat, names in catalog.items():
        cat_hits: dict[str, int] = {}
        for name in names:
            if len(name) < 3:
                continue
            total_known += 1
            # Build variant set: exact, lowercase-underscore, lowercase-hyphen.
            lc_us = re.sub(r'\s+', '_', name.lower())
            lc_hy = re.sub(r'\s+', '-', name.lower())
            variants = {name, lc_us, lc_hy}
            # Strip quoting/punct edge cases — check each variant with
            # word-boundary OR quote-boundary.
            hits = 0
            for v in variants:
                # Word-boundary first (matches "Link," or "Link.")
                hits += len(re.findall(rf"\b{re.escape(v)}\b", src_blob))
            if hits:
                cat_hits[name] = hits
                distinct_seen += 1
                total_count += hits
        if cat_hits:
            adopted[cat] = cat_hits
    adoption_rate = distinct_seen / total_known if total_known else 0.0
    return {
        "essence": essence_stem,
        "catalog_names": catalog,
        "adopted": adopted,
        "named_distinct": distinct_seen,
        "named_total": total_count,
        "adoption_rate": adoption_rate,
    }


def run(src_dir: Path, content_essence: str = "") -> dict:
    """Scan src_dir + any gamedev deliverable; return full probe report.

    For React-shape deliveries, src_dir is the project's src/ folder.
    For gamedev, src_dir can be the project root (probe expands to
    public/game_definition.json). We concat both surfaces so a hybrid
    or misclassified delivery isn't missed — the scan is cheap.
    """
    src_text = _read_src_tree(src_dir)
    # Also scan gamedev deliverable — src_dir's parent is the project
    # root; look for game_definition.json and assets manifest there.
    project_dir = src_dir.parent if src_dir.name == "src" else src_dir
    gamedev_text = _read_gamedev_deliverable(project_dir)
    src = src_text + "\n\n" + gamedev_text

    mechanics = scan_mechanic_imports(src)
    generic = scan_generic_bleed(src)
    content = scan_content_adoption(src, content_essence) if content_essence else None

    report = {
        "src_dir": str(src_dir),
        "project_dir": str(project_dir),
        "src_bytes": len(src_text),
        "gamedev_deliverable_bytes": len(gamedev_text),
        "scan_surface_bytes": len(src),
        "mechanic_imports": mechanics,
        "mechanic_import_count": len(mechanics),
        "generic_bleed": generic,
        "generic_bleed_count": len(generic),
    }
    if content is not None:
        report["content"] = content
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", required=True, help="path to deliverable src/")
    parser.add_argument("--content-essence", default="",
                        help="essence stem for F-I4 content probe (optional)")
    parser.add_argument("--out", default="-",
                        help="output JSON path; '-' = stdout")
    args = parser.parse_args()

    report = run(Path(args.src).expanduser(), args.content_essence)
    rendered = json.dumps(report, indent=2)
    if args.out == "-":
        print(rendered)
    else:
        out = Path(args.out).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(rendered)
        print(f"Wrote {out}")


if __name__ == "__main__":
    main()
