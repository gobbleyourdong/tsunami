"""Tiered eval — 5 apps, simple → hard, covering every Tsunami tool.

Each tier adds one new tool on top of the previous tier's baseline. Running
all five exercises the full tool registry (project_init, file_write,
file_read, file_edit, shell_exec, undertow, riptide, generate_image,
search_web, message_chat, message_result) through one real agent build per
tier.

  T1  counter           project_init, file_write, shell_exec, undertow,
                        message_result                                (baseline)
  T2  pomodoro          + file_edit, file_read                        (iterate)
  T3  birthday card     + generate_image                              (image)
  T4  calculator layout + riptide                                     (vision)
  T5  crypto tracker    + search_web  (message_chat naturally in any) (web)

Run:
  python3 -m tsunami.tests.eval_tiered
  python3 -m tsunami.tests.eval_tiered --tier 1    # single tier
  python3 -m tsunami.tests.eval_tiered --dry-run   # skip agent runs, print plan

Output:
  workspace/training_data/eval_tiered.json  (machine)
  workspace/training_data/eval_tiered.md    (human)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tsunami.config import TsunamiConfig
from tsunami.agent import Agent


ENDPOINT = "http://localhost:8090"
OUT_DIR = REPO / "workspace" / "training_data"


def _make_calculator_ref() -> Path:
    """Generate a simple calculator reference image for T4's riptide probe.
    Draws the same layout the eval grades: display bar at top, 4×4 button
    grid, '=' button in a known spot. Saved to a temp path so the eval is
    self-contained and doesn't depend on shipped assets."""
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (320, 400), color="#222")
    d = ImageDraw.Draw(img)
    # display
    d.rectangle((20, 20, 300, 80), fill="#111", outline="#444", width=2)
    # 4×4 button grid
    x0, y0 = 20, 100
    bw, bh, gap = 65, 65, 5
    for row in range(4):
        for col in range(4):
            x = x0 + col * (bw + gap)
            y = y0 + row * (bh + gap)
            # equals spans nothing special; it's just bottom-right
            color = "#333" if (row, col) != (3, 3) else "#4a8"
            d.rectangle((x, y, x + bw, y + bh), fill=color, outline="#666", width=1)
    tmp = Path(tempfile.mkdtemp(prefix="eval_tiered_")) / "calculator_ref.png"
    img.save(tmp)
    return tmp


@dataclass
class Tier:
    id: str
    name: str
    budget_s: int
    prompt: str
    # tools we expect to see in the agent's tool_history for a clean pass.
    # Subset semantics — "at least these appeared somewhere in the run".
    required_tools: list[str] = field(default_factory=list)
    # tools newly exercised by this tier (cumulative coverage accounting)
    introduces: list[str] = field(default_factory=list)
    # Content-level quality checks. Each takes the deliverables project
    # dir, returns (ok, reason). All must be ok for `quality_ok=True`;
    # passed := delivered AND tools_covered AND quality_ok. This keeps
    # the gate honest — "delivered + all tools used" is process; the
    # checks verify the artifact actually does what the prompt asked.
    quality_checks: list = field(default_factory=list)


# ─── Quality check primitives ─────────────────────────────────────────
#
# Every check: (project_dir: Path) → (ok: bool, reason: str).  reason is
# short — "build artifact missing" / "no start button" — shown in the
# markdown report column for failing tiers.

def _has_build_artifact(project_dir: Path) -> tuple[bool, str]:
    """At least one of dist/, build/, or a public HTML bundle exists +
    has a non-trivial index.html (actual compiled output, not a stub)."""
    for sub in ("dist", "build", "public"):
        d = project_dir / sub
        if not d.exists():
            continue
        idx = d / "index.html"
        if idx.exists() and idx.stat().st_size > 200:
            return True, ""
    # Fall back: any .html in project_dir tree that's >200 bytes.
    for html in project_dir.rglob("*.html"):
        if "node_modules" in str(html):
            continue
        if html.stat().st_size > 200:
            return True, ""
    return False, "no build artifact (dist/build/html)"


def _read_app_tsx(project_dir: Path) -> str | None:
    for p in [project_dir / "src" / "App.tsx", project_dir / "src" / "app.tsx",
              project_dir / "App.tsx"]:
        if p.exists():
            try: return p.read_text(encoding="utf-8", errors="replace")
            except Exception: return None
    # Fall back: any App.tsx under project.
    for p in project_dir.rglob("App.tsx"):
        if "node_modules" in str(p): continue
        try: return p.read_text(encoding="utf-8", errors="replace")
        except Exception: continue
    return None


def _has_tokens(project_dir: Path, all_of: list[str],
                field_name: str = "App.tsx") -> tuple[bool, str]:
    """Case-insensitive substring check against App.tsx. `all_of` lists
    the tokens that must all appear."""
    text = _read_app_tsx(project_dir)
    if text is None:
        return False, f"{field_name} not found"
    lower = text.lower()
    missing = [t for t in all_of if t.lower() not in lower]
    if missing:
        return False, f"{field_name} missing: {', '.join(missing)}"
    return True, ""


def _no_stub_placeholders(project_dir: Path) -> tuple[bool, str]:
    """Reject obvious scaffold placeholders that didn't get replaced."""
    text = _read_app_tsx(project_dir)
    if text is None:
        return True, ""  # covered by other checks
    markers = ["// TODO: implement", "Lorem ipsum",
               "YOUR_CODE_HERE", "/* placeholder */"]
    for m in markers:
        if m.lower() in text.lower():
            return False, f"placeholder left in: {m!r}"
    return True, ""


def _quality_counter() -> list:
    return [
        _has_build_artifact,
        lambda p: _has_tokens(p, ["increment", "decrement"]) if _read_app_tsx(p)
                  else _has_tokens(p, ["+", "-"]),
        _no_stub_placeholders,
    ]


def _quality_pomodoro() -> list:
    return [
        _has_build_artifact,
        # Must have all 3 controls + a task list.
        lambda p: _has_tokens(p, ["start", "pause", "reset", "task"]),
        _no_stub_placeholders,
    ]


def _quality_birthday() -> list:
    return [
        _has_build_artifact,
        # Card-maker flow: user input + generate action.
        lambda p: _has_tokens(p, ["name", "message", "card"]),
        _no_stub_placeholders,
    ]


def _quality_calculator() -> list:
    return [
        _has_build_artifact,
        lambda p: _has_tokens(p, ["7", "8", "9", "+", "-", "*", "/", "="]),
        _no_stub_placeholders,
    ]


def _quality_crypto() -> list:
    return [
        _has_build_artifact,
        # Must reference a real price fetch or coin id.
        lambda p: _has_tokens(p, ["fetch", "price"]),
        _no_stub_placeholders,
    ]


def build_tiers(calc_ref: Path) -> list[Tier]:
    # Pure "build X" prompts — the system's forced-undertow gate (post-build)
    # and forced-riptide gate (on image prompts) mean the model doesn't need
    # to be told to call them. `introduces` is cumulative-coverage accounting:
    # the new tool first needed at this tier.
    return [
        Tier(
            id="T1",
            name="counter",
            budget_s=600,
            prompt="Build a counter app with plus and minus buttons.",
            required_tools=["project_init", "file_write", "shell_exec", "undertow", "message_result"],
            introduces=["project_init", "file_write", "shell_exec", "undertow", "message_result"],
            quality_checks=_quality_counter(),
        ),
        Tier(
            id="T2",
            name="pomodoro",
            budget_s=900,
            prompt=(
                "Build a Pomodoro timer with start, pause, and reset buttons. "
                "Include a task list where each task tracks how many pomodoros it took."
            ),
            required_tools=["project_init", "file_write", "shell_exec", "undertow", "message_result"],
            introduces=["file_edit", "file_read"],
            quality_checks=_quality_pomodoro(),
        ),
        Tier(
            id="T3",
            name="birthday",
            budget_s=1200,
            prompt=(
                "Build a birthday card maker. User types a name and a short message, "
                "clicks Generate, and the page shows a festive card with a generated "
                "birthday image as the backdrop. Use generate_image for the backdrop."
            ),
            required_tools=["project_init", "file_write", "shell_exec", "undertow", "message_result", "generate_image"],
            introduces=["generate_image"],
            quality_checks=_quality_birthday(),
        ),
        Tier(
            id="T4",
            name="calculator_layout",
            budget_s=1500,
            prompt=(
                f"Build a calculator HTML page that matches this reference layout: {calc_ref}"
            ),
            required_tools=["project_init", "file_write", "shell_exec", "undertow", "message_result", "riptide"],
            introduces=["riptide"],
            quality_checks=_quality_calculator(),
        ),
        Tier(
            id="T5",
            name="crypto_tracker",
            budget_s=1500,
            prompt=(
                "Build a crypto price tracker that shows current prices for Bitcoin, "
                "Ethereum, and Solana. Use search_web to look up today's approximate "
                "prices and hard-code them as sensible defaults in the UI."
            ),
            required_tools=["project_init", "file_write", "shell_exec", "undertow", "message_result", "search_web"],
            introduces=["search_web"],
            quality_checks=_quality_crypto(),
        ),
    ]


@dataclass
class TierResult:
    id: str
    name: str
    delivered: bool          # agent.state.task_complete — agent says it shipped
    tools_covered: bool      # all required_tools appeared in the run
    quality_ok: bool         # all content-level quality_checks pass
    passed: bool             # delivered AND tools_covered AND quality_ok
    iterations: int
    wall_s: float
    tools_used: list[str]
    tools_missing: list[str]
    quality_fails: list[str] = field(default_factory=list)
    failure_mode: str = ""


async def run_tier(tier: Tier, endpoint: str) -> TierResult:
    print(f"\n===== {tier.id}: {tier.name} (budget {tier.budget_s}s) =====")
    print(f"  prompt: {tier.prompt[:120]}...")

    ws_base = Path(tempfile.mkdtemp(prefix=f"eval_{tier.id.lower()}_"))
    config = TsunamiConfig(
        model_endpoint=endpoint,
        workspace_dir=str(ws_base),
        max_iterations=40,
        temperature=0.7,
        max_tokens=2048,
    )
    agent = Agent(config)

    t0 = time.monotonic()
    failure = ""
    try:
        await asyncio.wait_for(agent.run(tier.prompt), timeout=tier.budget_s)
    except asyncio.TimeoutError:
        failure = f"timeout after {tier.budget_s}s"
    except Exception as e:
        failure = f"{type(e).__name__}: {str(e)[:200]}"
    dt = time.monotonic() - t0

    tools_used = list(agent._tool_history)
    tools_used_set = set(tools_used)
    missing = [t for t in tier.required_tools if t not in tools_used_set]
    delivered = bool(agent.state.task_complete)
    tools_covered = not missing

    # Content-level quality gate. Only runs if the agent ever created a
    # project dir — if it never got that far, we skip quality checks (the
    # delivery/tool gates already explain the failure).
    quality_fails: list[str] = []
    quality_ok = True
    deliverables_root = Path(config.workspace_dir) / "deliverables"
    if deliverables_root.exists():
        projects = [d for d in deliverables_root.iterdir() if d.is_dir()]
        if projects:
            # Newest project = the one this tier built.
            project = max(projects, key=lambda p: p.stat().st_mtime)
            for check in tier.quality_checks or []:
                try:
                    ok, reason = check(project)
                except Exception as e:
                    ok, reason = False, f"check crashed: {type(e).__name__}"
                if not ok:
                    quality_fails.append(reason or check.__name__)
                    quality_ok = False
        elif tier.quality_checks:
            quality_ok = False
            quality_fails.append("no project created")
    elif tier.quality_checks:
        quality_ok = False
        quality_fails.append("no deliverables dir")

    passed = delivered and tools_covered and quality_ok

    flag = "✓" if passed else ("△" if delivered else "✗")
    print(f"  {flag} result: delivered={delivered}  tools_covered={tools_covered}  "
          f"quality_ok={quality_ok}  iters={agent.state.iteration}  {dt:.1f}s")
    print(f"    tools used: {', '.join(tools_used[:20])}{'...' if len(tools_used) > 20 else ''}")
    if missing:
        print(f"    missing required: {missing}")
    if quality_fails:
        print(f"    quality fails: {quality_fails}")
    if failure:
        print(f"    failure: {failure}")

    # Tidy up temp workspace to avoid disk fill over many cron runs.
    shutil.rmtree(ws_base, ignore_errors=True)

    return TierResult(
        id=tier.id,
        name=tier.name,
        delivered=delivered,
        tools_covered=tools_covered,
        quality_ok=quality_ok,
        passed=passed,
        iterations=agent.state.iteration,
        wall_s=round(dt, 1),
        tools_used=tools_used,
        tools_missing=missing,
        quality_fails=quality_fails,
        failure_mode=failure,
    )


def write_report(tiers: list[Tier], results: list[TierResult]):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    passed = sum(1 for r in results if r.passed)
    delivered = sum(1 for r in results if r.delivered)
    all_tools_used = set()
    for r in results:
        all_tools_used.update(r.tools_used)
    # Full tool set across all tier requirements (cumulative)
    full_set = set()
    for t in tiers:
        full_set.update(t.required_tools)
        full_set.update(t.introduces)
    coverage_pct = 100 * len(all_tools_used & full_set) / max(1, len(full_set))

    # JSON
    detail = {
        "endpoint": ENDPOINT,
        "passed": passed,
        "delivered": delivered,
        "total": len(results),
        "tool_coverage_pct": round(coverage_pct, 1),
        "tool_set_target": sorted(full_set),
        "tool_set_hit": sorted(all_tools_used & full_set),
        "tool_set_missed": sorted(full_set - all_tools_used),
        "tiers": [asdict(r) for r in results],
    }
    (OUT_DIR / "eval_tiered.json").write_text(json.dumps(detail, indent=2))

    # Markdown
    lines = []
    lines.append(f"# Tsunami Tiered Eval")
    lines.append("")
    lines.append(f"Endpoint: `{ENDPOINT}`")
    lines.append("")
    quality_ok_count = sum(1 for r in results if r.quality_ok)
    lines.append(f"- **Passed**: {passed}/{len(results)} (delivered AND tools_covered AND quality_ok)")
    lines.append(f"- **Delivered**: {delivered}/{len(results)} (agent marked task complete)")
    lines.append(f"- **Quality-checked**: {quality_ok_count}/{len(results)} (artifact matches prompt intent)")
    lines.append(f"- **Tool coverage**: {coverage_pct:.0f}% ({len(all_tools_used & full_set)}/{len(full_set)})")
    lines.append("")
    lines.append("| Tier | App | Pass | Delivered | Tools | Quality | Iters | Time | Missing / Quality fails | Failure |")
    lines.append("|------|-----|------|-----------|-------|---------|-------|------|-------------------------|---------|")
    for t, r in zip(tiers, results):
        p = "✓" if r.passed else ("△" if r.delivered else "✗")
        d = "✓" if r.delivered else "✗"
        tc = "✓" if r.tools_covered else "✗"
        q = "✓" if r.quality_ok else "✗"
        miss = ", ".join(r.tools_missing) if r.tools_missing else ""
        qfail = "; ".join(r.quality_fails) if r.quality_fails else ""
        issues = " / ".join(x for x in (miss, qfail) if x) or "—"
        fail = r.failure_mode or "—"
        lines.append(f"| {r.id} | {r.name} | {p} | {d} | {tc} | {q} | {r.iterations} | {r.wall_s}s | {issues} | {fail} |")
    lines.append("")
    lines.append("△ = delivered but quality or tool-coverage gate failed.")
    lines.append("")
    lines.append("## Tool coverage")
    lines.append("")
    lines.append(f"- Hit ({len(all_tools_used & full_set)}): {', '.join(sorted(all_tools_used & full_set))}")
    missed = full_set - all_tools_used
    if missed:
        lines.append(f"- Missed ({len(missed)}): {', '.join(sorted(missed))}")
    else:
        lines.append("- Missed: none — all tools exercised")
    (OUT_DIR / "eval_tiered.md").write_text("\n".join(lines) + "\n")

    print(f"\n=== SUMMARY ===")
    print(f"  passed:    {passed}/{len(results)}")
    print(f"  delivered: {delivered}/{len(results)}")
    print(f"  tool coverage: {coverage_pct:.0f}% ({len(all_tools_used & full_set)}/{len(full_set)})")
    print(f"  report: {OUT_DIR}/eval_tiered.md")


async def amain(args):
    calc_ref = _make_calculator_ref()
    tiers = build_tiers(calc_ref)

    if args.tier:
        tiers = [t for t in tiers if t.id == args.tier or t.id.lower() == args.tier.lower()]
        if not tiers:
            print(f"No tier matching '{args.tier}'. Valid: T1, T2, T3, T4, T5.")
            return 2

    if args.dry_run:
        print("Planned tiers:")
        for t in tiers:
            print(f"  {t.id} {t.name:<20} budget={t.budget_s}s  introduces={t.introduces}")
        print(f"\nReference image: {calc_ref}")
        return 0

    results = []
    for tier in tiers:
        r = await run_tier(tier, args.endpoint)
        results.append(r)

    write_report(tiers, results)
    return 0 if all(r.passed for r in results) else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", default=ENDPOINT)
    parser.add_argument("--tier", default="", help="Run only one tier (T1–T5)")
    parser.add_argument("--dry-run", action="store_true", help="Print plan, don't run")
    args = parser.parse_args()
    return asyncio.run(amain(args))


if __name__ == "__main__":
    sys.exit(main())
