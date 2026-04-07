#!/usr/bin/env python3
"""Scaffold selection eval — does the model pick the RIGHT scaffold?

Tests that prompt keywords trigger the correct scaffold template.
This is the first decision the model makes, and if it's wrong,
everything downstream is wrong.

Usage:
  python training/eval_scaffold_selection.py --endpoint http://localhost:8095
"""

import argparse
import asyncio
import json
import logging
import time

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("eval_scaffold")

TOOL_SCHEMAS = [
    {"type": "function", "function": {"name": "project_init", "description": "Create a project from the scaffold library. Analyzes needs and picks the right template.", "parameters": {"type": "object", "properties": {"name": {"type": "string", "description": "Project name"}, "dependencies": {"type": "array", "items": {"type": "string"}, "description": "Extra npm packages"}}, "required": ["name"]}}},
    {"type": "function", "function": {"name": "message_chat", "description": "Talk to the user.", "parameters": {"type": "object", "properties": {"text": {"type": "string"}, "done": {"type": "boolean"}}, "required": ["text"]}}},
    {"type": "function", "function": {"name": "search_web", "description": "Search the web.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "plan_update", "description": "Create a plan.", "parameters": {"type": "object", "properties": {"goal": {"type": "string"}, "phases": {"type": "array"}}, "required": ["goal", "phases"]}}},
]

SYSTEM = (
    "You are Tsunami. You are the wave. You build apps by calling tools.\n"
    "Rules: project_init first. One tool call per response. Be brief."
)

# Prompt → expected scaffold (based on project_init.py _pick_scaffold logic)
SCAFFOLD_TESTS = [
    {"id": "S01", "prompt": "Build a 3D solar system with orbiting planets", "expect_scaffold": "threejs", "expect_in_name": ["solar", "3d", "planet"]},
    {"id": "S02", "prompt": "Build a multiplayer chat app with WebSocket", "expect_scaffold": "realtime", "expect_in_name": ["chat", "realtime", "ws"]},
    {"id": "S03", "prompt": "Build a Chrome extension that blocks ads", "expect_scaffold": "chrome", "expect_in_name": ["chrome", "ext", "block", "ad"]},
    {"id": "S04", "prompt": "Build an admin dashboard with charts and a data table", "expect_scaffold": "dashboard", "expect_in_name": ["dashboard", "admin"]},
    {"id": "S05", "prompt": "Build a marketing landing page for a startup", "expect_scaffold": "landing", "expect_in_name": ["landing", "startup", "market"]},
    {"id": "S06", "prompt": "Build a todo app that saves to a database", "expect_scaffold": "fullstack", "expect_in_name": ["todo", "db", "full"]},
    {"id": "S07", "prompt": "Build a CSV file upload and data viewer", "expect_scaffold": "form", "expect_in_name": ["csv", "upload", "file", "form"]},
    {"id": "S08", "prompt": "Build a snake game", "expect_scaffold": "pixi", "expect_in_name": ["snake", "game"]},
    {"id": "S09", "prompt": "Build a desktop app with system tray icon", "expect_scaffold": "electron", "expect_in_name": ["desktop", "electron", "tray"]},
    {"id": "S10", "prompt": "Build a simple counter with plus and minus", "expect_scaffold": "react", "expect_in_name": ["counter", "calc", "simple"]},
    {"id": "S11", "prompt": "Build a data analytics dashboard with d3 charts", "expect_scaffold": "data-viz", "expect_in_name": ["analytics", "chart", "d3", "viz"]},
    {"id": "S12", "prompt": "Build a top-down arena shooter with physics", "expect_scaffold": "webgpu", "expect_in_name": ["arena", "shooter", "game", "engine"]},
]


async def call_model(endpoint, messages, tools):
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{endpoint}/v1/chat/completions",
            json={
                "model": "eval", "messages": messages, "tools": tools,
                "tool_choice": "auto", "temperature": 0.3, "max_tokens": 1024,
            },
        )
        resp.raise_for_status()
        return resp.json()


async def eval_scaffolds(endpoint):
    results = []

    for test in SCAFFOLD_TESTS:
        messages = [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": test["prompt"]},
        ]

        name, args = None, {}
        try:
            response = await call_model(endpoint, messages, TOOL_SCHEMAS)
            choice = response["choices"][0]["message"]
            if choice.get("tool_calls"):
                tc = choice["tool_calls"][0]
                name = tc["function"]["name"]
                a = tc["function"].get("arguments", "{}")
                args = json.loads(a) if isinstance(a, str) else a
        except Exception as e:
            log.error(f"  {test['id']}: {e}")

        # Check: did it call project_init?
        called_init = name == "project_init"

        # Check: does the project name hint at the right scaffold?
        proj_name = args.get("name", "").lower() if isinstance(args, dict) else ""
        name_matches = any(kw in proj_name for kw in test["expect_in_name"])

        # Check: did it include relevant dependencies?
        deps = args.get("dependencies", []) if isinstance(args, dict) else []

        status = "PASS" if called_init and name_matches else "FAIL"
        reason = ""
        if not called_init:
            reason = f"Called {name} instead of project_init"
        elif not name_matches:
            reason = f"Name '{proj_name}' doesn't hint at {test['expect_scaffold']} scaffold"

        log.info(
            f"  {test['id']} [{status}] {test['prompt'][:45]:<45} "
            f"name='{proj_name}' deps={deps} "
            f"{'→ ' + test['expect_scaffold'] if status == 'PASS' else '✗ ' + reason}"
        )

        results.append({
            "id": test["id"], "prompt": test["prompt"],
            "status": status, "expected": test["expect_scaffold"],
            "project_name": proj_name, "dependencies": deps,
            "called_init": called_init, "name_matches": name_matches,
            "reason": reason,
        })

    passed = sum(1 for r in results if r["status"] == "PASS")
    print(f"\n{'='*50}")
    print(f"  SCAFFOLD SELECTION: {passed}/{len(results)} ({100*passed/len(results):.0f}%)")
    print(f"{'='*50}")
    return results


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", default="http://localhost:8095")
    args = parser.parse_args()

    log.info(f"Testing scaffold selection against {args.endpoint}\n")
    await eval_scaffolds(args.endpoint)


if __name__ == "__main__":
    asyncio.run(main())
