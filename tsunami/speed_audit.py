"""Speed-audit script — static check that the agentic-speed safeguards are
in place. Run after any broad refactor to catch accidental reverts.

Exit code 0 if all layers detected; 1 with a readable report otherwise.

Usage:
    python3 -m tsunami.speed_audit
    python3 -m tsunami.speed_audit --json   # machine-readable

The safeguards form a defense-in-depth for the SURGE failure mode (drone
spent 11 turns on generate_image before ever writing App.tsx):

  L1  System prompt      — tsunami/prompt.py step 3 mentions IMAGE BUDGET
  L2  Brand directive    — tsunami/brand_scaffold.py format_brand_directive
                           emits a BUDGET: line above the template list
  L3  Tool response path — tsunami/tools/generate.py appends budget hints
                           at image counts 3 and 5+
  L4  Phase-machine nudge — tsunami/phase_machine.py WRITE-stall threshold
                            fires at iter 5 (tightened from 8) with
                            explicit "STOP generating images" copy
  L5  Agent image ceiling — tsunami/agent.py counts generate_image since
                            last file_write, injects hard system-note at 5+
  L6  QA rubric loader   — tsunami/qa_rubrics.py exposes web_polish +
                           art_direction rubrics for vision_gate threading

Each layer has a small fingerprint check — a unique string we expect to
see. If the string is missing, the layer regressed. We don't try to run
the layer; we just verify the source contract.
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


ROOT = Path(__file__).parent


@dataclass
class LayerCheck:
    layer: int
    name: str
    file: str
    fingerprint: str
    reason: str
    present: bool = False
    match_line: int | None = None


def _scan(path: Path, fingerprint: str) -> int | None:
    try:
        for i, line in enumerate(path.read_text().splitlines(), start=1):
            if fingerprint in line:
                return i
    except FileNotFoundError:
        return None
    return None


def run_audit() -> list[LayerCheck]:
    checks = [
        LayerCheck(
            layer=1, name="system-prompt image budget",
            file="prompt.py",
            fingerprint="IMAGE BUDGET: 3 images",
            reason="drone reads budget from step 3 of every turn's system prompt",
        ),
        LayerCheck(
            layer=2, name="brand-directive BUDGET line",
            file="brand_scaffold.py",
            fingerprint="BUDGET: 3 images max",
            reason="brief emits budget right above LOGO/HERO/PRODUCT/... template list",
        ),
        LayerCheck(
            layer=3, name="tool-response budget hint (core set)",
            file="tools/generate.py",
            fingerprint="[budget: 3 images",
            reason="3rd successful generate_image appends a core-set hint",
        ),
        LayerCheck(
            layer=3, name="tool-response budget hint (exceeded)",
            file="tools/generate.py",
            fingerprint="[budget exceeded",
            reason="5+ generate_image appends a STOP hint",
        ),
        LayerCheck(
            layer=4, name="phase-machine WRITE-stall threshold 5",
            file="phase_machine.py",
            fingerprint="5 iterations without writing any files",
            reason="nudge at iter 5 (tightened from legacy 8) with STOP copy",
        ),
        LayerCheck(
            layer=5, name="agent image-ceiling nudge",
            file="agent.py",
            fingerprint="IMAGE CEILING HIT",
            reason="5+ generate_image without file_write injects hard system-note",
        ),
        LayerCheck(
            layer=6, name="QA rubric loader",
            file="qa_rubrics.py",
            fingerprint="def load_polish_rubric",
            reason="web_polish + art_direction rubric for vision_gate threading",
        ),
        LayerCheck(
            layer=7, name="turn-1 narration block",
            file="agent.py",
            fingerprint="BLOCKED: message_result is delivery, not narration",
            reason="catches drones that message_result('Starting phase 1...') on turn 1 and exit at 0s with no build",
        ),
        LayerCheck(
            layer=8, name="tsc-error component routing",
            file="auto_build.py",
            fingerprint="Do NOT read every component",
            reason="parses 'Property X does not exist on Y' tsc errors and points drone at the ONE component to read, breaking read-spirals",
        ),
        LayerCheck(
            layer=9, name="image ceiling HARD enforce",
            file="agent.py",
            fingerprint="IMAGE CEILING ENFORCED",
            reason="ORBIT v5 showed drone ignoring L5 advisory; this rejects further generate_image calls at the exec site once the ceiling is latched",
        ),
        LayerCheck(
            layer=10, name="grounded synth delivery text",
            file="agent.py",
            fingerprint="agent-synthesized",
            reason="replaces the hardcoded 'Pomodoro timer' placeholder that rode every agent-synth message_result; the synth text now references the actual project",
        ),
        LayerCheck(
            layer=11, name="wave-side component hoist on tsc-streak",
            file="agent.py",
            fingerprint="hoisted by wave — you ignored the nudge",
            reason="MIRA v8 showed drones ignoring 'read src/components/X.tsx' nudges and prop-guessing into read-spiral exits; on tsc streak >= 2, wave reads the named component and hoists its source into the drone's context directly",
        ),
    ]
    for c in checks:
        line = _scan(ROOT / c.file, c.fingerprint)
        if line is not None:
            c.present = True
            c.match_line = line
    return checks


def format_report(checks: list[LayerCheck]) -> str:
    lines: list[str] = []
    lines.append("Tsunami agentic-speed safeguard audit")
    lines.append("=" * 72)
    ok = sum(1 for c in checks if c.present)
    missing = [c for c in checks if not c.present]
    for c in checks:
        mark = "PASS" if c.present else "FAIL"
        loc = f"{c.file}:{c.match_line}" if c.match_line else f"{c.file} (not found)"
        lines.append(f"  L{c.layer}  [{mark}]  {c.name:<42}  {loc}")
    lines.append("-" * 72)
    lines.append(f"  {ok}/{len(checks)} safeguards present")
    if missing:
        lines.append("")
        lines.append("Missing layers:")
        for c in missing:
            lines.append(f"  · L{c.layer} {c.name} — {c.reason}")
    return "\n".join(lines)


def main() -> int:
    as_json = "--json" in sys.argv
    checks = run_audit()
    if as_json:
        print(json.dumps([asdict(c) for c in checks], indent=2))
    else:
        print(format_report(checks))
    return 0 if all(c.present for c in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
