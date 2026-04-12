#!/usr/bin/env python3
"""Data-viz adapter eval — L1-L4.

Tests the gemma-4-e4b data-viz adapter against patterns specific to the
data-viz scaffold: ChartCard wrapping, ResponsiveContainer usage, no raw
fetch() for chart data, proper Recharts imports.

Usage:
  python training/eval_dataviz.py --endpoint http://localhost:8090 --adapter dataviz-v1 --quick
  python training/eval_dataviz.py --endpoint http://localhost:8090 --adapter dataviz-v1
"""
import argparse
import asyncio
import json
import logging
import os
import re
import sys
import time
from pathlib import Path

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("eval_dataviz")

DV_SYSTEM = """You are Tsunami. You are the wave. You build data-visualization dashboards by calling tools.

## Data-Viz Pipeline (every build follows this EXACTLY)

1. project_init(name, template="data-viz") -- create project from data-viz scaffold
2. file_write(src/App.tsx) -- write complete dashboard using ChartCard + Recharts
3. shell_exec -- run npm run build
4. IF ERROR: fix directly with file_edit
5. undertow -- QA before delivery
6. message_result -- land the wave

## Component Rules

- ALWAYS import ChartCard, StatRow from './components'
- ALWAYS wrap every Recharts chart in <ResponsiveContainer width="100%" height={300}>
- NEVER use raw fetch() for chart data -- hardcode sample data arrays or use CsvLoader
- Use BarChart for comparisons, LineChart for trends, AreaChart for volume, PieChart for parts-of-whole
- StatRow for summary KPIs above charts

## Available Components

ChartCard: <ChartCard title="Revenue">...</ChartCard>
StatRow: <StatRow stats={[{label, value, change?}]} />
CsvLoader: <CsvLoader onData={(rows) => setData(rows)} />

## One tool call per response. Be brief.
"""

DV_TOOLS = [
    {"type": "function", "function": {
        "name": "project_init",
        "description": "Create a project from the scaffold library.",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string"},
            "template": {"type": "string"},
        }, "required": ["name"]},
    }},
    {"type": "function", "function": {
        "name": "file_write",
        "description": "Create or overwrite a file with full content.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]},
    }},
    {"type": "function", "function": {
        "name": "file_edit",
        "description": "Make targeted modifications to an existing file.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]},
    }},
    {"type": "function", "function": {
        "name": "shell_exec",
        "description": "Run a shell command and return its output.",
        "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]},
    }},
    {"type": "function", "function": {
        "name": "undertow",
        "description": "QA-test an HTML file in a headless browser before delivery.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
    }},
    {"type": "function", "function": {
        "name": "message_result",
        "description": "Deliver final outcome and end the task.",
        "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": []},
    }},
    {"type": "function", "function": {
        "name": "message_chat",
        "description": "Talk to the user. done=true ends, done=false continues.",
        "parameters": {"type": "object", "properties": {"text": {"type": "string"}, "done": {"type": "boolean"}}, "required": ["text"]},
    }},
]

# ---------------------------------------------------------------------------
# L1 Format — does the model pick the right first tool?
# ---------------------------------------------------------------------------
DV_FORMAT_PROMPTS = [
    {"id": "DT01", "prompt": "Build a sales dashboard with monthly revenue charts",
     "expected": "project_init"},
    {"id": "DT02", "prompt": "Build a data visualization for website traffic analytics",
     "expected": "project_init"},
    {"id": "DT03", "prompt": "Build a dashboard that lets me upload a CSV and see bar charts",
     "expected": "project_init"},
    {"id": "DT04", "prompt": "Hello, what kinds of charts can you build?",
     "expected": "message_chat"},
    {"id": "DT05", "prompt": "Build a portfolio performance chart with line graphs",
     "expected": "project_init"},
    {"id": "DT06", "prompt": "Make a retention heatmap dashboard for user cohorts",
     "expected": "project_init"},
]

# ---------------------------------------------------------------------------
# L2 Scaffold — project_init gets called, App.tsx uses ChartCard/Recharts
# ---------------------------------------------------------------------------
DV_SCAFFOLD_PROMPTS = [
    {"id": "DS01", "prompt": "Build a bar chart dashboard showing monthly sales by region"},
    {"id": "DS02", "prompt": "Build a line chart for tracking crypto prices over time"},
    {"id": "DS03", "prompt": "Build a pie chart dashboard showing product category breakdown"},
]

# ---------------------------------------------------------------------------
# L3 Error Recovery
# ---------------------------------------------------------------------------
DV_ERROR_SCENARIOS = [
    {
        "id": "DER01", "name": "missing-responsive-container",
        "messages": [
            {"role": "system", "content": DV_SYSTEM},
            {"role": "user", "content": "Build a revenue bar chart dashboard"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c1", "type": "function", "function": {
                    "name": "project_init", "arguments": json.dumps({"name": "revenue-dashboard", "template": "data-viz"})}}
            ]},
            {"role": "tool", "tool_call_id": "c1",
             "content": "[project_init] Created 'revenue-dashboard' from data-viz scaffold. Write src/App.tsx."},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c2", "type": "function", "function": {
                    "name": "file_write", "arguments": json.dumps({"path": "src/App.tsx", "content": "// app"})}}
            ]},
            {"role": "tool", "tool_call_id": "c2", "content": "[file_write] Written."},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c3", "type": "function", "function": {
                    "name": "shell_exec", "arguments": json.dumps({"command": "cd deliverables/revenue-dashboard && npm run build"})}}
            ]},
            {"role": "tool", "tool_call_id": "c3",
             "content": "[shell_exec] Error: Warning: BarChart is not wrapped in a ResponsiveContainer. Width/height will be 0. Build failed."},
        ],
        "expected_tool": "file_edit",
        "reject_tools": ["message_chat", "message_result", "project_init"],
    },
    {
        "id": "DER02", "name": "recharts-import-error",
        "messages": [
            {"role": "system", "content": DV_SYSTEM},
            {"role": "user", "content": "Build a line chart for monthly expenses"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c1", "type": "function", "function": {
                    "name": "project_init", "arguments": json.dumps({"name": "expense-chart", "template": "data-viz"})}}
            ]},
            {"role": "tool", "tool_call_id": "c1",
             "content": "[project_init] Created 'expense-chart' from data-viz scaffold. Write src/App.tsx."},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c2", "type": "function", "function": {
                    "name": "file_write", "arguments": json.dumps({"path": "src/App.tsx", "content": "import { LineChart } from 'recharts'"})}}
            ]},
            {"role": "tool", "tool_call_id": "c2", "content": "[file_write] Written."},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c3", "type": "function", "function": {
                    "name": "shell_exec", "arguments": json.dumps({"command": "cd deliverables/expense-chart && npm run build"})}}
            ]},
            {"role": "tool", "tool_call_id": "c3",
             "content": "[shell_exec] Error: Module not found: recharts. Did you mean to install it? Run: npm install recharts"},
        ],
        "expected_tool": "shell_exec",
        "content_check": "recharts",
        "reject_tools": ["message_chat", "message_result"],
    },
    {
        "id": "DER03", "name": "csv-fetch-wrong",
        "messages": [
            {"role": "system", "content": DV_SYSTEM},
            {"role": "user", "content": "Build a CSV data explorer with charts"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c1", "type": "function", "function": {
                    "name": "project_init", "arguments": json.dumps({"name": "csv-explorer", "template": "data-viz"})}}
            ]},
            {"role": "tool", "tool_call_id": "c1",
             "content": "[project_init] Created 'csv-explorer' from data-viz scaffold. Write src/App.tsx."},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c2", "type": "function", "function": {
                    "name": "file_write", "arguments": json.dumps({"path": "src/App.tsx", "content": "fetch('/api/data').then(...)"})}}
            ]},
            {"role": "tool", "tool_call_id": "c2", "content": "[file_write] Written."},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c3", "type": "function", "function": {
                    "name": "shell_exec", "arguments": json.dumps({"command": "cd deliverables/csv-explorer && npm run build"})}}
            ]},
            {"role": "tool", "tool_call_id": "c3",
             "content": "[shell_exec] Build OK. Warning: fetch('/api/data') will fail — no server running. Use CsvLoader component instead."},
        ],
        "expected_tool": "file_edit",
        "reject_tools": ["message_chat", "message_result"],
    },
]

# ---------------------------------------------------------------------------
# L4 Hack-Free
# ---------------------------------------------------------------------------
DV_HACK_SCENARIOS = [
    {
        "id": "DVF01", "hack": "ChartCard usage",
        "desc": "App.tsx should use ChartCard wrapper, not raw <div> around charts",
        "messages": [
            {"role": "system", "content": DV_SYSTEM},
            {"role": "user", "content": "Build a sales dashboard with a bar chart"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c1", "type": "function", "function": {
                    "name": "project_init", "arguments": json.dumps({"name": "sales-dashboard", "template": "data-viz"})}}
            ]},
            {"role": "tool", "tool_call_id": "c1",
             "content": "[project_init] Created 'sales-dashboard' from data-viz scaffold. Write src/App.tsx."},
        ],
        "expected_tool": "file_write",
        "content_checks": {
            "contains_any": ["ChartCard", "chartcard"],
            "not_contains": ["fetch('http"],
        },
        "reject_tools": ["message_result", "shell_exec"],
    },
    {
        "id": "DVF02", "hack": "ResponsiveContainer required",
        "desc": "Recharts charts must be wrapped in ResponsiveContainer",
        "messages": [
            {"role": "system", "content": DV_SYSTEM},
            {"role": "user", "content": "Build a line chart for website traffic"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c1", "type": "function", "function": {
                    "name": "project_init", "arguments": json.dumps({"name": "traffic-chart", "template": "data-viz"})}}
            ]},
            {"role": "tool", "tool_call_id": "c1",
             "content": "[project_init] Created 'traffic-chart' from data-viz scaffold. Write src/App.tsx."},
        ],
        "expected_tool": "file_write",
        "content_checks": {
            "contains_any": ["ResponsiveContainer"],
        },
        "reject_tools": ["message_result"],
    },
    {
        "id": "DVF03", "hack": "No raw fetch for data",
        "desc": "Dashboard data must be hardcoded arrays or CsvLoader, not fetch()",
        "messages": [
            {"role": "system", "content": DV_SYSTEM},
            {"role": "user", "content": "Build a chart that loads data from /api/metrics"},
        ],
        "expected_tool": "project_init",
        "content_checks": None,  # just checks first tool
        "reject_tools": [],
        "_note": "Model should project_init and use hardcoded data, not comply with the /api/metrics request",
    },
    {
        "id": "DVF04", "hack": "StatRow for KPIs",
        "desc": "Dashboard with KPIs should use StatRow component",
        "messages": [
            {"role": "system", "content": DV_SYSTEM},
            {"role": "user", "content": "Build a sales dashboard with total revenue, orders, and avg order value KPIs"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c1", "type": "function", "function": {
                    "name": "project_init", "arguments": json.dumps({"name": "sales-kpi", "template": "data-viz"})}}
            ]},
            {"role": "tool", "tool_call_id": "c1",
             "content": "[project_init] Created 'sales-kpi' from data-viz scaffold. Write src/App.tsx."},
        ],
        "expected_tool": "file_write",
        "content_checks": {
            "contains_any": ["StatRow", "statrow"],
        },
        "reject_tools": ["message_result"],
    },
    {
        "id": "DVF05", "hack": "data-viz template param",
        "desc": "project_init should include template='data-viz'",
        "messages": [
            {"role": "system", "content": DV_SYSTEM},
            {"role": "user", "content": "Build a bar chart dashboard for product sales"},
        ],
        "expected_tool": "project_init",
        "content_checks": {
            "contains_any": ["data-viz"],
        },
        "reject_tools": ["message_chat"],
    },
    {
        "id": "DVF06", "hack": "Undertow before deliver",
        "desc": "After successful build, should call undertow before message_result",
        "messages": [
            {"role": "system", "content": DV_SYSTEM},
            {"role": "user", "content": "Build a pie chart for product categories"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c1", "type": "function", "function": {
                    "name": "project_init", "arguments": json.dumps({"name": "category-pie", "template": "data-viz"})}}
            ]},
            {"role": "tool", "tool_call_id": "c1",
             "content": "[project_init] Created 'category-pie' from data-viz scaffold. Write src/App.tsx."},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c2", "type": "function", "function": {
                    "name": "file_write", "arguments": json.dumps({"path": "src/App.tsx", "content": "// app"})}}
            ]},
            {"role": "tool", "tool_call_id": "c2", "content": "[file_write] Written."},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c3", "type": "function", "function": {
                    "name": "shell_exec", "arguments": json.dumps({"command": "cd deliverables/category-pie && npm run build"})}}
            ]},
            {"role": "tool", "tool_call_id": "c3", "content": "[shell_exec] Build succeeded. dist/ ready."},
        ],
        "expected_tool": "undertow",
        "reject_tools": ["message_result"],
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_tool_call(content: str):
    """Parse first tool_call from response content or tool_calls field."""
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                return block.get("name"), block.get("input", {})
    if isinstance(content, str):
        m = re.search(r'"name"\s*:\s*"(\w+)"', content)
        if m:
            return m.group(1), {}
    return None, {}


async def _call(client: httpx.AsyncClient, endpoint: str, adapter: str, messages: list,
                timeout: float = 300.0) -> dict:
    payload = {
        "model": "tsunami",
        "messages": messages,
        "tools": DV_TOOLS,
        "max_tokens": 512,
        "temperature": 0.0,
    }
    if adapter and adapter != "none":
        payload["adapter"] = adapter
    r = await client.post(f"{endpoint}/v1/chat/completions", json=payload, timeout=timeout)
    r.raise_for_status()
    return r.json()


def _get_tool_name(resp: dict) -> str | None:
    choices = resp.get("choices", [])
    if not choices:
        return None
    msg = choices[0].get("message", {})
    tc = msg.get("tool_calls", [])
    if tc:
        return tc[0].get("function", {}).get("name")
    # fallback: scan content text
    name, _ = _extract_tool_call(msg.get("content", ""))
    return name


def _get_tool_args(resp: dict) -> dict:
    choices = resp.get("choices", [])
    if not choices:
        return {}
    msg = choices[0].get("message", {})
    tc = msg.get("tool_calls", [])
    if tc:
        raw = tc[0].get("function", {}).get("arguments", "{}")
        try:
            return json.loads(raw)
        except Exception:
            return {"_raw": raw}
    return {}


# ---------------------------------------------------------------------------
# Level runners
# ---------------------------------------------------------------------------

async def run_l1(client, endpoint, adapter, quick):
    passed, total = 0, 0
    for p in DV_FORMAT_PROMPTS:
        msgs = [{"role": "system", "content": DV_SYSTEM}, {"role": "user", "content": p["prompt"]}]
        try:
            resp = await _call(client, endpoint, adapter, msgs)
            tool = _get_tool_name(resp)
            ok = tool == p["expected"]
            log.info(f"  L1 {p['id']}: {'PASS' if ok else 'FAIL'} — got={tool!r} want={p['expected']!r}")
            if ok:
                passed += 1
        except Exception as e:
            log.error(f"  L1 {p['id']}: ERROR — {e}")
        total += 1
        if quick and total >= 3:
            break
    return passed, total


async def run_l2(client, endpoint, adapter, quick):
    """Check first two tools: project_init → file_write(App.tsx)."""
    passed, total = 0, 0
    for p in DV_SCAFFOLD_PROMPTS:
        msgs = [{"role": "system", "content": DV_SYSTEM}, {"role": "user", "content": p["prompt"]}]
        try:
            resp1 = await _call(client, endpoint, adapter, msgs)
            tool1 = _get_tool_name(resp1)
            args1 = _get_tool_args(resp1)
            ok1 = tool1 == "project_init" and "data-viz" in json.dumps(args1)

            if ok1:
                # Continue to step 2
                init_result = f"[project_init] Created '{args1.get('name', 'project')}' from data-viz scaffold. Write src/App.tsx."
                msgs2 = msgs + [
                    {"role": "assistant", "content": "", "tool_calls": [
                        {"id": "s2c1", "type": "function", "function": {
                            "name": "project_init", "arguments": json.dumps(args1)}}
                    ]},
                    {"role": "tool", "tool_call_id": "s2c1", "content": init_result},
                ]
                resp2 = await _call(client, endpoint, adapter, msgs2)
                tool2 = _get_tool_name(resp2)
                args2 = _get_tool_args(resp2)
                ok2 = tool2 == "file_write" and "App.tsx" in args2.get("path", "")
                ok = ok1 and ok2
                log.info(f"  L2 {p['id']}: {'PASS' if ok else 'FAIL'} — t1={tool1!r}(data-viz={ok1}) t2={tool2!r}(App={ok2})")
            else:
                ok = False
                log.info(f"  L2 {p['id']}: FAIL — t1={tool1!r} (missing data-viz template)")
            if ok:
                passed += 1
        except Exception as e:
            log.error(f"  L2 {p['id']}: ERROR — {e}")
        total += 1
        if quick and total >= 2:
            break
    return passed, total


async def run_l3(client, endpoint, adapter, quick):
    passed, total = 0, 0
    for s in DV_ERROR_SCENARIOS:
        try:
            resp = await _call(client, endpoint, adapter, s["messages"])
            tool = _get_tool_name(resp)
            args = _get_tool_args(resp)
            ok = tool == s["expected_tool"]
            if ok and "content_check" in s:
                ok = s["content_check"].lower() in json.dumps(args).lower()
            if tool in s.get("reject_tools", []):
                ok = False
            log.info(f"  L3 {s['id']}: {'PASS' if ok else 'FAIL'} — got={tool!r} want={s['expected_tool']!r}")
            if ok:
                passed += 1
        except Exception as e:
            log.error(f"  L3 {s['id']}: ERROR — {e}")
        total += 1
        if quick and total >= 2:
            break
    return passed, total


async def run_l4(client, endpoint, adapter, quick):
    passed, total = 0, 0
    for s in DV_HACK_SCENARIOS:
        try:
            resp = await _call(client, endpoint, adapter, s["messages"])
            tool = _get_tool_name(resp)
            args = _get_tool_args(resp)
            ok = tool == s["expected_tool"]

            if ok and tool in s.get("reject_tools", []):
                ok = False

            if ok and s.get("content_checks"):
                checks = s["content_checks"]
                content_str = json.dumps(args)
                if "contains_any" in checks:
                    ok = ok and any(c.lower() in content_str.lower() for c in checks["contains_any"])
                if "not_contains" in checks:
                    ok = ok and all(c not in content_str for c in checks["not_contains"])

            log.info(f"  L4 {s['id']}: {'PASS' if ok else 'FAIL'} — tool={tool!r} [{s['hack']}]")
            if ok:
                passed += 1
        except Exception as e:
            log.error(f"  L4 {s['id']}: ERROR — {e}")
        total += 1
        if quick and total >= 4:
            break
    return passed, total


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--endpoint", default="http://localhost:8090")
    ap.add_argument("--adapter", default="dataviz-v1")
    ap.add_argument("--quick", action="store_true", help="Run subset only")
    args = ap.parse_args()

    log.info(f"eval_dataviz — endpoint={args.endpoint} adapter={args.adapter} quick={args.quick}")

    async with httpx.AsyncClient() as client:
        l1p, l1t = await run_l1(client, args.endpoint, args.adapter, args.quick)
        l2p, l2t = await run_l2(client, args.endpoint, args.adapter, args.quick)
        l3p, l3t = await run_l3(client, args.endpoint, args.adapter, args.quick)
        l4p, l4t = await run_l4(client, args.endpoint, args.adapter, args.quick)

    total_p = l1p + l2p + l3p + l4p
    total_t = l1t + l2t + l3t + l4t
    print(f"\n=== DATAVIZ EVAL RESULTS ===")
    print(f"  L1 Format:          {l1p}/{l1t}")
    print(f"  L2 Scaffold:        {l2p}/{l2t}")
    print(f"  L3 Error Recovery:  {l3p}/{l3t}")
    print(f"  L4 Hack-Free:       {l4p}/{l4t}")
    print(f"  TOTAL:              {total_p}/{total_t}  ({total_p/max(total_t,1)*100:.1f}%)")

    out = {
        "adapter": args.adapter, "endpoint": args.endpoint,
        "quick": args.quick,
        "l1": f"{l1p}/{l1t}", "l2": f"{l2p}/{l2t}",
        "l3": f"{l3p}/{l3t}", "l4": f"{l4p}/{l4t}",
        "total": f"{total_p}/{total_t}",
        "pct": round(total_p / max(total_t, 1), 3),
    }
    out_path = Path("workspace/eval_results") / f"dataviz_{args.adapter}_{int(time.time())}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2))
    log.info(f"Results saved: {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
