#!/usr/bin/env python3
"""Tool latency bench — direct run vs forced-tool model emission.

Two phases, same (tool, param-shape) matrix:

  Phase A — DIRECT CALL:
    Call `tool.execute(**args)` directly. Measures pure tool latency
    (filesystem syscall, shell subprocess, no model in the loop).

  Phase B — MODEL EMIT:
    Send a one-line prompt like "Call {tool} with these args: {json}"
    with tool_choice forced to that tool. Measures prompt → response
    wall time (model thinking + emission + parse). No agent loop, no
    history, no retry.

Output: markdown table. Use the columns to spot where the snag is —
if DIRECT is 10ms and EMIT is 60000ms, the bottleneck is the model;
if DIRECT dominates, the tool itself is the problem.

Usage:
    python3 -m tsunami.tests.bench_tools
    python3 -m tsunami.tests.bench_tools --thinking       # force thinking on
    python3 -m tsunami.tests.bench_tools --skip-emit      # phase A only
"""

from __future__ import annotations

import argparse
import asyncio
import json
import tempfile
import time
from pathlib import Path

from tsunami.config import TsunamiConfig
from tsunami.model import TsunamiModel
from tsunami.prompt import build_system_prompt
from tsunami.state import AgentState
from tsunami.tools import build_registry


def _mk_small(tmp: Path) -> Path:
    p = tmp / "small.txt"
    p.write_text("hello world\n")
    return p


def _mk_medium(tmp: Path) -> Path:
    p = tmp / "medium.txt"
    p.write_text("line\n" * 2000)
    return p


def _mk_edit_target(tmp: Path) -> Path:
    p = tmp / "edit.txt"
    p.write_text("before = 1\nmiddle = 2\nafter = 3\n")
    return p


CASES = [
    ("file_read",    "small",   lambda tmp: {"path": str(_mk_small(tmp))},            False),
    ("file_read",    "medium",  lambda tmp: {"path": str(_mk_medium(tmp)), "limit": 2000}, False),
    ("file_write",   "small",   lambda tmp: {"path": str(tmp / "out_s.txt"), "content": "hi"}, False),
    ("file_write",   "medium",  lambda tmp: {"path": str(tmp / "out_m.txt"), "content": "x" * 10_000}, False),
    ("file_edit",    "single",  lambda tmp: {"path": str(_mk_edit_target(tmp)),
                                              "old_content": "middle = 2",
                                              "new_content": "middle = 42"}, False),
    ("shell_exec",   "echo",    lambda tmp: {"command": "echo hello"},                False),
    ("shell_exec",   "ls",      lambda tmp: {"command": "ls / | head -5"},            False),
    ("message_chat", "short",   lambda tmp: {"text": "status: ok"},                   False),
    ("message_result", "short", lambda tmp: {"text": "done", "done": True},           True),
    ("undertow",     "small",   lambda tmp: {"path": str(_mk_small(tmp)),
                                              "expect": "hello world"},               True),
    ("plan_update",  "trivial", lambda tmp: {"goal": "build timer",
                                              "phases": [{"name": "scaffold", "steps": ["init"]}]}, True),
    ("plan_advance", "trivial", lambda tmp: {"summary": "scaffold done"},             True),
]


async def bench_direct(registry) -> list[dict]:
    rows = []
    for tool_name, shape, factory, _planning in CASES:
        tool = registry.get(tool_name)
        if tool is None:
            rows.append({"tool": tool_name, "shape": shape,
                         "direct_ms": None, "error": "not in registry"})
            continue
        with tempfile.TemporaryDirectory(prefix="bench_", dir="workspace") as tmpdir:
            tmp = Path(tmpdir)
            kwargs = factory(tmp)
            t0 = time.perf_counter()
            try:
                result = await tool.execute(**kwargs)
                ms = (time.perf_counter() - t0) * 1000
                err = None
                if getattr(result, "is_error", False):
                    err = (result.content or "")[:60]
            except Exception as e:
                ms = (time.perf_counter() - t0) * 1000
                err = f"{type(e).__name__}: {str(e)[:60]}"
            rows.append({"tool": tool_name, "shape": shape,
                         "direct_ms": ms, "error": err})
    return rows


async def bench_emit(registry, client: TsunamiModel, force_thinking: bool,
                     with_agent_context: bool = False,
                     agent_system_prompt: str = "",
                     label: str = "B") -> list[dict]:
    """Phase B: minimal prompt → forced tool_call.
    Phase C: same prompt, but with the full agent system prompt prepended.

    The delta between B and C is the tax the agent's system prompt + skills
    load imposes on every tool emission.
    """
    rows = []
    all_schemas = registry.schemas()
    for tool_name, shape, factory, planning in CASES:
        tool = registry.get(tool_name)
        if tool is None:
            rows.append({"tool": tool_name, "shape": shape,
                         "emit_ms": None, "error": "not in registry"})
            continue
        with tempfile.TemporaryDirectory(prefix="bench_", dir="workspace") as tmpdir:
            tmp = Path(tmpdir)
            kwargs = factory(tmp)
            args_summary = json.dumps(kwargs, default=str)[:300]
            user_prompt = (
                f"Call the `{tool_name}` tool with these arguments:\n"
                f"{args_summary}\n\n"
                "Emit the tool call now. No prose, no thinking aloud, just the tool call."
            )
            messages: list[dict] = []
            if with_agent_context and agent_system_prompt:
                messages.append({"role": "system", "content": agent_system_prompt})
            messages.append({"role": "user", "content": user_prompt})
            # Report rough message size so the table can show cost-per-byte.
            prompt_chars = sum(len(m["content"]) for m in messages)
            thinking = force_thinking if force_thinking else planning
            t0 = time.perf_counter()
            err = None
            tc_name = None
            try:
                resp = await client.generate(
                    messages,
                    tools=all_schemas,
                    force_tool=tool_name,
                    enable_thinking=thinking,
                )
                ms = (time.perf_counter() - t0) * 1000
                if resp.tool_calls:
                    tc_name = resp.tool_calls[0].get("function", {}).get("name")
                else:
                    err = f"no tool_call (content preview: {(resp.content or '')[:40]})"
            except Exception as e:
                ms = (time.perf_counter() - t0) * 1000
                err = f"{type(e).__name__}: {str(e)[:60]}"
            rows.append({"tool": tool_name, "shape": shape,
                         "emit_ms": ms, "emitted_name": tc_name,
                         "thinking": thinking,
                         "prompt_chars": prompt_chars,
                         "phase": label,
                         "error": err})
    return rows


def render_markdown(direct_rows: list[dict], emit_rows: list[dict] | None) -> str:
    out = []
    out.append("# Tool latency bench\n")
    out.append("## Phase A — direct tool.execute() only\n")
    out.append("| tool | shape | direct ms | error |")
    out.append("|---|---|---:|---|")
    for r in direct_rows:
        ms = f"{r['direct_ms']:.1f}" if r["direct_ms"] is not None else "—"
        err = r.get("error") or ""
        out.append(f"| `{r['tool']}` | {r['shape']} | {ms} | {err} |")
    out.append("")
    if emit_rows:
        out.append("## Phase B — forced-tool model emission (prompt → tool_call)\n")
        out.append("| tool | shape | thinking | emit ms | emitted name | error |")
        out.append("|---|---|---|---:|---|---|")
        for r in emit_rows:
            ms = f"{r['emit_ms']:.1f}" if r["emit_ms"] is not None else "—"
            th = "T" if r.get("thinking") else "F"
            en = r.get("emitted_name") or ""
            err = r.get("error") or ""
            out.append(f"| `{r['tool']}` | {r['shape']} | {th} | {ms} | {en} | {err} |")
    return "\n".join(out)


async def main(args):
    cfg = TsunamiConfig()
    registry = build_registry(cfg)
    client = TsunamiModel(
        model=cfg.model_name,
        endpoint=cfg.model_endpoint,
        temperature=cfg.temperature,
        max_tokens=2048,
        top_p=cfg.top_p,
        top_k=cfg.top_k,
        min_p=cfg.min_p,
        presence_penalty=cfg.presence_penalty,
        repetition_penalty=cfg.repetition_penalty,
    )

    print("Phase A — direct tool.execute()...", flush=True)
    direct_rows = await bench_direct(registry)

    emit_rows = None
    if not args.skip_emit:
        print("Phase B — model emission (slower; one prompt per row)...", flush=True)
        emit_rows = await bench_emit(registry, client, force_thinking=args.thinking)

    md = render_markdown(direct_rows, emit_rows)
    print()
    print(md)

    if args.out:
        Path(args.out).write_text(md)
        print(f"\nSaved to {args.out}", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--thinking", action="store_true",
                    help="Force enable_thinking=True on every row (overrides default).")
    ap.add_argument("--skip-emit", action="store_true",
                    help="Skip phase B (model emission) — just run phase A.")
    ap.add_argument("--out", default="docs/bench_tools.md",
                    help="Write markdown to this path (default: docs/bench_tools.md).")
    asyncio.run(main(ap.parse_args()))
