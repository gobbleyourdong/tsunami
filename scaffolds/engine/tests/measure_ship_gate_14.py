"""Ship gate #14 — N=20 one-shot arena-shooter emission measurement.

Protocol:
  For N iterations, send Qwen 3.6 a system prompt that contains the
  DesignScript schema + the arena_shooter.json example, plus a user
  prompt asking for an arena-shooter design. Parse the model output
  as JSON, run it through the TS validator via the cli.ts subprocess
  (reusing emit_design.py's wrapper), and record pass/fail.

  Ship gate passes if valid_count / N ≥ 0.50.

Output:
  workspace/training_data/ship_gate_14.json — structured detail
  workspace/training_data/ship_gate_14.md   — human summary

Run:
  python3 scaffolds/engine/tests/measure_ship_gate_14.py
  python3 scaffolds/engine/tests/measure_ship_gate_14.py --n 5   # quick smoke
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from tsunami.tools.emit_design import emit_design  # noqa: E402

ENDPOINT = "http://localhost:8095"
OUT_DIR = REPO / "workspace" / "training_data"
EXAMPLES = REPO / "tsunami" / "context" / "examples"
DESIGN_GUIDE = REPO / "tsunami" / "context" / "design_script.md"
SCHEMA_FILE = REPO / "scaffolds" / "engine" / "src" / "design" / "schema.ts"


def build_system_prompt() -> str:
    """Compose the priming context: design_script.md + schema.ts + one
    canonical example. The one-shot emission is this context + a simple
    user prompt; we measure whether Qwen 3.6 emits valid JSON."""
    parts = ["You are Tsunami — you emit DesignScript JSON for engine projects.",
             "", "# Design-script guide", "", DESIGN_GUIDE.read_text()]
    parts += ["", "# Schema (abridged — see full file for details)",
              "```typescript", SCHEMA_FILE.read_text()[:3500], "```"]
    parts += ["", "# Canonical example (arena_shooter)",
              "```json", (EXAMPLES / "arena_shooter.json").read_text(), "```"]
    parts += ["",
              "On the next turn, output ONLY a valid DesignScript JSON object, "
              "no markdown fences, no commentary — the first `{` through the "
              "matching `}`. Your output is piped directly into a validator.",
              ]
    return "\n".join(parts)


def extract_json(text: str) -> str | None:
    """Find the first balanced {...} block in the model output. Qwen
    sometimes prepends a thought trace even with enable_thinking off."""
    # Strip fences if any.
    text = re.sub(r"```(?:json)?\s*", "", text)
    text = text.replace("```", "")
    # Find first {
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(text)):
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


async def one_shot(prompt: str, system_prompt: str) -> dict:
    """One call to :8095. Returns {ok, content, latency_s, error?}."""
    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=240) as client:
            resp = await client.post(
                f"{ENDPOINT}/v1/chat/completions",
                json={
                    "model": "Qwen/Qwen3.6-35B-A3B-FP8",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 8192,
                    "temperature": 0.7,
                    "enable_thinking": False,
                },
            )
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}",
                "latency_s": round(time.monotonic() - t0, 2)}
    dt = round(time.monotonic() - t0, 2)
    if resp.status_code != 200:
        return {"ok": False, "error": f"HTTP {resp.status_code}: {resp.text[:200]}",
                "latency_s": dt}
    try:
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
    except Exception as e:
        return {"ok": False, "error": f"parse: {e}", "latency_s": dt}
    return {"ok": True, "content": content, "latency_s": dt}


def measure_one(content: str) -> dict:
    """Extract JSON + run through validator. Returns
    {parsed, valid, validator_errors?, parse_error?}."""
    raw = extract_json(content)
    if not raw:
        return {"parsed": False, "valid": False, "parse_error": "no balanced {}"}
    try:
        design = json.loads(raw)
    except Exception as e:
        return {"parsed": False, "valid": False, "parse_error": f"json: {e}"}
    result = emit_design(design,
                         project_name=f"_measure_14_{int(time.time() * 1000)}",
                         deliverables_dir=OUT_DIR / "measure_14_dump",
                         timeout_sec=15)
    valid = result.get("ok") is True
    return {"parsed": True, "valid": valid,
            "validator_errors": result.get("errors") if not valid else None,
            "stage": result.get("stage")}


async def run_n(n: int, user_prompt: str) -> list[dict]:
    sys_prompt = build_system_prompt()
    results = []
    for i in range(n):
        print(f"  [{i + 1}/{n}] calling qwen36 …", flush=True)
        call = await one_shot(user_prompt, sys_prompt)
        if not call["ok"]:
            print(f"       ✗ call failed: {call.get('error', '?')[:80]}", flush=True)
            results.append({**call, "parsed": False, "valid": False})
            continue
        m = measure_one(call["content"])
        tag = "✓ valid" if m["valid"] else (
              "△ parsed, invalid" if m["parsed"] else "✗ unparseable")
        print(f"       {tag} in {call['latency_s']}s", flush=True)
        results.append({**call, **m})
    return results


def write_report(results: list[dict], n: int) -> dict:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    valid = sum(1 for r in results if r.get("valid"))
    parsed = sum(1 for r in results if r.get("parsed"))
    rate = valid / max(1, n)
    avg_lat = sum(r.get("latency_s", 0) for r in results) / max(1, n)

    detail = {
        "n": n, "valid": valid, "parsed": parsed,
        "valid_rate": round(rate, 3),
        "passes_gate": rate >= 0.50,
        "avg_latency_s": round(avg_lat, 2),
        "runs": results,
    }
    (OUT_DIR / "ship_gate_14.json").write_text(json.dumps(detail, indent=2))

    lines = [
        "# Ship Gate #14 — Tsunami one-shot arena-shooter emission",
        "",
        f"- **N = {n}**",
        f"- **Valid**: {valid}/{n} ({rate:.0%})",
        f"- **Parsed (but maybe invalid)**: {parsed}/{n}",
        f"- **Avg latency**: {avg_lat:.1f}s",
        f"- **Gate passes (≥50% valid)**: {'✓ GREEN' if rate >= 0.50 else '✗ RED'}",
        "",
        "| # | status | latency | notes |",
        "|---|--------|---------|-------|",
    ]
    for i, r in enumerate(results):
        if r.get("valid"):
            status = "✓"
            notes = "—"
        elif r.get("parsed"):
            errs = r.get("validator_errors") or []
            kinds = {e.get("kind") for e in errs if isinstance(e, dict)}
            notes = f"{len(errs)} validator errs: {', '.join(sorted(kinds))[:80]}"
            status = "△"
        else:
            notes = r.get("parse_error") or r.get("error") or "?"
            notes = notes[:80]
            status = "✗"
        lines.append(f"| {i + 1} | {status} | {r.get('latency_s', 0)}s | {notes} |")
    (OUT_DIR / "ship_gate_14.md").write_text("\n".join(lines) + "\n")

    print(f"\n=== SHIP GATE #14 ===")
    print(f"  valid: {valid}/{n} ({rate:.0%})  parsed: {parsed}/{n}  "
          f"avg: {avg_lat:.1f}s")
    print(f"  gate: {'✓ GREEN' if rate >= 0.50 else '✗ RED'}")
    print(f"  report: {OUT_DIR}/ship_gate_14.md")
    return detail


async def amain(args):
    user_prompt = ("Build an arena shooter: top-down, player in the center, "
                   "enemy waves spawn at the rim with increasing difficulty, "
                   "health pickups, score HUD, game-over on death.")
    results = await run_n(args.n, user_prompt)
    detail = write_report(results, args.n)
    return 0 if detail["passes_gate"] else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=20)
    args = parser.parse_args()
    return asyncio.run(amain(args))


if __name__ == "__main__":
    sys.exit(main())
