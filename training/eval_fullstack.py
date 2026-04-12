#!/usr/bin/env python3
"""Fullstack adapter eval — L1-L4.

Tests the gemma-4-e4b fullstack-v1 adapter against patterns specific to
the fullstack scaffold: server/index.js before App.tsx, useApi hook usage
(not raw fetch), correct template param, undertow before deliver.

Usage:
  python training/eval_fullstack.py --endpoint http://localhost:8090 --adapter fullstack-v1 --quick
  python training/eval_fullstack.py --endpoint http://localhost:8090 --adapter fullstack-v1
"""
import argparse
import asyncio
import json
import logging
import re
import sys
import time
from pathlib import Path

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("eval_fullstack")

FS_SYSTEM = """You are Tsunami. You are the wave. You build full-stack apps by calling tools.

## Fullstack Pipeline (every build follows this EXACTLY)

1. project_init(name, template="fullstack") -- create project from fullstack scaffold
2. file_write(server/index.js) -- Express + SQLite backend (tables + crudRoutes)
3. file_write(src/App.tsx) -- React frontend using useApi hook
4. shell_exec -- run npm run build
5. IF ERROR: fix directly with file_edit
6. undertow -- QA before delivery
7. message_result -- land the wave

## Backend Pattern (server/index.js)

```js
import express from "express"
import cors from "cors"
import Database from "better-sqlite3"
// db.exec(`CREATE TABLE IF NOT EXISTS items (...)`)
// crudRoutes("items")
// app.listen(PORT)
```

## Frontend Pattern (src/App.tsx)

```tsx
import { useApi } from './components/useApi'
const { data, loading, error, create, update, remove } = useApi<Item>("items")
```

## Rules
- NEVER use raw fetch() in frontend -- use useApi hook
- ALWAYS write server/index.js BEFORE src/App.tsx
- NEVER overwrite main.tsx, vite.config.ts, or index.css
- One tool call per response. Be brief.
"""

FS_TOOLS = [
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
# L1 Format
# ---------------------------------------------------------------------------
FS_FORMAT_PROMPTS = [
    {"id": "FT01", "prompt": "Build a todo app with SQLite persistence",
     "expected": "project_init"},
    {"id": "FT02", "prompt": "Build a notes app with an Express backend and SQLite database",
     "expected": "project_init"},
    {"id": "FT03", "prompt": "Build a full-stack expense tracker with a database backend",
     "expected": "project_init"},
    {"id": "FT04", "prompt": "Hello, what kind of databases can you use in a fullstack app?",
     "expected": "message_chat"},
    {"id": "FT05", "prompt": "Build a bookmark manager with SQLite storage",
     "expected": "project_init"},
    {"id": "FT06", "prompt": "Build a CRUD app for managing contacts with a REST API",
     "expected": "project_init"},
]

# ---------------------------------------------------------------------------
# L2 Scaffold — project_init with template="fullstack", then server/index.js first
# ---------------------------------------------------------------------------
FS_SCAFFOLD_PROMPTS = [
    {"id": "FS01", "prompt": "Build a persistent inventory tracker with SQLite"},
    {"id": "FS02", "prompt": "Build a task manager with an Express backend"},
    {"id": "FS03", "prompt": "Build a budget tracker backed by a database"},
]

# ---------------------------------------------------------------------------
# L3 Error Recovery
# ---------------------------------------------------------------------------
FS_ERROR_SCENARIOS = [
    {
        "id": "FER01", "name": "raw-fetch-error",
        "messages": [
            {"role": "system", "content": FS_SYSTEM},
            {"role": "user", "content": "Build a todo app with SQLite"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c1", "type": "function", "function": {
                    "name": "project_init", "arguments": json.dumps({"name": "todo-app", "template": "fullstack"})}}
            ]},
            {"role": "tool", "tool_call_id": "c1",
             "content": "[project_init] Created 'todo-app' from fullstack scaffold. Write server/index.js then src/App.tsx."},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c2", "type": "function", "function": {
                    "name": "file_write", "arguments": json.dumps({"path": "server/index.js", "content": "// server"})}}
            ]},
            {"role": "tool", "tool_call_id": "c2", "content": "[file_write] Written."},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c3", "type": "function", "function": {
                    "name": "file_write", "arguments": json.dumps({"path": "src/App.tsx", "content": "fetch('/api/todos').then(r=>r.json()).then(setTodos)"})}}
            ]},
            {"role": "tool", "tool_call_id": "c3", "content": "[file_write] Written."},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c4", "type": "function", "function": {
                    "name": "shell_exec", "arguments": json.dumps({"command": "cd deliverables/todo-app && npm run build"})}}
            ]},
            {"role": "tool", "tool_call_id": "c4",
             "content": "[shell_exec] Error: src/App.tsx(1,1): TS7006: Parameter implicitly has 'any' type. Also: raw fetch() detected — use useApi hook from ./components/useApi instead."},
        ],
        "expected_tool": "file_edit",
        "reject_tools": ["message_chat", "message_result", "project_init"],
    },
    {
        "id": "FER02", "name": "missing-better-sqlite3",
        "messages": [
            {"role": "system", "content": FS_SYSTEM},
            {"role": "user", "content": "Build a notes app with SQLite persistence"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c1", "type": "function", "function": {
                    "name": "project_init", "arguments": json.dumps({"name": "notes-app", "template": "fullstack"})}}
            ]},
            {"role": "tool", "tool_call_id": "c1",
             "content": "[project_init] Created 'notes-app' from fullstack scaffold. Write server/index.js then src/App.tsx."},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c2", "type": "function", "function": {
                    "name": "file_write", "arguments": json.dumps({"path": "server/index.js", "content": "import Database from 'better-sqlite3'"})}}
            ]},
            {"role": "tool", "tool_call_id": "c2", "content": "[file_write] Written."},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c3", "type": "function", "function": {
                    "name": "file_write", "arguments": json.dumps({"path": "src/App.tsx", "content": "// app"})}}
            ]},
            {"role": "tool", "tool_call_id": "c3", "content": "[file_write] Written."},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c4", "type": "function", "function": {
                    "name": "shell_exec", "arguments": json.dumps({"command": "cd deliverables/notes-app && npm run build"})}}
            ]},
            {"role": "tool", "tool_call_id": "c4",
             "content": "[shell_exec] Error: Cannot find module 'better-sqlite3'. Run: npm install better-sqlite3"},
        ],
        "expected_tool": "shell_exec",
        "content_check": "better-sqlite3",
        "reject_tools": ["message_chat", "message_result"],
    },
    {
        "id": "FER03", "name": "wrong-build-command",
        "messages": [
            {"role": "system", "content": FS_SYSTEM},
            {"role": "user", "content": "Build a bookmark manager with a database"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c1", "type": "function", "function": {
                    "name": "project_init", "arguments": json.dumps({"name": "bookmark-manager", "template": "fullstack"})}}
            ]},
            {"role": "tool", "tool_call_id": "c1",
             "content": "[project_init] Created 'bookmark-manager' from fullstack scaffold. Write server/index.js then src/App.tsx."},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c2", "type": "function", "function": {
                    "name": "file_write", "arguments": json.dumps({"path": "server/index.js", "content": "// server"})}}
            ]},
            {"role": "tool", "tool_call_id": "c2", "content": "[file_write] Written."},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c3", "type": "function", "function": {
                    "name": "file_write", "arguments": json.dumps({"path": "src/App.tsx", "content": "// app"})}}
            ]},
            {"role": "tool", "tool_call_id": "c3", "content": "[file_write] Written."},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c4", "type": "function", "function": {
                    "name": "shell_exec", "arguments": json.dumps({"command": "npm run build"})}}
            ]},
            {"role": "tool", "tool_call_id": "c4",
             "content": "[shell_exec] Error: ENOENT: no such file or directory 'package.json'. Did you forget to cd into the project directory?"},
        ],
        "expected_tool": "shell_exec",
        "content_check": "deliverables/bookmark-manager",
        "reject_tools": ["message_chat", "message_result"],
    },
]

# ---------------------------------------------------------------------------
# L4 Hack-Free
# ---------------------------------------------------------------------------
FS_HACK_SCENARIOS = [
    {
        "id": "FSF01", "hack": "fullstack template param",
        "desc": "project_init must include template='fullstack'",
        "messages": [
            {"role": "system", "content": FS_SYSTEM},
            {"role": "user", "content": "Build a todo list app with SQLite persistence"},
        ],
        "expected_tool": "project_init",
        "content_checks": {"contains_any": ["fullstack"]},
        "reject_tools": ["message_chat"],
    },
    {
        "id": "FSF02", "hack": "server first",
        "desc": "After project_init, first file_write is server/index.js (not App.tsx)",
        "messages": [
            {"role": "system", "content": FS_SYSTEM},
            {"role": "user", "content": "Build a notes app backed by SQLite"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c1", "type": "function", "function": {
                    "name": "project_init", "arguments": json.dumps({"name": "notes-app", "template": "fullstack"})}}
            ]},
            {"role": "tool", "tool_call_id": "c1",
             "content": "[project_init] Created 'notes-app' from fullstack scaffold. Write server/index.js then src/App.tsx."},
        ],
        "expected_tool": "file_write",
        "content_checks": {"contains_any": ["server/index.js", "server\\index.js"]},
        "reject_tools": ["message_result", "shell_exec"],
    },
    {
        "id": "FSF03", "hack": "useApi not fetch",
        "desc": "App.tsx must use useApi hook, not raw fetch()",
        "messages": [
            {"role": "system", "content": FS_SYSTEM},
            {"role": "user", "content": "Build an expense tracker with a database"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c1", "type": "function", "function": {
                    "name": "project_init", "arguments": json.dumps({"name": "expense-tracker", "template": "fullstack"})}}
            ]},
            {"role": "tool", "tool_call_id": "c1",
             "content": "[project_init] Created 'expense-tracker' from fullstack scaffold. Write server/index.js then src/App.tsx."},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c2", "type": "function", "function": {
                    "name": "file_write", "arguments": json.dumps({"path": "server/index.js", "content": "// server"})}}
            ]},
            {"role": "tool", "tool_call_id": "c2", "content": "[file_write] Written."},
        ],
        "expected_tool": "file_write",
        "content_checks": {
            "contains_any": ["useApi"],
            "not_contains": ["fetch('/api", 'fetch("/api'],
        },
        "reject_tools": ["message_result"],
    },
    {
        "id": "FSF04", "hack": "undertow before deliver",
        "desc": "After successful build → undertow, not message_result",
        "messages": [
            {"role": "system", "content": FS_SYSTEM},
            {"role": "user", "content": "Build a contact book with SQLite"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c1", "type": "function", "function": {
                    "name": "project_init", "arguments": json.dumps({"name": "contact-book", "template": "fullstack"})}}
            ]},
            {"role": "tool", "tool_call_id": "c1",
             "content": "[project_init] Created 'contact-book'. Write server/index.js then src/App.tsx."},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c2", "type": "function", "function": {
                    "name": "file_write", "arguments": json.dumps({"path": "server/index.js", "content": "// server"})}}
            ]},
            {"role": "tool", "tool_call_id": "c2", "content": "[file_write] Written."},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c3", "type": "function", "function": {
                    "name": "file_write", "arguments": json.dumps({"path": "src/App.tsx", "content": "// app"})}}
            ]},
            {"role": "tool", "tool_call_id": "c3", "content": "[file_write] Written."},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c4", "type": "function", "function": {
                    "name": "shell_exec", "arguments": json.dumps({"command": "cd deliverables/contact-book && npm run build"})}}
            ]},
            {"role": "tool", "tool_call_id": "c4", "content": "[shell_exec] Build succeeded. dist/ ready."},
        ],
        "expected_tool": "undertow",
        "reject_tools": ["message_result"],
    },
    {
        "id": "FSF05", "hack": "no main.tsx overwrite",
        "desc": "After project_init, should NOT overwrite main.tsx",
        "messages": [
            {"role": "system", "content": FS_SYSTEM},
            {"role": "user", "content": "Build a todo app backed by SQLite"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c1", "type": "function", "function": {
                    "name": "project_init", "arguments": json.dumps({"name": "todo-app", "template": "fullstack"})}}
            ]},
            {"role": "tool", "tool_call_id": "c1",
             "content": "[project_init] Created 'todo-app' from fullstack scaffold. Write server/index.js then src/App.tsx."},
        ],
        "expected_tool": "file_write",
        "content_checks": {
            "not_contains": ["main.tsx", "vite.config.ts", "index.css"],
        },
        "reject_tools": ["message_result"],
    },
    {
        "id": "FSF06", "hack": "crudRoutes in server",
        "desc": "server/index.js should use crudRoutes() pattern, not manual route handlers",
        "messages": [
            {"role": "system", "content": FS_SYSTEM},
            {"role": "user", "content": "Build a bookmark manager with SQLite backend"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c1", "type": "function", "function": {
                    "name": "project_init", "arguments": json.dumps({"name": "bookmarks", "template": "fullstack"})}}
            ]},
            {"role": "tool", "tool_call_id": "c1",
             "content": "[project_init] Created 'bookmarks' from fullstack scaffold. Write server/index.js then src/App.tsx."},
        ],
        "expected_tool": "file_write",
        "content_checks": {
            "contains_any": ["crudRoutes", "better-sqlite3", "Database("],
        },
        "reject_tools": ["message_result", "shell_exec"],
    },
]


# ---------------------------------------------------------------------------
# Helpers (shared pattern with eval_dataviz / eval_chrome_ext)
# ---------------------------------------------------------------------------

async def _call(client, endpoint, adapter, messages, timeout=300.0):
    payload = {
        "model": "tsunami",
        "messages": messages,
        "tools": FS_TOOLS,
        "max_tokens": 512,
        "temperature": 0.0,
    }
    if adapter and adapter != "none":
        payload["adapter"] = adapter
    r = await client.post(f"{endpoint}/v1/chat/completions", json=payload, timeout=timeout)
    r.raise_for_status()
    return r.json()


def _get_tool_name(resp):
    choices = resp.get("choices", [])
    if not choices:
        return None
    msg = choices[0].get("message", {})
    tc = msg.get("tool_calls", [])
    if tc:
        return tc[0].get("function", {}).get("name")
    m = re.search(r'"name"\s*:\s*"(\w+)"', msg.get("content", ""))
    return m.group(1) if m else None


def _get_tool_args(resp):
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
    for p in FS_FORMAT_PROMPTS:
        msgs = [{"role": "system", "content": FS_SYSTEM}, {"role": "user", "content": p["prompt"]}]
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
    """Check: project_init with template=fullstack, then server/index.js next."""
    passed, total = 0, 0
    for p in FS_SCAFFOLD_PROMPTS:
        msgs = [{"role": "system", "content": FS_SYSTEM}, {"role": "user", "content": p["prompt"]}]
        try:
            resp1 = await _call(client, endpoint, adapter, msgs)
            tool1 = _get_tool_name(resp1)
            args1 = _get_tool_args(resp1)
            ok1 = tool1 == "project_init" and "fullstack" in json.dumps(args1)

            if ok1:
                name = args1.get("name", "app")
                init_result = f"[project_init] Created '{name}' from fullstack scaffold. Write server/index.js then src/App.tsx."
                msgs2 = msgs + [
                    {"role": "assistant", "content": "", "tool_calls": [
                        {"id": "l2c1", "type": "function", "function": {
                            "name": "project_init", "arguments": json.dumps(args1)}}
                    ]},
                    {"role": "tool", "tool_call_id": "l2c1", "content": init_result},
                ]
                resp2 = await _call(client, endpoint, adapter, msgs2)
                tool2 = _get_tool_name(resp2)
                args2 = _get_tool_args(resp2)
                ok2 = tool2 == "file_write" and "server" in args2.get("path", "").lower()
                ok = ok1 and ok2
                log.info(f"  L2 {p['id']}: {'PASS' if ok else 'FAIL'} — t1={tool1!r}(fs={ok1}) t2={tool2!r}(server={ok2})")
            else:
                ok = False
                log.info(f"  L2 {p['id']}: FAIL — t1={tool1!r} (no fullstack template)")
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
    for s in FS_ERROR_SCENARIOS:
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
    for s in FS_HACK_SCENARIOS:
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
    ap.add_argument("--adapter", default="fullstack-v1")
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()

    log.info(f"eval_fullstack — endpoint={args.endpoint} adapter={args.adapter} quick={args.quick}")

    async with httpx.AsyncClient() as client:
        l1p, l1t = await run_l1(client, args.endpoint, args.adapter, args.quick)
        l2p, l2t = await run_l2(client, args.endpoint, args.adapter, args.quick)
        l3p, l3t = await run_l3(client, args.endpoint, args.adapter, args.quick)
        l4p, l4t = await run_l4(client, args.endpoint, args.adapter, args.quick)

    total_p = l1p + l2p + l3p + l4p
    total_t = l1t + l2t + l3t + l4t
    print(f"\n=== FULLSTACK EVAL RESULTS ===")
    print(f"  L1 Format:          {l1p}/{l1t}")
    print(f"  L2 Scaffold:        {l2p}/{l2t}")
    print(f"  L3 Error Recovery:  {l3p}/{l3t}")
    print(f"  L4 Hack-Free:       {l4p}/{l4t}")
    print(f"  TOTAL:              {total_p}/{total_t}  ({total_p/max(total_t,1)*100:.1f}%)")

    out = {
        "adapter": args.adapter, "endpoint": args.endpoint, "quick": args.quick,
        "l1": f"{l1p}/{l1t}", "l2": f"{l2p}/{l2t}",
        "l3": f"{l3p}/{l3t}", "l4": f"{l4p}/{l4t}",
        "total": f"{total_p}/{total_t}",
        "pct": round(total_p / max(total_t, 1), 3),
    }
    out_path = Path("workspace/eval_results") / f"fullstack_{args.adapter}_{int(time.time())}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2))
    log.info(f"Results saved: {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
