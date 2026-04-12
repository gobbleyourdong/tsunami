#!/usr/bin/env python3
"""Chrome Extension adapter eval — L1-L4 quick.

Tests the gemma-4-e4b chrome-ext-v1 adapter against a rubric mirroring
eval_gamedev.py but targeting extension-specific patterns:
  - 3-file writes (popup + background + content)
  - chrome.* API usage (not fetch to external URLs)
  - No undertow (extensions can't be headless-tested)
  - Build errors → file_edit not message_chat

Usage:
  python training/eval_chrome_ext.py --endpoint http://localhost:8090 --adapter chrome-ext-v1 --quick
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
log = logging.getLogger("eval_chrome_ext")

EXT_SYSTEM = """You are Tsunami. You are the wave. You build Chrome extensions by calling tools.

## Chrome Extension Pipeline (every build follows this EXACTLY)

1. project_init(name) -- create the extension project
2. file_write(src/popup/App.tsx) -- the popup UI (React component)
3. file_write(src/background/service-worker.ts) -- background service worker
4. file_write(src/content/content.ts) -- content script (page interaction)
5. shell_exec("cd deliverables/{name} && npm run build") -- build
6. IF build error: fix directly with file_edit
7. message_result -- deliver (no undertow -- extensions can't be headless-tested)

## Chrome Extension API

Tabs: chrome.tabs.query({active:true,currentWindow:true}, tabs => {...})
Storage: chrome.storage.local.get/set, chrome.storage.sync.get/set
Messaging: chrome.runtime.sendMessage(msg) / chrome.runtime.onMessage.addListener
Alarms: chrome.alarms.create({delayInMinutes:N}) / chrome.alarms.onAlarm.addListener
Notifications: chrome.notifications.create(id, {type:'basic', iconUrl, title, message})

## Rules
- NEVER skip the build step.
- Write ALL THREE files (popup + background + content) before building.
- No undertow -- extensions load in Chrome, not HTTP servers.
- One tool call per response. Be brief.
"""

EXT_TOOLS = [
    {"type": "function", "function": {
        "name": "project_init",
        "description": "Create a Chrome extension project from the scaffold library.",
        "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
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

# L1 Format
EXT_FORMAT_PROMPTS = [
    {"id": "CT01", "prompt": "Build a Chrome extension that shows how many tabs I have open",
     "expected": "project_init"},
    {"id": "CT02", "prompt": "Build a browser extension for blocking distracting websites",
     "expected": "project_init"},
    {"id": "CT03", "prompt": "Build a Chrome extension with a popup",
     "expected": "project_init"},
    {"id": "CT04", "prompt": "Hello, what extensions can you build?",
     "expected": "message_chat"},
    {"id": "CT05", "prompt": "Build a dark mode toggle for Chrome",
     "expected": "project_init"},
]

# L2 Scaffold — model should scaffold with project_init, name should be reasonable
EXT_SCAFFOLD_PROMPTS = [
    {"id": "CS01", "prompt": "Build a Chrome extension that counts words on any webpage"},
    {"id": "CS02", "prompt": "Build a Pomodoro timer Chrome extension"},
    {"id": "CS03", "prompt": "Build a browser extension that saves pages to read later"},
]

# L3 Error Recovery
EXT_ERROR_SCENARIOS = [
    {
        "id": "CER01", "name": "ts-type-error",
        "messages": [
            {"role": "system", "content": EXT_SYSTEM},
            {"role": "user", "content": "Build a tab counter extension"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c1", "type": "function", "function": {
                    "name": "project_init", "arguments": json.dumps({"name": "tab-counter"})}}
            ]},
            {"role": "tool", "tool_call_id": "c1",
             "content": "[project_init] Created extension 'tab-counter'. Write popup/App.tsx, background/service-worker.ts, content/content.ts."},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c2", "type": "function", "function": {
                    "name": "file_write", "arguments": json.dumps({"path": "src/popup/App.tsx", "content": "// popup"})}}
            ]},
            {"role": "tool", "tool_call_id": "c2", "content": "[file_write] Written."},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c3", "type": "function", "function": {
                    "name": "file_write", "arguments": json.dumps({"path": "src/background/service-worker.ts", "content": "// bg"})}}
            ]},
            {"role": "tool", "tool_call_id": "c3", "content": "[file_write] Written."},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c4", "type": "function", "function": {
                    "name": "file_write", "arguments": json.dumps({"path": "src/content/content.ts", "content": "export {}"})}}
            ]},
            {"role": "tool", "tool_call_id": "c4", "content": "[file_write] Written."},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c5", "type": "function", "function": {
                    "name": "shell_exec", "arguments": json.dumps({"command": "cd deliverables/tab-counter && npm run build"})}}
            ]},
            {"role": "tool", "tool_call_id": "c5",
             "content": "[shell_exec] Error: src/popup/App.tsx(5,12): error TS2345: Argument of type 'number' is not assignable to parameter of type 'string'."},
        ],
        "expected_tool": "file_edit",
        "reject_tools": ["message_chat", "project_init", "message_result"],
    },
    {
        "id": "CER02", "name": "missing-chrome-types",
        "messages": [
            {"role": "system", "content": EXT_SYSTEM},
            {"role": "user", "content": "Build a site blocker extension"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c1", "type": "function", "function": {
                    "name": "project_init", "arguments": json.dumps({"name": "site-blocker"})}}
            ]},
            {"role": "tool", "tool_call_id": "c1",
             "content": "[project_init] Created extension 'site-blocker'. Write popup/App.tsx, background/service-worker.ts, content/content.ts."},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c2", "type": "function", "function": {
                    "name": "file_write", "arguments": json.dumps({"path": "src/popup/App.tsx", "content": "// popup"})}}
            ]},
            {"role": "tool", "tool_call_id": "c2", "content": "[file_write] Written."},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c3", "type": "function", "function": {
                    "name": "file_write", "arguments": json.dumps({"path": "src/background/service-worker.ts", "content": "// bg"})}}
            ]},
            {"role": "tool", "tool_call_id": "c3", "content": "[file_write] Written."},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c4", "type": "function", "function": {
                    "name": "file_write", "arguments": json.dumps({"path": "src/content/content.ts", "content": "export {}"})}}
            ]},
            {"role": "tool", "tool_call_id": "c4", "content": "[file_write] Written."},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c5", "type": "function", "function": {
                    "name": "shell_exec", "arguments": json.dumps({"command": "cd deliverables/site-blocker && npm run build"})}}
            ]},
            {"role": "tool", "tool_call_id": "c5",
             "content": "[shell_exec] Error: src/background/service-worker.ts(1,1): error TS2304: Cannot find name 'chrome'. Are you missing a type definition file?"},
        ],
        "expected_tool": "shell_exec",   # npm install @types/chrome
        "content_check": "chrome",       # command should reference chrome types
        "reject_tools": ["message_chat", "message_result"],
    },
]

# L4 Hack-Free
EXT_HACK_SCENARIOS = [
    {
        "id": "CEF01", "hack": "Popup file path",
        "desc": "After project_init for extension, first file_write uses popup/ path",
        "messages": [
            {"role": "system", "content": EXT_SYSTEM},
            {"role": "user", "content": "Build a Chrome extension tab counter"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c1", "type": "function", "function": {
                    "name": "project_init", "arguments": json.dumps({"name": "tab-counter"})}}
            ]},
            {"role": "tool", "tool_call_id": "c1",
             "content": "[project_init] Created extension 'tab-counter'. Write popup/App.tsx, background/service-worker.ts, content/content.ts."},
        ],
        "expected_tool": "file_write",
        "content_checks": {"contains_any": ["popup/App.tsx", "src/popup", "popup"]},
        "reject_tools": ["message_result", "shell_exec"],
    },
    {
        "id": "CEF02", "hack": "Chrome API usage",
        "desc": "Popup code should use chrome.tabs (not raw fetch or XHR)",
        "messages": [
            {"role": "system", "content": EXT_SYSTEM},
            {"role": "user", "content": "Build a Chrome extension that shows tab count"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c1", "type": "function", "function": {
                    "name": "project_init", "arguments": json.dumps({"name": "tab-counter"})}}
            ]},
            {"role": "tool", "tool_call_id": "c1",
             "content": "[project_init] Created extension 'tab-counter'. Write popup/App.tsx, background/service-worker.ts, content/content.ts."},
        ],
        "expected_tool": "file_write",
        "content_checks": {
            "contains_any": ["chrome.tabs", "chrome.storage", "chrome.runtime"],
            "not_contains": ["fetch('http", "XMLHttpRequest"],
        },
        "reject_tools": ["message_result"],
    },
    {
        "id": "CEF03", "hack": "No undertow",
        "desc": "After successful build, should NOT call undertow — deliver directly",
        "messages": [
            {"role": "system", "content": EXT_SYSTEM},
            {"role": "user", "content": "Build a tab counter extension"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c1", "type": "function", "function": {
                    "name": "project_init", "arguments": json.dumps({"name": "tab-counter"})}}
            ]},
            {"role": "tool", "tool_call_id": "c1",
             "content": "[project_init] Created extension 'tab-counter'. Write popup/App.tsx, background/service-worker.ts, content/content.ts."},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c2", "type": "function", "function": {
                    "name": "file_write", "arguments": json.dumps({"path": "src/popup/App.tsx", "content": "// popup"})}}
            ]},
            {"role": "tool", "tool_call_id": "c2", "content": "[file_write] Written."},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c3", "type": "function", "function": {
                    "name": "file_write", "arguments": json.dumps({"path": "src/background/service-worker.ts", "content": "// bg"})}}
            ]},
            {"role": "tool", "tool_call_id": "c3", "content": "[file_write] Written."},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c4", "type": "function", "function": {
                    "name": "file_write", "arguments": json.dumps({"path": "src/content/content.ts", "content": "export {}"})}}
            ]},
            {"role": "tool", "tool_call_id": "c4", "content": "[file_write] Written."},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c5", "type": "function", "function": {
                    "name": "shell_exec", "arguments": json.dumps({"command": "cd deliverables/tab-counter && npm run build"})}}
            ]},
            {"role": "tool", "tool_call_id": "c5",
             "content": "[shell_exec] Build successful. dist/ ready for Chrome loading."},
        ],
        "expected_tool": "message_result",
        "reject_tools": ["undertow"],
    },
    {
        "id": "CEF04", "hack": "Build error → file_edit not message_chat",
        "desc": "After build TS error, must fix with file_edit",
        "messages": [
            {"role": "system", "content": EXT_SYSTEM},
            {"role": "user", "content": "Build a quick notes extension"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c1", "type": "function", "function": {
                    "name": "project_init", "arguments": json.dumps({"name": "quick-notes"})}}
            ]},
            {"role": "tool", "tool_call_id": "c1",
             "content": "[project_init] Created extension 'quick-notes'."},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c2", "type": "function", "function": {
                    "name": "file_write", "arguments": json.dumps({"path": "src/popup/App.tsx", "content": "// popup"})}}
            ]},
            {"role": "tool", "tool_call_id": "c2", "content": "[file_write] Written."},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c3", "type": "function", "function": {
                    "name": "file_write", "arguments": json.dumps({"path": "src/background/service-worker.ts", "content": "// bg"})}}
            ]},
            {"role": "tool", "tool_call_id": "c3", "content": "[file_write] Written."},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c4", "type": "function", "function": {
                    "name": "file_write", "arguments": json.dumps({"path": "src/content/content.ts", "content": "export {}"})}}
            ]},
            {"role": "tool", "tool_call_id": "c4", "content": "[file_write] Written."},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c5", "type": "function", "function": {
                    "name": "shell_exec", "arguments": json.dumps({"command": "cd deliverables/quick-notes && npm run build"})}}
            ]},
            {"role": "tool", "tool_call_id": "c5",
             "content": "[shell_exec] Error: src/popup/App.tsx(3,8): error TS2304: Cannot find name 'useState'."},
        ],
        "expected_tool": "file_edit",
        "reject_tools": ["message_chat", "message_result"],
    },
    {
        "id": "CEF05", "hack": "Background file path",
        "desc": "Second file_write after popup should write background/service-worker.ts",
        "messages": [
            {"role": "system", "content": EXT_SYSTEM},
            {"role": "user", "content": "Build a Chrome extension that shows tab count"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c1", "type": "function", "function": {
                    "name": "project_init", "arguments": json.dumps({"name": "tab-counter"})}}
            ]},
            {"role": "tool", "tool_call_id": "c1",
             "content": "[project_init] Created extension 'tab-counter'. Write popup/App.tsx, background/service-worker.ts, content/content.ts."},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c2", "type": "function", "function": {
                    "name": "file_write", "arguments": json.dumps({"path": "src/popup/App.tsx", "content": "// popup"})}}
            ]},
            {"role": "tool", "tool_call_id": "c2", "content": "[file_write] Written."},
        ],
        "expected_tool": "file_write",
        "content_checks": {"contains_any": ["background", "service-worker"]},
        "reject_tools": ["message_result", "shell_exec"],
    },
]

# ---------------------------------------------------------------------------
async def chat(client, endpoint, messages, tools, adapter, timeout=90.0):
    payload = {"model": "tsunami", "messages": messages, "tools": tools,
               "max_tokens": 512, "temperature": 0}
    if adapter:
        payload["adapter"] = adapter
    t0 = time.monotonic()
    try:
        r = await client.post(f"{endpoint}/v1/chat/completions", json=payload, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        data["_latency_ms"] = int((time.monotonic() - t0) * 1000)
        return data
    except Exception as e:
        return {"error": str(e), "_latency_ms": int((time.monotonic() - t0) * 1000)}


def extract_tool(response):
    if "error" in response:
        return "", {}, response["error"]
    try:
        msg = response["choices"][0]["message"]
        tc = msg.get("tool_calls")
        if tc and len(tc) > 0:
            fn = tc[0].get("function", {})
            name = fn.get("name", "")
            args = fn.get("arguments", {})
            if isinstance(args, str):
                try: args = json.loads(args)
                except: pass
            return name, args, ""
        content = msg.get("content", "") or ""
        m = re.search(r"<\|tool_call>call:(\w+)\{", content)
        if m: return m.group(1), {}, ""
        return "", {}, "no tool call in response"
    except Exception as e:
        return "", {}, str(e)


async def run_l1(client, endpoint, adapter):
    log.info("--- L1: FORMAT ---")
    results = []
    for p in EXT_FORMAT_PROMPTS:
        msgs = [{"role": "system", "content": EXT_SYSTEM}, {"role": "user", "content": p["prompt"]}]
        resp = await chat(client, endpoint, msgs, EXT_TOOLS, adapter)
        tool, _, err = extract_tool(resp)
        passed = tool == p["expected"]
        results.append({"id": p["id"], "prompt": p["prompt"], "expected": p["expected"],
                        "tool": tool or "NONE", "pass": passed, "latency_ms": resp.get("_latency_ms", 0)})
        log.info(f"  {p['id']} [{'PASS' if passed else 'FAIL'}] {p['prompt'][:45]} -> {tool or 'NONE'}")
    return results


async def run_l2(client, endpoint, adapter):
    log.info("--- L2: SCAFFOLD ---")
    results = []
    for p in EXT_SCAFFOLD_PROMPTS:
        msgs = [{"role": "system", "content": EXT_SYSTEM}, {"role": "user", "content": p["prompt"]}]
        resp = await chat(client, endpoint, msgs, EXT_TOOLS, adapter)
        tool, args, err = extract_tool(resp)
        passed = tool == "project_init"
        results.append({"id": p["id"], "prompt": p["prompt"], "status": "PASS" if passed else "FAIL",
                        "got_tool": tool or "NONE", "project_name": args.get("name", "") if isinstance(args, dict) else "",
                        "latency_ms": resp.get("_latency_ms", 0)})
        log.info(f"  {p['id']} [{'PASS' if passed else 'FAIL'}] {p['prompt'][:45]} -> {tool or 'NONE'}")
    return results


async def run_l3(client, endpoint, adapter):
    log.info("--- L3: ERROR RECOVERY ---")
    results = []
    for sc in EXT_ERROR_SCENARIOS:
        resp = await chat(client, endpoint, sc["messages"], EXT_TOOLS, adapter, timeout=120)
        tool, args, err = extract_tool(resp)
        passed = tool == sc["expected_tool"]
        bad = tool in sc.get("reject_tools", [])
        results.append({"id": sc["id"], "name": sc["name"], "expected_tool": sc["expected_tool"],
                        "actual_tool": tool or "NONE", "status": "PASS" if passed else "FAIL",
                        "bad_retry": bad, "latency_ms": resp.get("_latency_ms", 0)})
        log.info(f"  {sc['id']} [{'PASS' if passed else 'FAIL'}] {sc['name']} -> {tool or 'NONE'}")
    return results


async def run_l4(client, endpoint, adapter):
    log.info("--- L4: HACK-FREE ---")
    results = []
    for sc in EXT_HACK_SCENARIOS:
        resp = await chat(client, endpoint, sc["messages"], EXT_TOOLS, adapter, timeout=120)
        tool, args, err = extract_tool(resp)
        passed = tool == sc["expected_tool"]
        content_fail = ""
        if passed and "content_checks" in sc:
            content = args.get("content", "") if isinstance(args, dict) else ""
            for req in sc["content_checks"].get("contains", []):
                if req not in content: content_fail = f"missing '{req}'"; passed = False; break
            if passed:
                opts = sc["content_checks"].get("contains_any", [])
                if opts and not any(o in content for o in opts):
                    content_fail = f"missing all of {opts!r}"; passed = False
            if passed:
                for forb in sc["content_checks"].get("not_contains", []):
                    if forb in content: content_fail = f"forbidden '{forb}'"; passed = False; break
        actual = (tool or "NONE") + (f"(fail:{content_fail})" if content_fail else "")
        results.append({"id": sc["id"], "hack": sc["hack"], "desc": sc["desc"],
                        "expected": sc["expected_tool"], "actual": actual,
                        "status": "PASS" if passed else "FAIL",
                        "reason": content_fail or (err if not passed else ""),
                        "latency_ms": resp.get("_latency_ms", 0)})
        log.info(f"  {sc['id']} [{'PASS' if passed else 'FAIL'}] {sc['hack']} -> {actual}")
    return results


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", default="http://localhost:8090")
    parser.add_argument("--adapter", default="chrome-ext-v1")
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    t0 = time.monotonic()
    async with httpx.AsyncClient() as client:
        l1 = await run_l1(client, args.endpoint, args.adapter)
        l2 = await run_l2(client, args.endpoint, args.adapter)
        l3 = await run_l3(client, args.endpoint, args.adapter)
        l4 = await run_l4(client, args.endpoint, args.adapter)

    elapsed = int(time.monotonic() - t0)

    p1 = sum(1 for x in l1 if x["pass"])
    p2 = sum(1 for x in l2 if x["status"] == "PASS")
    p3 = sum(1 for x in l3 if x["status"] == "PASS")
    p4 = sum(1 for x in l4 if x["status"] == "PASS")
    pts = p1*5 + p2*2 + p3*15 + p4*10
    max_pts = len(l1)*5 + len(l2)*2 + len(l3)*15 + len(l4)*10
    pct = pts / max_pts if max_pts else 0

    print(f"\n{'='*60}")
    print(f"Chrome Extension Eval | adapter={args.adapter} | {elapsed}s")
    print(f"{'='*60}")
    print(f"L1 Format:   {p1}/{len(l1)}")
    print(f"L2 Scaffold: {p2}/{len(l2)}")
    print(f"L3 Recovery: {p3}/{len(l3)}")
    print(f"L4 Hack-Free:{p4}/{len(l4)}")
    print(f"TOTAL:       {pts}/{max_pts} ({pct:.0%})")

    out_path = args.out or f"workspace/training_data/eval_report_chrome_ext_{time.strftime('%Y-%m-%d_%H%M%S')}.json"
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump({"l1": l1, "l2": l2, "l3": l3, "l4": l4,
                   "score": {"pts": pts, "max": max_pts, "pct": pct},
                   "adapter": args.adapter, "elapsed": elapsed}, f, indent=2)
    log.info(f"Report: {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
