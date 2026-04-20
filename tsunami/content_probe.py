"""Post-delivery content probe (F-B1 mechanic + F-I4 content adoption).

Runs AFTER a tsunami worker finishes a row. Scans a delivered project
(src/ tree plus any gamedev-specific artifacts) for:

  - MechanicType imports from @engine/design/catalog  → mechanic adoption
  - Content-catalog-name references                   → content adoption
  - Placeholder names ("Enemy 1", "Boss A")           → generic_bleed
  - Non-catalog ad-hoc game logic markers             → vanilla_bleed
  - Scaffold customization vs seed                    → engagement signal

Writes a JSON report to a caller-provided path. No model calls —
inference-free. Matches the shape of tsunami/tests/test_game_content.py's
``_probe_app_tsx`` but operating on a real deliverable.

History: originally lived at ``scripts/overnight/probe.py`` alongside
the overnight harness. Promoted into the ``tsunami`` package so the
worker, morning consolidator, delivery gates, and tests import from
one canonical path.

Usage:
    python -m tsunami.content_probe \\
        --src <deliverable>/src \\
        --content-essence 1986_legend_of_zelda \\
        --out <telemetry>/probes/<run_id>.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from tsunami.game_content import (
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
    """For gamedev scaffolds, include any gamedev-specific deliverable
    payload (JSON / TS scene wiring) in the scan surface.

    Two deliverable shapes are supported:

      legacy flow — public/game_definition.json (DesignScript emitted
      by the wave's emit_design tool)

      scaffold flow — data/*.json (entities, items, mechanics, rooms,
      …) + src/scenes/*.ts (wave-edited scene files). The scaffolds
      seed ships with these; the wave edits them in place.

    Round F revealed ``probe: {'skipped': 'no src dir'}`` for legacy
    gamedev deliveries because the probe only looked at src/. The
    scaffold flow landed 2026-04-20 with a different artifact shape;
    this function is the one place that unions both.
    """
    parts: list[str] = []
    # Legacy paths
    legacy_candidates = (
        project_dir / "public" / "game_definition.json",
        project_dir / "game_definition.json",
        project_dir / "public" / "assets.manifest.json",
    )
    for candidate in legacy_candidates:
        if candidate.is_file():
            try:
                parts.append(candidate.read_text(errors="ignore"))
            except Exception:
                continue
    # Scaffold flow — glob data/*.json (entities/items/mechanics/rooms/
    # levels/characters/moves/rules/config — all variants)
    data_dir = project_dir / "data"
    if data_dir.is_dir():
        for jf in sorted(data_dir.glob("*.json")):
            try:
                parts.append(jf.read_text(errors="ignore"))
            except Exception:
                continue
    # Scaffold flow — the wave often wires mechanics in src/scenes/*.ts,
    # which _read_src_tree already picks up if src_dir points at the
    # project root. If src_dir was project/src (canonical), include
    # scenes/*.ts here as a safety net (cheap double-read at worst).
    scenes_dir = project_dir / "src" / "scenes"
    if scenes_dir.is_dir():
        for ts in sorted(scenes_dir.rglob("*.ts")):
            try:
                parts.append(ts.read_text(errors="ignore"))
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


# ---------------------------------------------------------------------------
# Scaffold-customization scanner (separate metric from content_adoption —
# preserves the Round-L→T benchmark continuity). Measures HOW MUCH the
# wave edited the data-driven gamedev scaffold vs. the seed it was
# handed, so "wave launched scaffold and shipped verbatim" reads
# distinct from "wave customized one entity name" from "wave rebuilt
# half the rooster."
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SEED_DIR_ROOT = _REPO_ROOT / "scaffolds" / "gamedev"


def _detect_scaffold_kind(project_dir: Path) -> str | None:
    """Return the scaffold kind (e.g. 'action_adventure') from
    package.json's name field, or None if the project doesn't follow
    the ``gamedev-<kind>-scaffold`` convention."""
    pkg = project_dir / "package.json"
    if not pkg.is_file():
        return None
    try:
        data = json.loads(pkg.read_text(encoding="utf-8", errors="replace"))
    except (json.JSONDecodeError, OSError):
        return None
    name = data.get("name", "")
    m = re.match(r"gamedev-([a-z0-9_-]+)-scaffold$", name)
    if not m:
        return None
    kind = m.group(1).replace("-", "_")
    if (_SEED_DIR_ROOT / kind).is_dir():
        return kind
    return None


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _bucket_for_ratio(ratio: float) -> str:
    """Map customization ratio (0.0 → 1.0) to a readable bucket so
    the morning report can split runs without eyeballing floats."""
    if ratio <= 0.0:
        return "untouched"
    if ratio < 0.15:
        return "surface_edit"
    if ratio < 0.55:
        return "substantive"
    return "heavy_rewrite"


def scan_scaffold_customization(project_dir: Path,
                                seed_kind: str | None = None) -> dict:
    """Compare the project's ``data/*.json`` + ``src/scenes/*.ts`` to
    its scaffold seed. Proves the wave actually customized the
    scaffold rather than shipping the seed verbatim.

    Returns::

        {
          "applicable":          bool,       # false when kind is unknown
          "seed_kind":           str | None,
          "data_files_total":    int,
          "data_files_modified": int,
          "modified_files":      [str, …],   # filenames only
          "net_lines_added":     int,        # project lines − seed lines
          "net_entities_added":  int,        # rough: top-level keys added
          "scenes_modified":     bool,       # any src/scenes/*.ts differs
          "customization_ratio": float,      # 0.0 → 1.0 fraction modified
          "customization_bucket": str,       # untouched|surface_edit|
                                             #   substantive|heavy_rewrite
        }
    """
    if seed_kind is None:
        seed_kind = _detect_scaffold_kind(project_dir)
    if seed_kind is None:
        return {
            "applicable": False,
            "seed_kind": None,
            "data_files_total": 0,
            "data_files_modified": 0,
            "modified_files": [],
            "net_lines_added": 0,
            "net_entities_added": 0,
            "scenes_modified": False,
            "customization_ratio": 0.0,
            "customization_bucket": "untouched",
        }

    project_data = project_dir / "data"
    seed_data = _SEED_DIR_ROOT / seed_kind / "data"

    # Data-file diff
    data_files = sorted(project_data.glob("*.json")) if project_data.is_dir() else []
    modified: list[str] = []
    project_lines = 0
    seed_lines = 0
    project_top_keys = 0
    seed_top_keys = 0
    for pfile in data_files:
        try:
            pbytes = pfile.read_bytes()
        except OSError:
            continue
        project_lines += pbytes.count(b"\n")
        # Top-level key count (rough entity cardinality)
        try:
            parsed = json.loads(pbytes.decode("utf-8", errors="replace"))
            if isinstance(parsed, dict):
                # Prefer nested archetypes/entities/items/… if present
                for key in ("archetypes", "entities", "items", "mechanics",
                            "rooms", "levels", "characters", "moves", "rules"):
                    sub = parsed.get(key)
                    if isinstance(sub, dict):
                        project_top_keys += len(sub)
                        break
                    if isinstance(sub, list):
                        project_top_keys += len(sub)
                        break
                else:
                    project_top_keys += len(parsed)
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass

        sfile = seed_data / pfile.name
        if sfile.is_file():
            try:
                sbytes = sfile.read_bytes()
            except OSError:
                sbytes = b""
            seed_lines += sbytes.count(b"\n")
            try:
                sparsed = json.loads(sbytes.decode("utf-8", errors="replace"))
                if isinstance(sparsed, dict):
                    for key in ("archetypes", "entities", "items", "mechanics",
                                "rooms", "levels", "characters", "moves", "rules"):
                        sub = sparsed.get(key)
                        if isinstance(sub, dict):
                            seed_top_keys += len(sub)
                            break
                        if isinstance(sub, list):
                            seed_top_keys += len(sub)
                            break
                    else:
                        seed_top_keys += len(sparsed)
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass
            if _sha256_bytes(pbytes) != _sha256_bytes(sbytes):
                modified.append(pfile.name)
        else:
            # New file the wave added — counts as modification.
            modified.append(pfile.name)

    # Scene diff — any src/scenes/*.ts differs from seed
    scenes_modified = False
    project_scenes_dir = project_dir / "src" / "scenes"
    seed_scenes_dir = _SEED_DIR_ROOT / seed_kind / "src" / "scenes"
    if project_scenes_dir.is_dir():
        for sfile in project_scenes_dir.rglob("*.ts"):
            rel = sfile.relative_to(project_scenes_dir)
            seed_counterpart = seed_scenes_dir / rel
            try:
                pbytes = sfile.read_bytes()
            except OSError:
                continue
            if not seed_counterpart.is_file():
                scenes_modified = True
                break
            try:
                sbytes = seed_counterpart.read_bytes()
            except OSError:
                sbytes = b""
            if _sha256_bytes(pbytes) != _sha256_bytes(sbytes):
                scenes_modified = True
                break

    total = len(data_files) or 1
    ratio = len(modified) / total
    return {
        "applicable": True,
        "seed_kind": seed_kind,
        "data_files_total": len(data_files),
        "data_files_modified": len(modified),
        "modified_files": modified,
        "net_lines_added": project_lines - seed_lines,
        "net_entities_added": project_top_keys - seed_top_keys,
        "scenes_modified": scenes_modified,
        "customization_ratio": round(ratio, 3),
        "customization_bucket": _bucket_for_ratio(ratio),
    }


def run(src_dir: Path, content_essence: str = "") -> dict:
    """Scan src_dir + any gamedev deliverable; return full probe report.

    For React-shape deliveries, src_dir is the project's src/ folder.
    For gamedev, src_dir can be the project root (probe expands to
    public/game_definition.json AND data/*.json). We concat both
    surfaces so a hybrid or misclassified delivery isn't missed — the
    scan is cheap.
    """
    src_text = _read_src_tree(src_dir)
    # Also scan gamedev deliverable — src_dir's parent is the project
    # root; look for game_definition.json, data/*.json, and scenes.
    project_dir = src_dir.parent if src_dir.name == "src" else src_dir
    gamedev_text = _read_gamedev_deliverable(project_dir)
    src = src_text + "\n\n" + gamedev_text

    mechanics = scan_mechanic_imports(src)
    generic = scan_generic_bleed(src)
    content = scan_content_adoption(src, content_essence) if content_essence else None
    customization = scan_scaffold_customization(project_dir)

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
    report["customization"] = customization
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
