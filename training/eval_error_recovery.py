#!/usr/bin/env python3
"""Error recovery eval — injects specific errors and tests if the model recovers.

Instead of hoping errors occur naturally, this eval FORCES them and measures
whether the model reads the error, diagnoses the cause, and fixes it.

Tests the exact failure modes from live sessions:
  1. Missing npm module → should install it
  2. Type error → should fix the type
  3. Syntax error → should fix the syntax
  4. File not found → should create the file
  5. Wrong path → should correct the path
  6. Build loop → should stop retrying and fix code

Usage:
  python training/eval_error_recovery.py --endpoint http://localhost:8095
"""

import argparse
import asyncio
import json
import logging
import time

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("eval_recovery")

TOOL_SCHEMAS = [
    {"type": "function", "function": {"name": "file_read", "description": "Read a file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "file_write", "description": "Write a file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "file_edit", "description": "Edit a file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]}}},
    {"type": "function", "function": {"name": "shell_exec", "description": "Run a shell command.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
    {"type": "function", "function": {"name": "message_chat", "description": "Talk to the user. done=true ends task, done=false continues.", "parameters": {"type": "object", "properties": {"text": {"type": "string"}, "done": {"type": "boolean"}}, "required": ["text"]}}},
    {"type": "function", "function": {"name": "message_result", "description": "Deliver final result.", "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": []}}},
]

SYSTEM = (
    "You are Tsunami. You are the wave. You build apps by calling tools.\n\n"
    "The ocean:\n"
    "- reef: error. Read it, fix the cause, rebuild.\n"
    "- break: compile. shell_exec build after writing.\n\n"
    "Rules: One tool call per response. Be brief. Fix errors, don't retry blindly."
)

ERROR_SCENARIOS = [
    {
        "id": "ER01",
        "name": "Missing module",
        "setup_messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": "The build just failed. Fix it."},
            {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "shell_exec", "arguments": json.dumps({"command": "cd deliverables/app && npx vite build"})}}]},
            {"role": "tool", "tool_call_id": "c1", "content": "[shell_exec] Error: Cannot find module 'recharts'. Did you install it?"},
        ],
        "expect_tool": "shell_exec",
        "expect_in_args": "npm install recharts",
        "bad_pattern": "npx vite build",  # retrying build without installing = BAD
    },
    {
        "id": "ER02",
        "name": "Type error",
        "setup_messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": "The build just failed. Fix it."},
            {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "shell_exec", "arguments": json.dumps({"command": "cd deliverables/app && npx vite build"})}}]},
            {"role": "tool", "tool_call_id": "c1", "content": "[shell_exec] Error: src/App.tsx(12,5): Type 'null' is not assignable to type 'string'. setError(null) should be setError('')"},
        ],
        "expect_tool": "file_edit",
        "expect_in_args": "setError",
        "bad_pattern": "npx vite build",
    },
    {
        "id": "ER03",
        "name": "Syntax error — missing paren",
        "setup_messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": "The build just failed. Fix it."},
            {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "shell_exec", "arguments": json.dumps({"command": "cd deliverables/app && npx vite build"})}}]},
            {"role": "tool", "tool_call_id": "c1", "content": "[shell_exec] Error: src/App.tsx(8,45): Expected ')' to close '(' at line 8. {items.map(i => <div key={i}>{i}</div>"},
        ],
        "expect_tool": "file_edit",
        "expect_in_args": "map",
        "bad_pattern": "npx vite build",
    },
    {
        "id": "ER04",
        "name": "Import not found",
        "setup_messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": "The build just failed. Fix it."},
            {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "shell_exec", "arguments": json.dumps({"command": "cd deliverables/app && npx vite build"})}}]},
            {"role": "tool", "tool_call_id": "c1", "content": "[shell_exec] Error: Could not resolve './components/Header' from src/App.tsx. File does not exist."},
        ],
        "expect_tool": "file_write",
        "expect_in_args": "Header",
        "bad_pattern": "npx vite build",
    },
    {
        "id": "ER05",
        "name": "Wrong path — cd fails",
        "setup_messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": "The build just failed. Fix it."},
            {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "shell_exec", "arguments": json.dumps({"command": "cd workspace/deliverables/app && npx vite build"})}}]},
            {"role": "tool", "tool_call_id": "c1", "content": "[shell_exec] bash: cd: workspace/deliverables/app: No such file or directory"},
        ],
        "expect_tool": "shell_exec",
        "expect_in_args": "deliverables/app",
        "bad_pattern": "cd workspace/deliverables",  # same wrong path
    },
    {
        "id": "ER06",
        "name": "CSS import missing",
        "setup_messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": "The build just failed. Fix it."},
            {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "shell_exec", "arguments": json.dumps({"command": "cd deliverables/app && npx vite build"})}}]},
            {"role": "tool", "tool_call_id": "c1", "content": "[shell_exec] Error: Could not resolve 'leaflet/dist/leaflet.css' from src/App.tsx"},
        ],
        "expect_tool": "file_edit",
        "expect_in_args": "leaflet",
        "bad_pattern": "npx vite build",
    },
]


async def call_model(endpoint, messages, tools, max_tokens=2048):
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{endpoint}/v1/chat/completions",
            json={
                "model": "eval",
                "messages": messages,
                "tools": tools,
                "tool_choice": "auto",
                "temperature": 0.3,
                "max_tokens": max_tokens,
            },
        )
        resp.raise_for_status()
        return resp.json()


def extract_tool(response):
    choice = response["choices"][0]
    msg = choice["message"]
    if msg.get("tool_calls"):
        tc = msg["tool_calls"][0]
        func = tc["function"]
        args = func.get("arguments", "{}")
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {"raw": args}
        return func["name"], args
    return None, None


async def eval_recovery(endpoint):
    results = []

    for scenario in ERROR_SCENARIOS:
        name, args = None, None
        try:
            response = await call_model(endpoint, scenario["setup_messages"], TOOL_SCHEMAS)
            name, args = extract_tool(response)
        except Exception as e:
            log.error(f"  {scenario['id']}: API error: {e}")

        # Evaluate
        correct_tool = name == scenario["expect_tool"]
        correct_action = False
        bad_retry = False

        if args:
            args_str = json.dumps(args) if isinstance(args, dict) else str(args)
            correct_action = scenario["expect_in_args"].lower() in args_str.lower()
            bad_retry = scenario["bad_pattern"].lower() in args_str.lower()

        status = "PASS" if (correct_tool and correct_action and not bad_retry) else "FAIL"
        reason = ""
        if not correct_tool:
            reason = f"Expected {scenario['expect_tool']}, got {name}"
        elif bad_retry:
            reason = f"Retried build without fixing: {scenario['bad_pattern']}"
        elif not correct_action:
            reason = f"Missing expected action: {scenario['expect_in_args']}"

        log.info(
            f"  {scenario['id']} [{status}] {scenario['name']:<25} "
            f"tool={name or 'NONE':<15} "
            f"{'GOOD: ' + scenario['expect_in_args'] if correct_action else 'BAD: ' + reason}"
        )

        results.append({
            "id": scenario["id"],
            "name": scenario["name"],
            "status": status,
            "expected_tool": scenario["expect_tool"],
            "actual_tool": name,
            "correct_action": correct_action,
            "bad_retry": bad_retry,
            "reason": reason,
        })

    # Summary
    passed = sum(1 for r in results if r["status"] == "PASS")
    total = len(results)
    print(f"\n{'='*50}")
    print(f"  ERROR RECOVERY: {passed}/{total} ({100*passed/total:.0f}%)")
    print(f"{'='*50}")

    return results


async def main():
    parser = argparse.ArgumentParser(description="Error recovery eval")
    parser.add_argument("--endpoint", default="http://localhost:8095")
    parser.add_argument("--output", default="workspace/training_data/eval_recovery_results.json")
    args = parser.parse_args()

    log.info(f"Testing error recovery against {args.endpoint}\n")
    results = await eval_recovery(args.endpoint)

    Path = __import__("pathlib").Path
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump({"timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), "results": results}, f, indent=2)


if __name__ == "__main__":
    asyncio.run(main())
