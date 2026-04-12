#!/usr/bin/env python3
"""Eval suite for the form-app adapter.

L1 — routing: form-app prompts → project_init; questions → message_chat
L2 — scaffold: project_init(template="form-app") + file_write(src/App.tsx)
L3 — error recovery: fetch()→file_edit, missing papaparse→shell_exec, bad path→shell_exec
L4 — hack-free: FAF01-FAF06 (template param, parseFile, DataTable, exportCsv, undertow, no-main.tsx)

Usage:
  python training/eval_formapp.py --endpoint http://localhost:8090 --adapter form-app-v1 [--quick]
"""
import argparse, asyncio, json, re
from datetime import date
from pathlib import Path
import httpx

ENDPOINT = "http://localhost:8090"
ADAPTER = "form-app-v1"
TIMEOUT = 90

SYSTEM = (
    "You are Tsunami. You are the wave. You build apps by calling tools.\n\n"
    "FORM-APP PIPELINE (file upload / data table apps follow this EXACTLY):\n"
    "1. project_init(name, template='form-app')\n"
    "2. file_write(src/App.tsx) -- import FileDropzone, DataTable, parseFile, exportCsv\n"
    "3. shell_exec -- npm run build\n"
    "4. IF ERROR: fix directly\n"
    "5. undertow -- QA before delivery\n"
    "6. message_result -- land the wave\n\n"
    "FORM-APP RULES:\n"
    "- ALWAYS template='form-app' in project_init\n"
    "- ALWAYS use parseFile(file) for CSV/Excel — NEVER fetch() a file\n"
    "- ALWAYS use <DataTable> — never raw <table>\n"
    "- ALWAYS use exportCsv() for downloads\n"
    "- NEVER overwrite main.tsx, vite.config.ts, or index.css\n"
    "- NEVER skip undertow before message_result\n\n"
    "One tool call per response."
)

TOOLS = [
    {"type": "function", "function": {"name": "project_init", "description": "Create a project.", "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "template": {"type": "string"}}, "required": ["name"]}}},
    {"type": "function", "function": {"name": "file_write", "description": "Write a file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "file_edit", "description": "Edit a file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]}}},
    {"type": "function", "function": {"name": "shell_exec", "description": "Run a shell command.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
    {"type": "function", "function": {"name": "message_result", "description": "Deliver final outcome.", "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": []}}},
    {"type": "function", "function": {"name": "message_chat", "description": "Talk to user.", "parameters": {"type": "object", "properties": {"text": {"type": "string"}, "done": {"type": "boolean"}}, "required": ["text"]}}},
    {"type": "function", "function": {"name": "undertow", "description": "QA test an HTML file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
]


async def chat(client, messages):
    r = await client.post(
        f"{ENDPOINT}/v1/chat/completions",
        json={"model": ADAPTER, "messages": messages, "tools": TOOLS, "max_tokens": 512},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]


def first_tool(msg):
    calls = msg.get("tool_calls") or []
    if calls:
        fn = calls[0]["function"]
        return fn["name"], json.loads(fn.get("arguments", "{}"))
    return None, {}


# ─── L1: Routing ─────────────────────────────────────────────────────────────

L1_CASES = [
    ("FAT01", "Build a CSV file explorer with drag-and-drop upload and data table", "project_init"),
    ("FAT02", "Build a multi-step form wizard with 3 steps and a review screen", "project_init"),
    ("FAT03", "Build an XLSX analyzer that shows each sheet as a tab", "project_init"),
    ("FAT04", "Build a data entry form where I can add rows and export to CSV", "project_init"),
    ("FAT05", "Build a spreadsheet viewer with file dropzone", "project_init"),
    ("FAT06", "What does the parseFile utility return?", "message_chat"),
]


async def run_l1(client):
    results = []
    for test_id, prompt, expected_tool in L1_CASES:
        msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]
        msg = await chat(client, msgs)
        tool, _ = first_tool(msg)
        passed = (tool == expected_tool)
        results.append({"id": test_id, "passed": passed, "expected": expected_tool, "got": tool or "text"})
    return results


# ─── L2: Scaffold ────────────────────────────────────────────────────────────

L2_CASES = [
    ("FAS01", "Build a CSV viewer with upload and table"),
    ("FAS02", "Build a file upload app that shows spreadsheet data"),
    ("FAS03", "Build a form with file dropzone and editable table"),
]


async def run_l2(client):
    results = []
    for test_id, prompt in L2_CASES:
        msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]

        # Step 1: should project_init with template="form-app"
        msg = await chat(client, msgs)
        tool, args = first_tool(msg)
        has_template = (tool == "project_init" and args.get("template") == "form-app")

        if not has_template:
            results.append({"id": test_id, "passed": False, "reason": f"step1 got {tool}(template={args.get('template')!r})"})
            continue

        # Step 2: should file_write(src/App.tsx)
        msgs.append(msg)
        msgs.append({"role": "tool", "tool_call_id": msg["tool_calls"][0]["id"],
                     "content": f"[project_init] Created with template='form-app'. Write src/App.tsx."})
        msg2 = await chat(client, msgs)
        tool2, args2 = first_tool(msg2)
        writes_app = (tool2 == "file_write" and "App.tsx" in args2.get("path", ""))

        passed = has_template and writes_app
        results.append({"id": test_id, "passed": passed,
                        "reason": f"template={'form-app' if has_template else 'MISSING'}, step2={tool2}({args2.get('path','')})"})
    return results


# ─── L3: Error recovery ──────────────────────────────────────────────────────

async def run_l3(client):
    results = []

    # FAER01: fetch() for file → should file_edit to use parseFile
    msgs = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": "Build a CSV viewer"},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "x1", "type": "function",
            "function": {"name": "project_init", "arguments": json.dumps({"name": "csv-viewer", "template": "form-app"})}}]},
        {"role": "tool", "tool_call_id": "x1", "content": "[project_init] Created with template='form-app'."},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "x2", "type": "function",
            "function": {"name": "file_write", "arguments": json.dumps({
                "path": "src/App.tsx",
                "content": "const res = await fetch('/data.csv'); const text = await res.text();"
            })}}]},
        {"role": "tool", "tool_call_id": "x2", "content": "[file_write] src/App.tsx written."},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "x3", "type": "function",
            "function": {"name": "shell_exec", "arguments": json.dumps({"command": "npm run build"})}}]},
        {"role": "tool", "tool_call_id": "x3", "content": "[shell_exec] Warning: fetch('/data.csv') will fail — no server in static build. Build succeeded."},
    ]
    msg = await chat(client, msgs)
    tool, args = first_tool(msg)
    passed = (tool == "file_edit")
    results.append({"id": "FAER01", "passed": passed, "reason": f"fetch in App.tsx → expected file_edit, got {tool}"})

    # FAER02: missing papaparse → should shell_exec npm install
    msgs2 = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": "Build a CSV parser app"},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "y1", "type": "function",
            "function": {"name": "project_init", "arguments": json.dumps({"name": "csv-app", "template": "form-app"})}}]},
        {"role": "tool", "tool_call_id": "y1", "content": "[project_init] Created."},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "y2", "type": "function",
            "function": {"name": "file_write", "arguments": json.dumps({"path": "src/App.tsx", "content": "import Papa from 'papaparse';"})}}]},
        {"role": "tool", "tool_call_id": "y2", "content": "[file_write] src/App.tsx written."},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "y3", "type": "function",
            "function": {"name": "shell_exec", "arguments": json.dumps({"command": "npm run build"})}}]},
        {"role": "tool", "tool_call_id": "y3",
         "content": "[shell_exec] ERROR: Cannot find module 'papaparse'. Build failed."},
    ]
    msg2 = await chat(client, msgs2)
    tool2, args2 = first_tool(msg2)
    passed2 = (tool2 == "shell_exec" and "npm install" in args2.get("command", ""))
    results.append({"id": "FAER02", "passed": passed2, "reason": f"missing papaparse → expected shell_exec npm install, got {tool2}"})

    # FAER03: TypeScript error → should file_edit
    msgs3 = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": "Build a data table app"},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "z1", "type": "function",
            "function": {"name": "project_init", "arguments": json.dumps({"name": "data-app", "template": "form-app"})}}]},
        {"role": "tool", "tool_call_id": "z1", "content": "[project_init] Created."},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "z2", "type": "function",
            "function": {"name": "file_write", "arguments": json.dumps({"path": "src/App.tsx", "content": "const x: string = 42;"})}}]},
        {"role": "tool", "tool_call_id": "z2", "content": "[file_write] src/App.tsx written."},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "z3", "type": "function",
            "function": {"name": "shell_exec", "arguments": json.dumps({"command": "npm run build"})}}]},
        {"role": "tool", "tool_call_id": "z3",
         "content": "[shell_exec] ERROR: src/App.tsx(1,7): Type 'number' is not assignable to type 'string'. Build failed."},
    ]
    msg3 = await chat(client, msgs3)
    tool3, _ = first_tool(msg3)
    passed3 = (tool3 == "file_edit")
    results.append({"id": "FAER03", "passed": passed3, "reason": f"TS error → expected file_edit, got {tool3}"})

    return results


# ─── L4: Hack-free ───────────────────────────────────────────────────────────

async def run_l4(client):
    results = []

    # FAF01: project_init must include template="form-app"
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": "Build a CSV file upload viewer"}]
    msg = await chat(client, msgs)
    tool, args = first_tool(msg)
    passed = (tool == "project_init" and args.get("template") == "form-app")
    results.append({"id": "FAF01", "passed": passed, "reason": f"template={args.get('template')!r}"})

    # FAF02: use parseFile not fetch
    msgs2 = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": "Build a CSV viewer with file upload"},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "a1", "type": "function",
            "function": {"name": "project_init", "arguments": json.dumps({"name": "csv-viewer", "template": "form-app"})}}]},
        {"role": "tool", "tool_call_id": "a1", "content": "[project_init] Created with template='form-app'."},
    ]
    msg2 = await chat(client, msgs2)
    tool2, args2 = first_tool(msg2)
    content2 = args2.get("content", "")
    uses_parse_file = "parseFile" in content2
    uses_fetch = re.search(r'fetch\s*\(', content2)
    passed2 = (tool2 == "file_write" and uses_parse_file and not uses_fetch)
    results.append({"id": "FAF02", "passed": passed2,
                    "reason": f"parseFile={'yes' if uses_parse_file else 'NO'}, fetch={'YES (bad)' if uses_fetch else 'absent'}"})

    # FAF03: use DataTable not raw <table>
    content3 = content2  # reuse from FAF02
    uses_datatable = "DataTable" in content3
    uses_raw_table = bool(re.search(r'<table[\s>]', content3))
    passed3 = (uses_datatable and not uses_raw_table)
    results.append({"id": "FAF03", "passed": passed3,
                    "reason": f"DataTable={'yes' if uses_datatable else 'NO'}, raw table={'YES (bad)' if uses_raw_table else 'absent'}"})

    # FAF04: use exportCsv for downloads
    msgs4 = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": "Build a spreadsheet viewer with export button"},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "b1", "type": "function",
            "function": {"name": "project_init", "arguments": json.dumps({"name": "sheet-viewer", "template": "form-app"})}}]},
        {"role": "tool", "tool_call_id": "b1", "content": "[project_init] Created."},
    ]
    msg4 = await chat(client, msgs4)
    _, args4 = first_tool(msg4)
    content4 = args4.get("content", "")
    uses_export_csv = "exportCsv" in content4
    passed4 = uses_export_csv
    results.append({"id": "FAF04", "passed": passed4, "reason": f"exportCsv={'yes' if uses_export_csv else 'NO'}"})

    # FAF05: undertow before message_result
    msgs5 = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": "Build a file upload CSV viewer"},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "type": "function",
            "function": {"name": "project_init", "arguments": json.dumps({"name": "csv-app", "template": "form-app"})}}]},
        {"role": "tool", "tool_call_id": "c1", "content": "[project_init] Created."},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "c2", "type": "function",
            "function": {"name": "file_write", "arguments": json.dumps({"path": "src/App.tsx", "content": "// app"})}}]},
        {"role": "tool", "tool_call_id": "c2", "content": "[file_write] src/App.tsx written."},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "c3", "type": "function",
            "function": {"name": "shell_exec", "arguments": json.dumps({"command": "npm run build"})}}]},
        {"role": "tool", "tool_call_id": "c3", "content": "[shell_exec] Build succeeded. dist/index.html ready."},
    ]
    msg5 = await chat(client, msgs5)
    tool5, _ = first_tool(msg5)
    passed5 = (tool5 == "undertow")
    results.append({"id": "FAF05", "passed": passed5, "reason": f"after build → expected undertow, got {tool5}"})

    # FAF06: never overwrite main.tsx
    msgs6 = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": "Build a data table app with file upload"},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "d1", "type": "function",
            "function": {"name": "project_init", "arguments": json.dumps({"name": "data-app", "template": "form-app"})}}]},
        {"role": "tool", "tool_call_id": "d1", "content": "[project_init] Created with template='form-app'. Write src/App.tsx."},
    ]
    msg6 = await chat(client, msgs6)
    tool6, args6 = first_tool(msg6)
    path6 = args6.get("path", "")
    passed6 = (tool6 == "file_write" and "App.tsx" in path6 and "main.tsx" not in path6)
    results.append({"id": "FAF06", "passed": passed6, "reason": f"wrote {path6!r}"})

    return results


# ─── Main ─────────────────────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", default=ENDPOINT)
    parser.add_argument("--adapter", default=ADAPTER)
    parser.add_argument("--quick", action="store_true", help="L1+L2 only")
    parser.add_argument("--out", default="workspace/eval_results/formapp_eval.json")
    args = parser.parse_args()

    global ENDPOINT, ADAPTER
    ENDPOINT = args.endpoint
    ADAPTER = args.adapter

    async with httpx.AsyncClient() as client:
        print(f"=== FORM-APP EVAL — {args.adapter} ===\n")

        l1 = await run_l1(client)
        l1_pass = sum(r["passed"] for r in l1)
        print(f"L1 Routing:        {l1_pass}/{len(l1)}")
        for r in l1:
            mark = "✓" if r["passed"] else "✗"
            print(f"  {mark} {r['id']}: expected {r['expected']!r}, got {r['got']!r}")

        l2 = await run_l2(client)
        l2_pass = sum(r["passed"] for r in l2)
        print(f"\nL2 Scaffold:       {l2_pass}/{len(l2)}")
        for r in l2:
            mark = "✓" if r["passed"] else "✗"
            print(f"  {mark} {r['id']}: {r['reason']}")

        if args.quick:
            total = l1_pass + l2_pass
            out_of = len(l1) + len(l2)
            print(f"\nQUICK TOTAL: {total}/{out_of} ({100*total//out_of}%)")
            return

        l3 = await run_l3(client)
        l3_pass = sum(r["passed"] for r in l3)
        print(f"\nL3 Error Recovery: {l3_pass}/{len(l3)}")
        for r in l3:
            mark = "✓" if r["passed"] else "✗"
            print(f"  {mark} {r['id']}: {r['reason']}")

        l4 = await run_l4(client)
        l4_pass = sum(r["passed"] for r in l4)
        print(f"\nL4 Hack-Free:      {l4_pass}/{len(l4)}")
        for r in l4:
            mark = "✓" if r["passed"] else "✗"
            print(f"  {mark} {r['id']}: {r['reason']}")

        total = l1_pass + l2_pass + l3_pass + l4_pass
        out_of = len(l1) + len(l2) + len(l3) + len(l4)
        print(f"\nTOTAL: {total}/{out_of} ({100*total//out_of}%)")

        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({
            "adapter": args.adapter, "date": date.today().isoformat(),
            "l1": f"{l1_pass}/{len(l1)}", "l2": f"{l2_pass}/{len(l2)}",
            "l3": f"{l3_pass}/{len(l3)}", "l4": f"{l4_pass}/{len(l4)}",
            "total": f"{total}/{out_of}", "pct": total / out_of,
            "results": {"l1": l1, "l2": l2, "l3": l3, "l4": l4},
        }, indent=2))
        print(f"Results saved to {args.out}")


if __name__ == "__main__":
    asyncio.run(main())
