"""F-A1 — Report drift between catalog_proposals.md and the engine catalog.

Parses `scaffolds/.claude/game_essence/catalog_proposals.md` for
mechanics promoted at ≥3 cites and compares against the shipped
MechanicType union in `scaffolds/engine/src/design/schema.ts`.

Modes:
  --check          (default)  report shipped/missing/drift counts + names
  --json                      emit a machine-readable JSON report
  --stub-schema               emit a TS snippet to append to schema.ts's
                              MechanicType union (commented header + the
                              missing `| 'X'` lines)
  --stub-catalog               emit skeleton CatalogEntry objects for
                              catalog.ts — 'TODO' descriptions, source-
                              game comments, ready for a human to fill

`--apply` intentionally NOT implemented here. catalog.ts's CatalogEntry
carries description, example_params, needs_mechanic_types, tier, and
common_patches — generating placeholders loses the hand-curation value.
The stubs are copy-paste-ready; a human completes the entries.

Sigma v9.1 C5 falsifier: if the shipped catalog's mechanic count never
grows to match the promoted list over multiple audit cycles, promotion
evidence isn't load-bearing on delivery — retract the whole promotion
framework.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import OrderedDict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
PROPOSALS_MD = (REPO / "scaffolds" / ".claude" / "game_essence"
                / "catalog_proposals.md")
SCHEMA_TS = (REPO / "scaffolds" / "engine" / "src" / "design" / "schema.ts")
CATALOG_TS = (REPO / "scaffolds" / "engine" / "src" / "design" / "catalog.ts")


def parse_promoted(proposals_md: Path) -> "OrderedDict[str, list[str]]":
    r"""Return an ordered dict of promoted-mechanic-name → [source_games].

    Iterates every ``| `Name` | 3 | A + B + C |`` row under a
    ``### Pass N promotions`` heading.
    """
    text = proposals_md.read_text()
    out: "OrderedDict[str, list[str]]" = OrderedDict()
    # Match rows like: | `DestructibleTerrain` | 3 | SMB + Zelda + Super Metroid |
    # Also matches the extra-column variant: | `X` | 3 | A + B + C (with `dimensionality` param) |
    row_re = re.compile(
        r"^\|\s*`([A-Z][A-Za-z0-9_]+)`\s*\|\s*3\s*\|\s*([^|]+)\|",
        re.MULTILINE,
    )
    for m in row_re.finditer(text):
        name = m.group(1)
        sources = [s.strip() for s in m.group(2).split("+")]
        if name not in out:
            out[name] = sources
    return out


def parse_shipped(schema_ts: Path) -> set[str]:
    """Extract the MechanicType string-literal union from schema.ts."""
    text = schema_ts.read_text()
    # Find the block from `export type MechanicType =` to the next
    # top-level `export` or a blank-line-followed-by-non-`|` terminator.
    m = re.search(r"export type MechanicType\s*=\s*\n((?:.*\n)*?)(?=^\S|\Z)",
                  text, re.MULTILINE)
    if not m:
        return set()
    block = m.group(1)
    names = set(re.findall(r"'([A-Z][A-Za-z0-9_]+)'", block))
    return names


def drift_report(proposals_md: Path = PROPOSALS_MD,
                 schema_ts: Path = SCHEMA_TS) -> dict:
    promoted = parse_promoted(proposals_md)
    shipped = parse_shipped(schema_ts)
    missing = OrderedDict(
        (name, sources) for name, sources in promoted.items()
        if name not in shipped
    )
    grandfathered = sorted(shipped - set(promoted.keys()))
    return {
        "promoted_count": len(promoted),
        "shipped_count": len(shipped),
        "missing_count": len(missing),
        "grandfathered_count": len(grandfathered),
        "missing_mechanics": [
            {"name": n, "sources": s} for n, s in missing.items()
        ],
        # v0 / v0.2 / v1.0 mechanics that shipped BEFORE the ≥3-cite
        # discipline existed — still valid, just not annotated with
        # source-game provenance in catalog_proposals.md. Not drift.
        "grandfathered_in_schema": grandfathered,
        # Back-compat alias used by tests written against v1 naming:
        "redundant_in_schema": grandfathered,
        "shipped_mechanics": sorted(shipped),
    }


def render_check(rep: dict) -> str:
    lines = [
        f"Promotion audit — {PROPOSALS_MD}",
        f"  vs            {SCHEMA_TS}",
        "",
        f"  promoted (≥3 cites):       {rep['promoted_count']}",
        f"  shipped (in schema):       {rep['shipped_count']}",
        f"  missing (not yet shipped): {rep['missing_count']}",
        f"  grandfathered (v0/v1):     {rep['grandfathered_count']}",
        "",
    ]
    if rep["grandfathered_in_schema"]:
        lines.append("Grandfathered (v0/v1 mechanics shipped before ≥3-cite rule):")
        for n in rep["grandfathered_in_schema"]:
            lines.append(f"  {n}")
        lines.append("")
    lines.append(
        f"Missing ({rep['missing_count']}) — ready for catalog.ts PR:"
    )
    for m in rep["missing_mechanics"]:
        sources = ", ".join(m["sources"][:3])
        if len(m["sources"]) > 3:
            sources += f" (+{len(m['sources'])-3} more)"
        lines.append(f"  {m['name']:32} {sources}")
    return "\n".join(lines)


def render_stub_schema(rep: dict) -> str:
    """Emit a TS snippet to paste into MechanicType union."""
    out = [
        "  // F-A1 promotion batch — paste below the last v* comment in",
        f"  // schema.ts's MechanicType union. {rep['missing_count']} new entries.",
    ]
    # Group into chunks of 4 for readability
    missing_names = [m["name"] for m in rep["missing_mechanics"]]
    chunk_size = 4
    for i in range(0, len(missing_names), chunk_size):
        chunk = missing_names[i:i + chunk_size]
        literals = " | ".join(f"'{n}'" for n in chunk)
        out.append(f"  | {literals}")
    return "\n".join(out)


def render_stub_catalog(rep: dict) -> str:
    """Emit skeleton CatalogEntry objects for catalog.ts — human fills."""
    out = ["  // F-A1 promotion batch — skeletons. Fill TODO fields,",
           "  // then paste into CATALOG record in catalog.ts.", ""]
    for m in rep["missing_mechanics"]:
        name = m["name"]
        sources = ", ".join(m["sources"])
        out.extend([
            f"  {name}: {{",
            f"    type: '{name}',",
            f"    description: 'TODO — sourced from: {sources}',",
            f"    example_params: {{}},  // TODO",
            f"    tier: 'v1_core',        // TODO",
            f"  }},",
            "",
        ])
    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode", choices=["check", "json", "stub-schema", "stub-catalog"],
        default="check",
    )
    parser.add_argument("--proposals", default=str(PROPOSALS_MD))
    parser.add_argument("--schema", default=str(SCHEMA_TS))
    parser.add_argument(
        "--exit-nonzero-on-drift", action="store_true",
        help="CI mode — exit 1 when missing_count > 0 (use to block merge "
             "of proposals without matching schema expansion)",
    )
    args = parser.parse_args()

    rep = drift_report(Path(args.proposals), Path(args.schema))

    if args.mode == "check":
        print(render_check(rep))
    elif args.mode == "json":
        print(json.dumps(rep, indent=2))
    elif args.mode == "stub-schema":
        print(render_stub_schema(rep))
    elif args.mode == "stub-catalog":
        print(render_stub_catalog(rep))

    if args.exit_nonzero_on_drift and rep["missing_count"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
