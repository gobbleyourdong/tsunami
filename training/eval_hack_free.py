#!/usr/bin/env python3
"""Hack-free eval — tests model behavior for every scenario the agent loop
currently compensates for with hacks.

Each test presents a scenario where the old model needed a hack (nudge,
forced action, loop detection). The trained model should handle it natively.

Usage:
  python training/eval_hack_free.py --endpoint http://localhost:8095
"""

import argparse
import asyncio
import json
import logging
import time

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("eval_hack_free")

TOOL_SCHEMAS = [
    {"type": "function", "function": {"name": "file_read", "description": "Read a file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "file_write", "description": "Write a file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "file_edit", "description": "Edit a file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]}}},
    {"type": "function", "function": {"name": "shell_exec", "description": "Run a shell command.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
    {"type": "function", "function": {"name": "project_init", "description": "Scaffold a project.", "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "dependencies": {"type": "array", "items": {"type": "string"}}}, "required": ["name"]}}},
    {"type": "function", "function": {"name": "search_web", "description": "Search the web.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "plan_update", "description": "Create a plan.", "parameters": {"type": "object", "properties": {"goal": {"type": "string"}, "phases": {"type": "array"}}, "required": ["goal", "phases"]}}},
    {"type": "function", "function": {"name": "swell", "description": "Dispatch parallel eddies.", "parameters": {"type": "object", "properties": {"tasks": {"type": "array"}}, "required": ["tasks"]}}},
    {"type": "function", "function": {"name": "undertow", "description": "QA test an HTML file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "expect": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "message_chat", "description": "Talk to user. done=true ends, done=false continues.", "parameters": {"type": "object", "properties": {"text": {"type": "string"}, "done": {"type": "boolean"}}, "required": ["text"]}}},
    {"type": "function", "function": {"name": "message_result", "description": "Deliver final result.", "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": []}}},
    {"type": "function", "function": {"name": "generate_image", "description": "Generate an image.", "parameters": {"type": "object", "properties": {"prompt": {"type": "string"}, "save_path": {"type": "string"}}, "required": ["prompt", "save_path"]}}},
    {"type": "function", "function": {"name": "match_glob", "description": "Find files by pattern.", "parameters": {"type": "object", "properties": {"pattern": {"type": "string"}}, "required": ["pattern"]}}},
]

SYSTEM = (
    "You are Tsunami. You are the wave. You build apps by calling tools.\n\n"
    "The ocean:\n"
    "- current: your sense of direction. If uncertain, search first.\n"
    "- circulation: routing. Low tension=deliver. High tension=search or refuse.\n"
    "- pressure: sustained uncertainty. 2 failures=search. 4 failures=ask the user.\n"
    "- eddies: parallel workers. 3+ components=dispatch swell.\n"
    "- undertow: QA. ALWAYS verify before delivering.\n"
    "- break: compile. shell_exec build after EVERY file_write.\n"
    "- reef: error. Fix directly. Type/syntax -> file_edit. Missing module -> shell_exec npm install. Missing file -> file_write. Wrong path (cd fails) -> shell_exec with corrected path (NEVER message_chat). CSS resolution errors -> file_edit to remove/replace the import (don't file_read first).\n\n"
    "BEFORE THE PIPELINE:\n"
    "- Visual clones (\"looks like X\", \"style of Y\") -> search_web FIRST for reference\n"
    "- User explicitly asks for a plan (\"plan needed\", \"plan carefully\") -> plan_update FIRST\n"
    "- Default: go straight to project_init\n\n"
    "THE PIPELINE (every build follows this EXACTLY):\n"
    "1. project_init(name)\n"
    "2. file_write(App.tsx) -- write COMPLETE code\n"
    "3. shell_exec -- run the break\n"
    "4. IF ERROR: fix directly -- file_edit (type/syntax fix), file_write (missing file), or shell_exec (install module, corrected path)\n"
    "5. undertow -- QA before delivery\n"
    "6. message_result -- land the wave\n\n"
    "NEVER skip the break. NEVER deliver without building. One tool call per response. Be brief."
)

HACK_SCENARIOS = [
    # === HACK: Auto-scaffold (model should scaffold on its own) ===
    {
        "id": "HF01",
        "hack": "Auto-scaffold",
        "desc": "Model should call project_init as first action on build task",
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": "Build a calculator app"},
        ],
        "expect_tool": "project_init",
        "reject_tools": ["file_read", "match_glob", "search_web"],  # should NOT research first for simple build
    },
    # === HACK: Research gate (model should search before visual builds) ===
    {
        "id": "HF02",
        "hack": "Research gate",
        "desc": "Model should search before building a visual clone",
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": "Build a page that looks like the Stripe pricing page"},
        ],
        "expect_tool": "search_web",
        "reject_tools": ["project_init", "file_write"],  # should NOT build before researching
    },
    # === HACK: Stall detection (model should not loop on reads) ===
    {
        "id": "HF03",
        "hack": "Stall detection",
        "desc": "After reading files, model should start writing, not keep reading",
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": "Build a todo app"},
            {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "project_init", "arguments": json.dumps({"name": "todo"})}}]},
            {"role": "tool", "tool_call_id": "c1", "content": "[project_init] Created project 'todo' with react-app scaffold. Write in src/."},
            {"role": "assistant", "content": "", "tool_calls": [{"id": "c2", "type": "function", "function": {"name": "file_read", "arguments": json.dumps({"path": "deliverables/todo/src/App.tsx"})}}]},
            {"role": "tool", "tool_call_id": "c2", "content": "[file_read] Stub App.tsx: export default function App() { return <div>App</div> }"},
            {"role": "assistant", "content": "", "tool_calls": [{"id": "c3", "type": "function", "function": {"name": "file_read", "arguments": json.dumps({"path": "deliverables/todo/package.json"})}}]},
            {"role": "tool", "tool_call_id": "c3", "content": "[file_read] package.json with react, vite dependencies"},
        ],
        "expect_tool": "file_write",
        "reject_tools": ["file_read", "match_glob"],  # should STOP reading and START writing
    },
    # === HACK: Code-write gate (model should write code, not deliver scaffold) ===
    {
        "id": "HF04",
        "hack": "Code-write gate",
        "desc": "After scaffolding, model should write code, not deliver empty scaffold",
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": "Build a color picker"},
            {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "project_init", "arguments": json.dumps({"name": "color-picker"})}}]},
            {"role": "tool", "tool_call_id": "c1", "content": "[project_init] Created project 'color-picker'. Write in src/."},
        ],
        "expect_tool": "file_write",
        "reject_tools": ["message_result", "message_chat"],  # should NOT deliver empty scaffold
    },
    # === HACK: Shell loop (model should fix code, not retry build) ===
    {
        "id": "HF05",
        "hack": "Shell loop detection",
        "desc": "After 2 build failures, model should read+fix, not retry build",
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": "The build keeps failing. Fix it."},
            {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "shell_exec", "arguments": json.dumps({"command": "cd deliverables/app && npx vite build"})}}]},
            {"role": "tool", "tool_call_id": "c1", "content": "[shell_exec] Error: Cannot find module './components/Header'"},
            {"role": "assistant", "content": "", "tool_calls": [{"id": "c2", "type": "function", "function": {"name": "shell_exec", "arguments": json.dumps({"command": "cd deliverables/app && npx vite build"})}}]},
            {"role": "tool", "tool_call_id": "c2", "content": "[shell_exec] Error: Cannot find module './components/Header'"},
        ],
        "expect_tool": "file_write",  # should write the missing component
        "reject_tools": ["shell_exec"],  # should NOT retry build again
    },
    # === HACK: message_info loop (model should use message_chat) ===
    {
        "id": "HF06",
        "hack": "Info loop detection",
        "desc": "For conversation, model should use message_chat(done=true), not message_info",
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": "Hello! What can you build?"},
        ],
        "expect_tool": "message_chat",
        "reject_tools": ["message_info"],
    },
    # === HACK: Auto-wire (model should write proper App.tsx imports) ===
    {
        "id": "HF07",
        "hack": "Auto-wire",
        "desc": "Model should write App.tsx with proper component imports",
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": "Build a dashboard with sidebar, chart, and data table"},
            {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "project_init", "arguments": json.dumps({"name": "dashboard"})}}]},
            {"role": "tool", "tool_call_id": "c1", "content": "[project_init] Created project 'dashboard' with dashboard scaffold. Pre-built: Layout, Sidebar, StatCard, DataTable."},
        ],
        "expect_tool": "file_write",
        "expect_in_args": "import",  # App.tsx should have imports
        "reject_tools": ["message_result"],
    },
    # === HACK: Duplicate search guard (model should not repeat same search) ===
    {
        "id": "HF08",
        "hack": "Dedup guard",
        "desc": "After getting search results, model should use them, not search again",
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": "Research React state management and build a demo"},
            {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "search_web", "arguments": json.dumps({"query": "react state management 2026"})}}]},
            {"role": "tool", "tool_call_id": "c1", "content": "[search_web] Results: 1. Zustand (lightweight), 2. Jotai (atomic), 3. Redux Toolkit (full-featured)"},
        ],
        "expect_tool": "project_init",  # should start building with what it found
        "reject_tools": ["search_web"],  # should NOT search the same thing again
    },
    # === HACK: Complex build needs plan (model should plan 3+ component builds) ===
    {
        "id": "HF09",
        "hack": "No plan for complex builds",
        "desc": "Complex multi-component build should start with plan_update or swell",
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": "Build a full e-commerce store with product grid, shopping cart, checkout form, user auth, and order history"},
        ],
        "expect_tool": "plan_update",  # complex build should be planned
        "reject_tools": ["file_write"],  # should NOT jump straight to writing
    },
    # === HACK: Undertow before delivery (model should QA before delivering) ===
    {
        "id": "HF10",
        "hack": "Missing QA",
        "desc": "After successful build, model should run undertow before delivering",
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": "Build a timer app"},
            {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "project_init", "arguments": json.dumps({"name": "timer"})}}]},
            {"role": "tool", "tool_call_id": "c1", "content": "[project_init] Created project 'timer'"},
            {"role": "assistant", "content": "", "tool_calls": [{"id": "c2", "type": "function", "function": {"name": "file_write", "arguments": json.dumps({"path": "deliverables/timer/src/App.tsx", "content": "import React from 'react';\nexport default function App() { return <div>Timer</div>; }"})}}]},
            {"role": "tool", "tool_call_id": "c2", "content": "[file_write] Wrote App.tsx"},
            {"role": "assistant", "content": "", "tool_calls": [{"id": "c3", "type": "function", "function": {"name": "shell_exec", "arguments": json.dumps({"command": "cd deliverables/timer && npx vite build"})}}]},
            {"role": "tool", "tool_call_id": "c3", "content": "[shell_exec] ✓ built in 420ms"},
        ],
        "expect_tool": "undertow",
        "reject_tools": ["message_result"],  # should NOT deliver without QA
    },
]


async def call_model(endpoint, messages, tools):
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{endpoint}/v1/chat/completions",
            json={
                "model": "eval", "messages": messages, "tools": tools,
                "tool_choice": "auto", "temperature": 0.3, "max_tokens": 2048,
            },
        )
        resp.raise_for_status()
        return resp.json()


async def eval_hack_free(endpoint):
    results = []

    for scenario in HACK_SCENARIOS:
        name, args = None, {}
        try:
            response = await call_model(endpoint, scenario["messages"], TOOL_SCHEMAS)
            choice = response["choices"][0]["message"]
            if choice.get("tool_calls"):
                tc = choice["tool_calls"][0]
                name = tc["function"]["name"]
                a = tc["function"].get("arguments", "{}")
                args = json.loads(a) if isinstance(a, str) else a
            elif choice.get("content"):
                # Fallback: 31B sometimes puts tool calls in content instead of tool_calls
                content = choice["content"].strip()
                # Strategy 1: JSON with "name" field (most robust)
                idx = content.find('"name"')
                if idx != -1:
                    start = content.rfind('{', 0, idx)
                    if start != -1:
                        for end in range(start + 10, len(content) + 1):
                            if content[end - 1] != '}':
                                continue
                            try:
                                obj = json.loads(content[start:end])
                                if isinstance(obj, dict) and "name" in obj:
                                    name = obj["name"]
                                    a = obj.get("arguments", {})
                                    args = json.loads(a) if isinstance(a, str) else (a if isinstance(a, dict) else {})
                                    break
                            except (json.JSONDecodeError, TypeError):
                                continue
                # Strategy 2: response:tool_name{...} prefix format
                if name is None:
                    import re as _re
                    m = _re.match(r"(?:response:|call:)?(\w+)\{", content)
                    if m:
                        name = m.group(1)
                        # Try to parse the {...} as JSON for args
                        brace_start = content.find('{')
                        if brace_start != -1:
                            for end in range(brace_start + 2, len(content) + 1):
                                if content[end - 1] != '}':
                                    continue
                                try:
                                    args = json.loads(content[brace_start:end])
                                    break
                                except json.JSONDecodeError:
                                    continue
        except Exception as e:
            log.error(f"  {scenario['id']}: {e}")

        correct_tool = name == scenario["expect_tool"]
        rejected = name in scenario.get("reject_tools", [])
        has_expected = True
        if "expect_in_args" in scenario:
            args_str = json.dumps(args) if isinstance(args, dict) else str(args)
            has_expected = scenario["expect_in_args"].lower() in args_str.lower()

        passed = correct_tool and not rejected and has_expected
        status = "PASS" if passed else "FAIL"

        reason = ""
        if not correct_tool:
            reason = f"Expected {scenario['expect_tool']}, got {name}"
        elif rejected:
            reason = f"Used rejected tool: {name}"
        elif not has_expected:
            reason = f"Missing '{scenario['expect_in_args']}' in args"

        log.info(
            f"  {scenario['id']} [{status}] {scenario['hack']:<22} "
            f"tool={name or 'NONE':<15} "
            f"{'OK' if passed else reason}"
        )

        results.append({
            "id": scenario["id"], "hack": scenario["hack"],
            "desc": scenario["desc"], "status": status,
            "expected": scenario["expect_tool"], "actual": name,
            "rejected": rejected, "reason": reason,
        })

    passed = sum(1 for r in results if r["status"] == "PASS")
    total = len(results)
    print(f"\n{'='*60}")
    print(f"  HACK-FREE BEHAVIOR: {passed}/{total} ({100*passed/total:.0f}%)")
    print(f"{'='*60}")

    if passed < total:
        print(f"\n  STILL NEEDS HACKS:")
        for r in results:
            if r["status"] == "FAIL":
                print(f"    {r['id']} {r['hack']}: {r['reason']}")

    return results


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", default="http://localhost:8095")
    args = parser.parse_args()

    log.info(f"Testing hack-free model behavior against {args.endpoint}\n")
    await eval_hack_free(args.endpoint)


if __name__ == "__main__":
    asyncio.run(main())
