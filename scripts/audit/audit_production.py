#!/usr/bin/env python3
"""Production-firing audit — reference implementation of sigma v10.

Each row in scripts/audit/fix_registry.jsonl names a fix + a
signature string it should produce when it fires (gate error text,
log line, tailored reject, etc.). This script scans recent session
JSONL files in workspace/.history for each signature and reports:

  - how many sessions hit each signature (≥1 = fix is alive)
  - which fixes have expect_nonzero=True but zero hits (DEAD CODE)
  - which fixes are refactors / predicate-only (expect_nonzero=False,
    verified via unit tests not log mining)

Origin: discovered 2026-04-21 overnight campaign; the protocol was
promoted to the canonical Sigma Method as the new v10 principle
"Production-Firing Audit." The motivating observation: structural
fixes that key on a brittle predicate can silently stop firing after
an upstream change. Unit tests keep passing because the fixture
satisfies the predicate; production traces never do. This tool
closes the fixture-vs-production gap.

Usage:
  python3 scripts/audit/audit_production.py                # last 80 sessions
  python3 scripts/audit/audit_production.py --since 200    # wider window
  python3 scripts/audit/audit_production.py --slug scaffold_first_gate_hoist
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent.parent.parent
HISTORY = REPO / "workspace" / ".history"
REGISTRY = REPO / "scripts" / "audit" / "fix_registry.jsonl"


@dataclass
class AuditRow:
    slug: str
    sha: str
    signature: str
    expect_nonzero: bool
    hits: int = 0
    sessions_hit: int = 0
    note: str = ""


def load_registry() -> list[AuditRow]:
    rows: list[AuditRow] = []
    if not REGISTRY.is_file():
        return rows
    with REGISTRY.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except Exception:
                continue
            rows.append(AuditRow(
                slug=data.get("slug", ""),
                sha=data.get("sha", ""),
                signature=data.get("signature", ""),
                expect_nonzero=bool(data.get("expect_nonzero", True)),
                note=data.get("note", ""),
            ))
    return rows


def scan_sessions(rows: list[AuditRow], window: int) -> None:
    """Walk the last `window` session JSONLs and increment each row's
    hits/sessions_hit counts based on signature matches."""
    sessions = sorted(HISTORY.glob("session_*.jsonl"))
    sessions = sessions[-window:] if window > 0 else sessions
    for session_path in sessions:
        try:
            with session_path.open() as f:
                raw = f.read()
        except OSError:
            continue
        for row in rows:
            if not row.signature:
                continue
            n = raw.count(row.signature)
            if n > 0:
                row.hits += n
                row.sessions_hit += 1


def render_report(rows: list[AuditRow], window: int) -> str:
    """Tabular report. Flags dead code loud — a signature with
    expect_nonzero=True but zero sessions_hit across the window is
    the 2026-04-21 failure mode we're here to prevent."""
    out = [
        f"Kelp production-firing audit — window={window} sessions",
        f"History: {HISTORY}",
        "",
        f"{'slug':<42s} {'sha':<10s} {'status':<12s} {'sessions':>8s}  note",
        "-" * 120,
    ]
    dead = []
    live = []
    skip = []
    for row in rows:
        if not row.expect_nonzero:
            status = "refactor"
            skip.append(row)
        elif row.sessions_hit == 0:
            status = "DEAD"
            dead.append(row)
        else:
            status = "live"
            live.append(row)
        out.append(
            f"{row.slug:<42s} {row.sha:<10s} {status:<12s} {row.sessions_hit:>8d}  {row.note[:60]}"
        )
    out.extend([
        "",
        f"Summary: {len(live)} live, {len(dead)} DEAD, {len(skip)} refactor-only",
    ])
    if dead:
        out.append("")
        out.append("DEAD FIXES (expect_nonzero=True, zero sessions hit):")
        for row in dead:
            out.append(f"  - {row.slug} (sha {row.sha}): {row.signature!r}")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--since", type=int, default=80,
        help="window of most-recent sessions to scan (default 80)",
    )
    parser.add_argument(
        "--slug", default="",
        help="only audit one fix by slug (default: all)",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="emit structured JSON instead of a report",
    )
    args = parser.parse_args(argv)

    rows = load_registry()
    if args.slug:
        rows = [r for r in rows if r.slug == args.slug]
        if not rows:
            print(f"No registry entry for slug: {args.slug}", file=sys.stderr)
            return 2

    scan_sessions(rows, args.since)

    if args.json:
        payload = [
            {
                "slug": r.slug, "sha": r.sha, "signature": r.signature,
                "expect_nonzero": r.expect_nonzero, "hits": r.hits,
                "sessions_hit": r.sessions_hit, "note": r.note,
            }
            for r in rows
        ]
        print(json.dumps(payload, indent=2))
    else:
        print(render_report(rows, args.since))

    # Exit non-zero if any fix is dead — lets CI / post-push hooks flag
    dead_count = sum(
        1 for r in rows if r.expect_nonzero and r.sessions_hit == 0
    )
    return 1 if dead_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
