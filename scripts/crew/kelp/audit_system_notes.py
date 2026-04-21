#!/usr/bin/env python3
"""Census of add_system_note emission sites — structural vs advisory.

A structural system_note narrates enforcement that just happened (tool
rejected, tool_call rewritten, phase advanced). An advisory system_note
tells the drone what to do and hopes it complies. The kelp doctrine
(sigma v5 — convention beats instruction) says every advisory is a
pain candidate: something the orchestrator should be enforcing at a
gate instead of asking the drone to please listen.

This script walks tsunami/agent.py, classifies every add_system_note
call into structural / advisory / ambiguous, and emits a JSON report
kelp can consume each round. Used to seed new pain candidates for
Coral and to lock in audit numbers via a regression test.

Classification heuristic:
  structural — the call sits in an error-return branch (is_error=True
    near the top of the enclosing function, or the enclosing try/
    except branch returns an error ToolResult), OR enforcement
    (return / raise / continue / break / tool_call.name = ... /
    self._force_deliver = True / ToolCall(name=...)) appears within
    6 lines after the call.
  advisory — call is followed by hedged copy ("maybe", "should",
    "consider", "skip the", "try to") with no enforcement in the
    same block.
  ambiguous — neither signal fires. Usually a system_note that
    labels an event without explicitly enforcing it. Manual review
    needed; many of these are still pain candidates.

Usage:
  python3 scripts/crew/kelp/audit_system_notes.py
  python3 scripts/crew/kelp/audit_system_notes.py --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent.parent.parent
AGENT = REPO / "tsunami" / "agent.py"


ENFORCEMENT_RE = re.compile(
    r"\b(return\b|raise\b|continue\b|break\b|"
    r"tool_call\.name\s*=|"
    r"ToolCall\(name|"
    r"response\.tool_call\s*=|"
    r"is_error\s*=\s*True|"
    r"self\._(force_deliver|skip|block|gate|reject))"
)
HEDGE_RE = re.compile(
    r"\b(maybe|consider|you might|you may|could use|try to|"
    r"should|skip the|plan your next|stop running|stop searching)\b",
    re.IGNORECASE,
)


def _extract_note_text(lines: list[str], idx: int) -> str:
    """Pull the first quoted string from the system_note call body.
    Returns up to 140 chars."""
    blob = " ".join(lines[idx:idx + 12])
    # First triple- or double-quoted string after add_system_note(
    m = re.search(r'add_system_note\(\s*["\']([^"\']{10,})["\']', blob)
    if m:
        return m.group(1)[:140]
    m = re.search(r'add_system_note\(\s*f?["\']([^"\']{10,})["\']', blob)
    if m:
        return m.group(1)[:140]
    # f-string with variable interpolation
    m = re.search(r'add_system_note\(\s*\(\s*\n?\s*f?["\']([^"\']{10,})["\']', blob)
    if m:
        return m.group(1)[:140]
    return blob[:140]


def classify(line_idx: int, lines: list[str]) -> tuple[str, str]:
    """(category, reason) for the system_note at line_idx."""
    window_before = "\n".join(lines[max(0, line_idx - 8):line_idx])
    window_after = "\n".join(lines[line_idx:line_idx + 8])
    blob = " ".join(lines[line_idx:line_idx + 12])

    # Strong structural: error-return branch signals above
    if any(kw in window_before for kw in
           ("is_error=True", "return ToolResult", "reject_msg =")):
        return "structural", "in error-return branch"

    # Enforcement within the next ~8 lines — the note is load-bearing
    enforcement = ENFORCEMENT_RE.findall(window_after)
    if enforcement:
        return "structural", f"enforcement follows: {enforcement[0]}"

    # Hedged copy — advisory
    if HEDGE_RE.search(blob):
        return "advisory", "hedged copy"

    return "ambiguous", "no enforcement, no hedges"


def audit(agent_src: Path = AGENT) -> dict:
    """Run the full audit, return a structured report."""
    lines = agent_src.read_text().splitlines()
    sites: list[dict] = []
    for i, ln in enumerate(lines):
        if "add_system_note" in ln and "def " not in ln:
            category, reason = classify(i, lines)
            note = _extract_note_text(lines, i)
            sites.append({
                "line": i + 1,
                "category": category,
                "reason": reason,
                "note_preview": note,
            })
    summary = {"structural": 0, "advisory": 0, "ambiguous": 0}
    for s in sites:
        summary[s["category"]] += 1
    return {
        "file": str(agent_src),
        "total_sites": len(sites),
        "summary": summary,
        "sites": sites,
    }


def render_report(audit_result: dict) -> str:
    out = [
        f"system_note audit: {audit_result['file']}",
        f"Total sites: {audit_result['total_sites']}",
        "Summary: "
        + ", ".join(f"{k}={v}" for k, v in audit_result["summary"].items()),
        "",
    ]
    for cat in ("advisory", "ambiguous", "structural"):
        rows = [s for s in audit_result["sites"] if s["category"] == cat]
        if not rows:
            continue
        out.append(f"=== {cat.upper()} ({len(rows)}) ===")
        for site in rows:
            out.append(
                f"  L{site['line']:<5d} [{site['reason'][:30]:<30s}] "
                f"{site['note_preview']!r}"
            )
        out.append("")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json", action="store_true",
        help="emit structured JSON instead of a report",
    )
    parser.add_argument(
        "--fail-on-advisory", action="store_true",
        help="exit 1 if any advisory sites exist (for CI gating)",
    )
    args = parser.parse_args(argv)
    result = audit()
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(render_report(result))
    if args.fail_on_advisory and result["summary"]["advisory"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
