"""Offline morning aggregator (sigma audit §17.6).

Reads overnight telemetry and produces a coverage/stall/retraction/
cold-start/force-miss/probe-saturation/budget/gap report. NO model
calls — pure stdlib + the existing module aggregators.

Distinct from the tsunami-driven consolidator (§17.6 proper), which
is a tsunami-wave run against a specific prompt. This offline version
is the "before-coffee" quick glance: operator runs it with zero cost
when the overnight ends, and only spins up the wave-driven consolidator
if the numbers warrant deeper analysis.

Usage:
    python scripts/overnight/morning_report.py
    python scripts/overnight/morning_report.py \
        --root /tmp/live_zelda_revalidation \
        --telemetry /tmp/live_zelda_revalidation/telemetry \
        --out /tmp/live_zelda_revalidation/morning.md
    python scripts/overnight/morning_report.py --json  # machine-readable
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))

# Default locations (home-dir telemetry when run against the live
# rolling state; per-run-root when auditing one overnight).
_DEFAULT_ROOT = Path.home() / ".tsunami" / "overnight"
_DEFAULT_TELEMETRY = Path.home() / ".tsunami" / "telemetry"


def _iter_jsonl(path: Path):
    if not path.is_file():
        return
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


# ────────────────── Section builders ──────────────────

def section_coverage(runs_path: Path) -> dict:
    """§1 — per-axis delivery/timeout/error breakdown."""
    out: dict = {
        "total": 0,
        "by_exit_reason": Counter(),
        "by_expected_scaffold": Counter(),
        "by_expected_genre": Counter(),
        "delivered": 0,
        "timeout": 0,
        "error": 0,
    }
    rows = list(_iter_jsonl(runs_path))
    for r in rows:
        out["total"] += 1
        reason = r.get("exit_reason", "")
        out["by_exit_reason"][reason] += 1
        row_env = r.get("row", {})
        scaf = row_env.get("expected_scaffold", "") or "?"
        out["by_expected_scaffold"][scaf] += 1
        genre = row_env.get("expected_genre", "") or "?"
        out["by_expected_genre"][genre] += 1
        if reason == "message_result":
            out["delivered"] += 1
        elif reason == "timeout":
            out["timeout"] += 1
        elif reason and reason.startswith("error"):
            out["error"] += 1
    return out


def section_stall(telemetry_dir: Path) -> dict:
    """§2 — per-domain fallback stats via routing_telemetry.stall_report."""
    from tsunami.routing_telemetry import stall_report
    return stall_report(log_dir=telemetry_dir)


def section_retractions(telemetry_dir: Path) -> dict:
    """§3 — kind × (declared→detected) counts.

    Read ~/.tsunami/retractions.jsonl or local equivalent.
    """
    p = telemetry_dir / "retractions.jsonl"
    if not p.is_file():
        p = Path.home() / ".tsunami" / "retractions.jsonl"
    rows = list(_iter_jsonl(p))
    if not rows:
        return {"total": 0, "by_kind": {}, "top_pairs": []}
    by_kind: dict[str, list[dict]] = {}
    pair_counter: Counter = Counter()
    for r in rows:
        kind = r.get("kind", "")
        by_kind.setdefault(kind, []).append(r)
        pair_counter[(
            kind,
            r.get("declared", ""),
            r.get("detected", ""),
        )] += 1
    return {
        "total": len(rows),
        "by_kind": {k: len(v) for k, v in by_kind.items()},
        "top_pairs": pair_counter.most_common(5),
    }


def section_cold_start(telemetry_dir: Path, threshold: int = 30) -> dict:
    """§4 — per-doctrine delivery_count, segregated by cold-start bar."""
    from tsunami.doctrine_history import picks_by_domain
    path = telemetry_dir / "doctrine_history.jsonl"
    by = picks_by_domain(path if path.is_file() else None)
    out: dict = {"cold_start": {}, "plateau": {}}
    for domain, counter in by.items():
        cold = {n: c for n, c in counter.items() if c < threshold}
        plateau = {n: c for n, c in counter.items() if c >= threshold}
        out["cold_start"][domain] = sorted(cold.items(), key=lambda kv: kv[1])
        out["plateau"][domain] = sorted(plateau.items(), key=lambda kv: -kv[1])
    return out


def section_force_miss(telemetry_dir: Path) -> dict:
    """§5 — force_miss (forced, actual) distribution."""
    from tsunami.routing_telemetry import force_miss_report
    return force_miss_report(log_dir=telemetry_dir)


def section_probe_saturation(probes_dir: Path) -> dict:
    """§6 — dead-letter doctrines: adoption_rate < 0.20 over ≥N runs."""
    if not probes_dir.is_dir():
        return {
            "total_probes": 0,
            "content_essences_sampled": 0,
            "dead_letters": [],
            "mechanic_imports_mean": 0,
        }
    mechanic_rates: dict[str, list[float]] = {}
    content_rates: dict[str, list[float]] = {}
    total = 0
    for p in probes_dir.glob("*.json"):
        try:
            rep = json.loads(p.read_text())
        except Exception:
            continue
        total += 1
        # mechanic adoption per genre / scaffold — we don't have the
        # source metadata here; leave bucketing by run_id
        m_imports = rep.get("mechanic_import_count", 0) or 0
        # generic_bleed_count penalty — count as anti-adoption
        mechanic_rates.setdefault("all", []).append(m_imports)
        content = rep.get("content") or {}
        rate = content.get("adoption_rate", 0.0)
        essence = content.get("essence", "unknown")
        if essence and essence != "unknown":
            content_rates.setdefault(essence, []).append(rate)
    dead_letters: list[dict] = []
    for essence, rates in content_rates.items():
        if len(rates) >= 3:
            avg = statistics.mean(rates)
            if avg < 0.20:
                dead_letters.append({
                    "essence": essence, "n": len(rates),
                    "avg_adoption": round(avg, 3),
                })
    return {
        "total_probes": total,
        "content_essences_sampled": len(content_rates),
        "dead_letters": dead_letters,
        "mechanic_imports_mean": (
            round(statistics.mean(mechanic_rates.get("all", [0])), 2)
            if mechanic_rates else 0
        ),
    }


def section_budget(runs_path: Path) -> dict:
    """§7 — directive-bytes percentiles + cache-hit proxy."""
    rows = list(_iter_jsonl(runs_path))
    dirs = [r.get("directive_bytes") for r in rows if r.get("directive_bytes")]
    if not dirs:
        return {"n": len(rows), "directive_bytes_available": 0}
    dirs.sort()
    return {
        "n": len(rows),
        "directive_bytes_available": len(dirs),
        "p50": dirs[len(dirs)//2],
        "p90": dirs[int(len(dirs)*0.9)],
        "max": dirs[-1],
    }


def section_quality(telemetry_dir: Path) -> dict:
    """§6b — per-delivery quality signals via quality_telemetry."""
    from tsunami.quality_telemetry import quality_report
    path = telemetry_dir / "deliverable_quality.jsonl"
    if not path.is_file():
        return {"total_deliveries": 0}
    return quality_report(path)


def section_new_gaps(stall: dict, coverage: dict | None = None) -> list[dict]:
    """§8 — top 5 corpus additions implied by the stall table.

    Style-domain fall-throughs on gamedev scaffolds are EXPECTED (F-A3
    gates style injection off when scaffold=gamedev; genre takes over).
    Skip that false-positive.
    """
    gaps: list[dict] = []
    # When no runs have completed (runs.jsonl empty), we're in in-flight
    # preview mode — suppress gap suggestions since there's no signal
    # volume. Show gaps only when ≥1 run has shipped.
    total_runs = (coverage or {}).get("total", 0)
    if total_runs == 0:
        return []
    gamedev_heavy = False
    if coverage and coverage.get("by_expected_scaffold", {}).get("gamedev", 0) > 0:
        # If ≥50% of runs are gamedev, style fall-throughs are expected
        gamedev_heavy = (
            coverage["by_expected_scaffold"].get("gamedev", 0) / total_runs > 0.5
        )
    for domain, data in stall.items():
        if data.get("default_rate", 0) < 0.3:
            continue
        if domain == "style" and gamedev_heavy:
            continue  # style is scaffold-gated; gamedev runs skip it by design
        gaps.append({
            "domain": domain,
            "evidence": f"{data['default_count']}/{data['total']} calls "
                        f"fell through to default ({data['default_rate']:.0%})",
            "proposed_action": f"extend {domain} keyword map or add new "
                               f"{domain} doctrine file",
            "would_falsify": (
                f"if the next overnight has {domain} default_rate < 10%, "
                f"the keyword additions worked"
            ),
        })
    gaps.sort(key=lambda g: -stall[g["domain"]]["default_count"])
    return gaps[:5]


# ────────────────── Renderers ──────────────────

def render_md(report: dict) -> str:
    lines = [
        "# Morning report (offline)",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}Z",
        f"Root:      {report['config']['root']}",
        f"Telemetry: {report['config']['telemetry_dir']}",
        f"Probes:    {report['config']['probes_dir']}",
        "",
    ]

    # §1
    c = report["coverage"]
    lines += [
        "## §1 Coverage",
        "",
        f"- Total runs: **{c['total']}**",
        f"- Delivered:  {c['delivered']}",
        f"- Timeout:    {c['timeout']}",
        f"- Error:      {c['error']}",
        "",
    ]
    if c["by_expected_scaffold"]:
        lines.append("| scaffold | count |")
        lines.append("|---|---:|")
        for k, v in sorted(c["by_expected_scaffold"].items(),
                           key=lambda kv: -kv[1]):
            lines.append(f"| {k} | {v} |")
        lines.append("")

    # §2
    s = report["stall"]
    lines.append("## §2 Stall table (routing fall-throughs)")
    lines.append("")
    if not s:
        lines.append("_(no telemetry — set TSUNAMI_ROUTING_TELEMETRY=1)_")
    else:
        for domain, data in sorted(s.items()):
            lines.append(
                f"### {domain}: {data['default_count']}/{data['total']} "
                f"fall-through ({data['default_rate']:.1%})"
            )
            if data["top_keywords"]:
                for name, n in data["top_keywords"][:5]:
                    lines.append(f"- {name}: {n}")
            lines.append("")

    # §3
    r = report["retractions"]
    lines.append("## §3 Retractions (v9.1 C2)")
    lines.append("")
    if r["total"] == 0:
        lines.append("_(no retractions yet — needs F-D1 live integration)_")
    else:
        lines.append(f"Total: {r['total']}")
        lines.append("")
        for pair, n in r["top_pairs"]:
            lines.append(f"- ({pair[0]}) {pair[1]!r} → {pair[2]!r}: {n}")
    lines.append("")

    # §4
    cs = report["cold_start"]
    lines.append("## §4 Cold-start segregation (v9.1 C1)")
    lines.append("")
    any_cs = False
    for domain, items in cs["cold_start"].items():
        if items:
            any_cs = True
            lines.append(f"### {domain} — cold-start (< 30 deliveries)")
            for name, n in items[:10]:
                lines.append(f"- {name}: {n}")
            lines.append("")
    if not any_cs:
        lines.append("_(nothing cold-start-flagged — all doctrines at <30 deliveries or none seen)_")
        lines.append("")

    # §5
    fm = report["force_miss"]
    lines.append("## §5 Force-miss ledger (F-C4)")
    lines.append("")
    if fm["total"] == 0:
        lines.append("_(no force_miss events captured)_")
    else:
        lines.append(f"Total: {fm['total']}")
        for pair, n in fm["top_pairs"][:5]:
            lines.append(f"- forced={pair[0]!r} → actual={pair[1]!r}: {n}")
    lines.append("")

    # §6
    ps = report["probe_saturation"]
    lines.append("## §6 Probe saturation / dead-letter doctrines")
    lines.append("")
    lines.append(f"Probes sampled: {ps['total_probes']}")
    lines.append(f"Mechanic imports (mean): {ps['mechanic_imports_mean']}")
    if ps["dead_letters"]:
        lines.append("")
        lines.append("Dead-letter essences (adoption < 20% over ≥3 runs):")
        for d in ps["dead_letters"]:
            lines.append(
                f"- {d['essence']}: {d['avg_adoption']:.1%} over {d['n']} runs"
            )
    lines.append("")

    # §6b
    q = report["quality"]
    lines.append("## §6b Quality telemetry")
    lines.append("")
    if q["total_deliveries"] == 0:
        lines.append("_(no quality rows — needs TSUNAMI_QUALITY_TELEMETRY=1 and task_complete path)_")
    else:
        lines.append(f"Total deliveries: {q['total_deliveries']}")
        dh = q.get("delivery_health", {})
        if dh:
            lines.append(
                f"- Build pass rate:  {dh.get('build_pass_rate', 0):.1%}"
            )
            lines.append(
                f"- Vision pass rate: {dh.get('vision_pass_rate', 0):.1%}"
            )
        gen = q.get("generation_arc", {})
        if gen:
            lines.append(
                f"- Image-heavy runs (≥4 generate_image before file_write): "
                f"{gen.get('image_heavy_runs', 0)}"
            )
    lines.append("")

    # §7
    b = report["budget"]
    lines.append("## §7 Budget check")
    lines.append("")
    if b.get("directive_bytes_available", 0) == 0:
        lines.append("_(directive_bytes not tracked yet — worker needs to record it)_")
    else:
        lines.append(
            f"- Directive bytes p50={b['p50']}, p90={b['p90']}, max={b['max']}"
        )
    lines.append("")

    # §8
    gaps = report["new_gaps"]
    lines.append("## §8 New corpus gaps (top 5)")
    lines.append("")
    if not gaps:
        lines.append("_(no gap candidates — stall rates all under 30%)_")
    else:
        for i, g in enumerate(gaps, 1):
            lines.append(f"**{i}. {g['domain']} keyword gap**")
            lines.append(f"- Evidence: {g['evidence']}")
            lines.append(f"- Action: {g['proposed_action']}")
            lines.append(f"- Would falsify: {g['would_falsify']}")
            lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(
        "Generated by `scripts/overnight/morning_report.py`. "
        "Not a substitute for the tsunami-driven consolidator "
        "(sigma §17.6), but runs at zero cost."
    )
    return "\n".join(lines)


def build_report(root: Path, telemetry_dir: Path, probes_dir: Path) -> dict:
    runs_path = root / "runs.jsonl"
    stall = section_stall(telemetry_dir)
    report = {
        "config": {
            "root": str(root),
            "telemetry_dir": str(telemetry_dir),
            "probes_dir": str(probes_dir),
        },
        "coverage": section_coverage(runs_path),
        "stall": stall,
        "retractions": section_retractions(telemetry_dir),
        "cold_start": section_cold_start(telemetry_dir),
        "force_miss": section_force_miss(telemetry_dir),
        "probe_saturation": section_probe_saturation(probes_dir),
        "quality": section_quality(telemetry_dir),
        "budget": section_budget(runs_path),
    }
    report["new_gaps"] = section_new_gaps(stall, report["coverage"])
    # Coverage counters are Counters, serialize-unfriendly — flatten.
    c = report["coverage"]
    for k in ("by_exit_reason", "by_expected_scaffold", "by_expected_genre"):
        c[k] = dict(c[k])
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(_DEFAULT_ROOT),
                        help="overnight run root (contains runs.jsonl)")
    parser.add_argument("--telemetry", default="",
                        help="telemetry dir (default: <root>/telemetry or ~/.tsunami/telemetry)")
    parser.add_argument("--probes", default="",
                        help="probes dir (default: <root>/probes)")
    parser.add_argument("--out", default="-",
                        help="output path (- for stdout)")
    parser.add_argument("--json", action="store_true",
                        help="emit machine-readable JSON instead of Markdown")
    args = parser.parse_args()

    root = Path(args.root).expanduser()
    if args.telemetry:
        telemetry_dir = Path(args.telemetry).expanduser()
    elif (root / "telemetry").is_dir():
        telemetry_dir = root / "telemetry"
    else:
        telemetry_dir = _DEFAULT_TELEMETRY
    probes_dir = (Path(args.probes).expanduser() if args.probes
                  else root / "probes")

    report = build_report(root, telemetry_dir, probes_dir)
    rendered = (json.dumps(report, indent=2, default=str)
                if args.json else render_md(report))

    if args.out == "-":
        print(rendered)
    else:
        out = Path(args.out).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(rendered)
        print(f"Wrote {out}")


if __name__ == "__main__":
    main()
