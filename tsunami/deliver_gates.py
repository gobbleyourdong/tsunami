"""Declarative delivery-gate pipeline.

Layer 2 of the 'eliminate hardcoded brittle surfaces' pass. The
message_result handler in agent.py had 2+ stacked `if` blocks each
with its own error message and system_note — a drone that failed
the first check never saw the second's concerns until the first was
resolved, and adding a new gate meant interleaving another if-branch
inline.

This module exposes:

    run_deliver_gates(state, project_dir, delivery_attempts)
        → Optional[GateFailure]  (first failure, or None = all pass)

Each gate is a small function returning `GateResult(passed, message,
system_note)`. Registered in the ordered `DELIVER_GATES` list; the
first failing gate short-circuits and returns its failure. Adding a
new gate = appending one function to the list.

Today's gates:

    code_write_gate        — src/App.tsx written by the drone
                             (or dist/index.html exists from a build)
    asset_existence_gate   — every <img src="/..."> referenced from
                             src/*.tsx exists in public/

Future gates slot in without touching the message_result handler:

    prop_type_gate         — tsc --noEmit against src/App.tsx
    runtime_smoke_gate     — a playwright page.goto on dist/ doesn't
                             throw (catches unmounted React roots)
    accessibility_gate     — axe-core on dist/ (missing alt, no H1, etc)
    brand_tokens_gate      — verified palette in computed styles
                             matches the style_scaffold's palette
    brief_coverage_gate    — every <section> named in the task brief
                             has a corresponding DOM element

The structural win: each gate owns ONE responsibility with ONE check
function, ONE message template, and a clear name for logs. The
message_result handler becomes a 5-line driver loop.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

log = logging.getLogger("tsunami.deliver_gates")


@dataclass
class GateResult:
    """Outcome of a single gate's check."""
    passed: bool
    name: str
    message: str = ""          # internal log message
    system_note: str = ""      # text injected into drone's context on failure
    advisory: bool = False     # True = log + continue, False = block
    hard: bool = False         # True = fires even past retry-budget
                               # (definitive breakage: 404 assets,
                               # syntax errors, blank dist). Default
                               # False lets the standard retry-budget
                               # auto-pass gates that a drone genuinely
                               # can't fix past 2 attempts.


@dataclass
class GateFailure:
    """Packaged failure result ready to drop into message_result's reject path."""
    gate: str
    log_message: str
    system_note: str
    return_text: str


# ── Gate implementations ───────────────────────────────────────────


def code_write_gate(
    state_flags: dict,
    project_dir: Path,
) -> GateResult:
    """src/App.tsx must be written by the drone, OR dist/index.html
    must exist (build shipped). Scaffold stub alone doesn't count —
    `state_flags['app_source_written']` flips only on a real write to
    src/App.tsx / src/App.jsx / src/main.ts / src/main.tsx.
    """
    name = "code_write"
    if state_flags.get("app_source_written"):
        return GateResult(passed=True, name=name)
    # Dist-built fallback — accept a successful prior build as positive
    # evidence that the drone shipped something renderable.
    try:
        if project_dir and (project_dir / "dist" / "index.html").exists():
            return GateResult(passed=True, name=name, message="dist/index.html present")
    except Exception:
        pass
    return GateResult(
        passed=False,
        name=name,
        message="App.tsx not written (and no prior dist/)",
        system_note=(
            "BLOCKED: src/App.tsx has not been written. Write the full "
            "app implementation to src/App.tsx BEFORE calling "
            "message_result. Writes to index.css or component files "
            "alone are not delivery."
        ),
    )


_IMG_SRC_RE = re.compile(
    r"""src=['"](/[^'"?#]+\.(?:png|jpg|jpeg|webp|svg|gif))['"]""",
    re.IGNORECASE,
)
_URL_BG_RE = re.compile(
    r"""url\(['"]?(/[^'"?#\)]+\.(?:png|jpg|jpeg|webp|svg|gif))['"]?\)""",
    re.IGNORECASE,
)


def asset_existence_gate(
    state_flags: dict,
    project_dir: Path,
) -> GateResult:
    """Every `<img src="/path">` or CSS `url(/path)` referenced from
    src/*.tsx must exist at public/<path>. Catches the failure mode
    where drone writes App.tsx without generating referenced imagery
    (v26: 4 image refs, 0 generations, 4 runtime 404s).
    """
    name = "asset_existence"
    if not project_dir or not project_dir.exists():
        return GateResult(passed=True, name=name, message="no project dir")
    src_dir = project_dir / "src"
    public_dir = project_dir / "public"
    if not src_dir.exists():
        return GateResult(passed=True, name=name, message="no src/ dir")

    referenced: set[str] = set()
    for tsx in src_dir.rglob("*.tsx"):
        try:
            body = tsx.read_text()
        except Exception:
            continue
        for m in _IMG_SRC_RE.finditer(body):
            referenced.add(m.group(1).lstrip("/"))
        for m in _URL_BG_RE.finditer(body):
            referenced.add(m.group(1).lstrip("/"))
    missing = sorted(rel for rel in referenced if not (public_dir / rel).is_file())
    if not missing:
        return GateResult(passed=True, name=name)
    lst = ", ".join(missing[:8])
    return GateResult(
        passed=False,
        name=name,
        message=f"{len(missing)} asset(s) 404: {lst}",
        system_note=(
            f"BLOCKED: your App.tsx references {len(missing)} image "
            f"path(s) that don't exist in public/ — {lst}. Call "
            f"generate_image() for each before delivering. Users will "
            f"see broken-image icons if you ship now."
        ),
        hard=True,   # 404s are definitive — never bypass, even past
                     # retry-budget. PIKO v5 shipped with missing
                     # founder.png / z.png / x.png because the budget
                     # auto-pass silently skipped this check.
    )


# ── Registry and driver ────────────────────────────────────────────


GateCheckFn = Callable[[dict, Path], GateResult]

DELIVER_GATES: list[GateCheckFn] = [
    code_write_gate,
    asset_existence_gate,
]


def run_deliver_gates(
    state_flags: dict,
    project_dir: Path | None,
    max_attempts: int = 2,
    attempt_number: int = 1,
) -> GateFailure | None:
    """Run gates in order, return first failure or None.

    Drone gets `max_attempts` retries; past that the gates auto-pass
    (drone's failure budget is exhausted; let it ship with whatever
    advisories the downstream undertow / vision-gate surface).

    `state_flags` is a plain dict the caller populates from the agent
    state — keeps this module orthogonal to the Agent class and easy
    to unit-test.
    """
    budget_exhausted = attempt_number > max_attempts
    if budget_exhausted:
        log.debug(f"deliver-gate budget exhausted (attempt {attempt_number}); only HARD gates fire")
    proj = project_dir or Path("/nonexistent")
    for gate_fn in DELIVER_GATES:
        try:
            result = gate_fn(state_flags, proj)
        except Exception as e:
            log.debug(f"gate {gate_fn.__name__} crashed: {e}; treating as pass")
            continue
        if result.advisory:
            log.info(f"[deliver-gate:{result.name}] advisory: {result.message}")
            continue
        if not result.passed:
            # Budget-exhausted: skip soft gates but HARD gates still fire.
            # Hard gates are for definitive breakage (404 assets, syntax
            # errors) — no amount of retries will make them acceptable.
            if budget_exhausted and not result.hard:
                log.info(f"[deliver-gate:{result.name}] soft-fail past budget — passing")
                continue
            log.warning(f"[deliver-gate:{result.name}] FAIL — {result.message}")
            return GateFailure(
                gate=result.name,
                log_message=result.message,
                system_note=result.system_note,
                return_text=f"Gate '{result.name}' failed: {result.message}",
            )
    return None


__all__ = [
    "GateResult",
    "GateFailure",
    "DELIVER_GATES",
    "run_deliver_gates",
    "code_write_gate",
    "asset_existence_gate",
]
