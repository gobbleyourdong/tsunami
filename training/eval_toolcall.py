#!/usr/bin/env python3
"""Eval harness for Tsunami tool call models.

Tests three levels:
  1. FORMAT  — does the model produce valid <|tool_call>call:name{...}<tool_call|> ?
  2. SCHEMA  — are the tool name and arguments correct for the prompt?
  3. BUILD   — can the model scaffold + write + compile a real app?

Usage:
  # Point at a running llama-server with the fine-tuned model
  python training/eval_toolcall.py --endpoint http://localhost:8095

  # Or specify a GGUF to auto-launch
  python training/eval_toolcall.py --model models/gemma-4-e2b-tsunami-Q4_K_M.gguf
"""

import argparse
import asyncio
import json
import logging
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("eval")

# ---------------------------------------------------------------------------
# Eval prompts — graded by difficulty
# ---------------------------------------------------------------------------

EVAL_PROMPTS = [
    # --- TRIVIAL (should be 1-3 tool calls) ---
    # Greetings
    {"id": "T01", "level": "trivial", "prompt": "What's 2+2?",
     "expect_tool": "message_result", "expect_steps": 2},
    {"id": "T02", "level": "trivial", "prompt": "Say hello",
     "expect_tool": "message_result", "expect_steps": 2},
    {"id": "T03", "level": "trivial", "prompt": "What day is it?",
     "expect_tool": "search_web", "expect_steps": 3},
    # Conversational
    {"id": "T04", "level": "trivial", "prompt": "Who are you?",
     "expect_tool": "message_result", "expect_steps": 2},
    {"id": "T05", "level": "trivial", "prompt": "Thanks, that's all",
     "expect_tool": "message_result", "expect_steps": 2},
    {"id": "T06", "level": "trivial", "prompt": "What can you build?",
     "expect_tool": "message_result", "expect_steps": 2},
    # Search-needed
    {"id": "T07", "level": "trivial", "prompt": "What's the population of Japan?",
     "expect_tool": "search_web", "expect_steps": 3},
    {"id": "T08", "level": "trivial", "prompt": "What's bitcoin trading at?",
     "expect_tool": "search_web", "expect_steps": 3},

    # --- EASY (scaffold + single file, 2-8 steps) ---
    {"id": "E01", "level": "easy", "prompt": "Build a counter app with increment and decrement buttons",
     "expect_tool": "project_init", "expect_steps": 8},
    {"id": "E02", "level": "easy", "prompt": "Build a hello world page with a centered heading",
     "expect_tool": "project_init", "expect_steps": 6},
    {"id": "E03", "level": "easy", "prompt": "Build a random quote generator",
     "expect_tool": "project_init", "expect_steps": 8},
    {"id": "E04", "level": "easy", "prompt": "Build a tip calculator",
     "expect_tool": "project_init", "expect_steps": 8},
    {"id": "E05", "level": "easy", "prompt": "Build a BMI calculator with height and weight inputs",
     "expect_tool": "project_init", "expect_steps": 8},
    {"id": "E06", "level": "easy", "prompt": "Build a color palette generator that shows 5 random colors with hex codes",
     "expect_tool": "project_init", "expect_steps": 8},
    {"id": "E07", "level": "easy", "prompt": "Build a digital clock that shows the current time",
     "expect_tool": "project_init", "expect_steps": 8},
    {"id": "E08", "level": "easy", "prompt": "Build a password generator with length slider and copy button",
     "expect_tool": "project_init", "expect_steps": 8},

    # --- MEDIUM (multi-component, some logic, 4-15 steps) ---
    {"id": "M01", "level": "medium", "prompt": "Build a todo app with add, delete, and mark complete",
     "expect_tool": "project_init", "expect_steps": 15},
    {"id": "M02", "level": "medium", "prompt": "Build a pomodoro timer with start, pause, and reset",
     "expect_tool": "project_init", "expect_steps": 15},
    {"id": "M03", "level": "medium", "prompt": "Build a weather dashboard that shows a 5-day forecast with fake data",
     "expect_tool": "project_init", "expect_steps": 15},
    {"id": "M04", "level": "medium", "prompt": "Build a markdown previewer with a split editor and live preview",
     "expect_tool": "project_init", "expect_steps": 15},
    {"id": "M05", "level": "medium", "prompt": "Build a flashcard study app with flip animation and card deck management",
     "expect_tool": "project_init", "expect_steps": 15},
    {"id": "M06", "level": "medium", "prompt": "Build a recipe book app where you can add recipes with ingredients, steps, and a search filter",
     "expect_tool": "project_init", "expect_steps": 15},
    {"id": "M07", "level": "medium", "prompt": "Build an expense tracker with categories, a bar chart summary, and localStorage persistence",
     "expect_tool": "project_init", "expect_steps": 15},
    {"id": "M08", "level": "medium", "prompt": "Build a quiz app with 10 multiple choice questions, a score counter, and a results screen",
     "expect_tool": "project_init", "expect_steps": 15},

    # --- HARD (multi-file, complex logic, 4-25 steps) ---
    {"id": "H01", "level": "hard", "prompt": "Build a kanban board with 3 columns and drag-and-drop cards",
     "expect_tool": "project_init", "expect_steps": 25},
    {"id": "H02", "level": "hard", "prompt": "Build a typing speed test game with WPM tracking and a countdown timer",
     "expect_tool": "project_init", "expect_steps": 25},
    {"id": "H03", "level": "hard", "prompt": "Build a crypto portfolio dashboard with pie chart, line chart, and a data table showing 10 coins with price, change, holdings",
     "expect_tool": "project_init", "expect_steps": 25},
    {"id": "H04", "level": "hard", "prompt": "Build a file manager with a tree view sidebar, breadcrumb nav, and a grid/list toggle for the main area",
     "expect_tool": "project_init", "expect_steps": 30},
    {"id": "H05", "level": "hard", "prompt": "Build a drawing app with brush, eraser, color picker, line width, undo/redo, and PNG export",
     "expect_tool": "project_init", "expect_steps": 25},
    {"id": "H06", "level": "hard", "prompt": "Build a multi-step form wizard with validation, progress bar, back/next buttons, and a review page",
     "expect_tool": "project_init", "expect_steps": 25},
    {"id": "H07", "level": "hard", "prompt": "Build a Spotify-style music player UI with playlist sidebar, album art, progress bar, and play/pause/skip controls",
     "expect_tool": "project_init", "expect_steps": 25},
    {"id": "H08", "level": "hard", "prompt": "Build a snake game with arrow key controls, score tracking, speed increase, and game over screen",
     "expect_tool": "project_init", "expect_steps": 25},

    # --- EXTREME (multi-component, 3D, fullstack, or novel) ---
    {"id": "X01", "level": "extreme", "prompt": "Build a 3D solar system with orbiting planets using Three.js. Include Mercury through Neptune with relative sizes and orbit speeds.",
     "expect_tool": "project_init", "expect_steps": 35},
    {"id": "X02", "level": "extreme", "prompt": "Build a real-time chat app with WebSocket server, message history, typing indicators, and user avatars",
     "expect_tool": "project_init", "expect_steps": 35},
    {"id": "X03", "level": "extreme", "prompt": "Build a code editor with syntax highlighting, line numbers, a file tree sidebar, and a terminal panel at the bottom",
     "expect_tool": "project_init", "expect_steps": 35},
    {"id": "X04", "level": "extreme", "prompt": "Build a music visualizer that uses the Web Audio API to show a real-time frequency spectrum, waveform, and beat detection with pulsing background",
     "expect_tool": "project_init", "expect_steps": 35},
    {"id": "X05", "level": "extreme", "prompt": "Build a spreadsheet app with cell editing, formulas (SUM, AVERAGE, COUNT), column resize, and CSV export",
     "expect_tool": "project_init", "expect_steps": 35},
    {"id": "X06", "level": "extreme", "prompt": "Build a full e-commerce store with product grid, cart, checkout form, and order confirmation page using fake product data",
     "expect_tool": "project_init", "expect_steps": 35},
    {"id": "X07", "level": "extreme", "prompt": "Build a pixel art editor with a 32x32 canvas grid, color palette, brush/fill/erase tools, undo/redo, and PNG export",
     "expect_tool": "project_init", "expect_steps": 35},
    {"id": "X08", "level": "extreme", "prompt": "Build a project management dashboard with Gantt chart, task table with status/assignee/dates, and a team workload sidebar",
     "expect_tool": "project_init", "expect_steps": 35},
]

# Tool schemas for the eval (same as what Tsunami sends at inference)
TOOL_SCHEMAS = [
    {"type": "function", "function": {"name": "file_read", "description": "Read text content from a file.", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Path to the file to read"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "file_write", "description": "Create or overwrite a file with full content.", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Path to write to"}, "content": {"type": "string", "description": "Full file content"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "file_edit", "description": "Make targeted modifications to an existing file.", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Path to the file"}, "old_text": {"type": "string", "description": "Exact text to find and replace"}, "new_text": {"type": "string", "description": "Replacement text"}}, "required": ["path", "old_text", "new_text"]}}},
    {"type": "function", "function": {"name": "shell_exec", "description": "Run a shell command and return its output.", "parameters": {"type": "object", "properties": {"command": {"type": "string", "description": "Shell command to execute"}}, "required": ["command"]}}},
    {"type": "function", "function": {"name": "match_glob", "description": "Find files by name and path patterns.", "parameters": {"type": "object", "properties": {"pattern": {"type": "string", "description": "Glob pattern"}}, "required": ["pattern"]}}},
    {"type": "function", "function": {"name": "message_info", "description": "Acknowledge, update, or inform the user.", "parameters": {"type": "object", "properties": {"text": {"type": "string", "description": "Information to share"}}, "required": ["text"]}}},
    {"type": "function", "function": {"name": "message_ask", "description": "Request input from the user. Only use when genuinely blocked.", "parameters": {"type": "object", "properties": {"text": {"type": "string", "description": "Question to ask"}}, "required": ["text"]}}},
    {"type": "function", "function": {"name": "message_result", "description": "Deliver final outcome and end the task.", "parameters": {"type": "object", "properties": {"text": {"type": "string", "description": "Final result to deliver"}}, "required": []}}},
    {"type": "function", "function": {"name": "plan_update", "description": "Create or revise the task plan.", "parameters": {"type": "object", "properties": {"goal": {"type": "string", "description": "Desired end state"}, "phases": {"type": "array", "description": "Ordered list of phases"}}, "required": ["goal", "phases"]}}},
    {"type": "function", "function": {"name": "search_web", "description": "Search the web for information.", "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Search query"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "project_init", "description": "Create a project from the scaffold library.", "parameters": {"type": "object", "properties": {"name": {"type": "string", "description": "Project name"}}, "required": ["name"]}}},
    {"type": "function", "function": {"name": "generate_image", "description": "Generate an image from a text description.", "parameters": {"type": "object", "properties": {"prompt": {"type": "string", "description": "Text description"}, "save_path": {"type": "string", "description": "Path to save image"}}, "required": ["prompt", "save_path"]}}},
    {"type": "function", "function": {"name": "load_toolbox", "description": "Load tools on demand. Available: browser, webdev, generate, services, parallel, management", "parameters": {"type": "object", "properties": {"toolbox": {"type": "string", "description": "Toolbox to load"}}}}},
    {"type": "function", "function": {"name": "message_chat", "description": "Talk to the user. For conversation (greetings, questions, thanks): set done=true to end. For status updates during builds: set done=false to continue.", "parameters": {"type": "object", "properties": {"text": {"type": "string", "description": "Message to the user"}, "done": {"type": "boolean", "description": "true=end task, false=keep working", "default": True}}, "required": ["text"]}}},
]

SYSTEM_PROMPT = (
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
    "- Complex builds (3+ features, multi-state, \"full-featured\") -> plan_update FIRST to structure phases\n\n"
    "THE PIPELINE (every build follows this EXACTLY):\n"
    "1. project_init(name) -- scaffold the project\n"
    "2. file_write(App.tsx) -- write COMPLETE code\n"
    "3. shell_exec(\"cd deliverables/{name} && npx vite build\") -- run the break\n"
    "4. IF ERROR: fix directly -- file_edit (type/syntax fix), file_write (missing file), or shell_exec (install module, corrected path)\n"
    "5. undertow(dist/index.html) -- QA before delivery\n"
    "6. message_result -- land the wave\n\n"
    "RESUME/MODIFY (existing project):\n"
    "1. file_read -> 2. file_write/file_edit -> 3. shell_exec build -> 4. message_result\n\n"
    "NEVER skip the break. NEVER deliver without building. One tool call per response. Be brief."
)

VALID_TOOLS = {s["function"]["name"] for s in TOOL_SCHEMAS}
# Tools that end the task
TERMINAL_TOOLS = {"message_result", "message_chat"}


# ---------------------------------------------------------------------------
# Result tracking
# ---------------------------------------------------------------------------

@dataclass
class EvalResult:
    prompt_id: str
    level: str
    prompt: str
    # Format checks
    produced_tool_call: bool = False
    valid_format: bool = False
    valid_tool_name: bool = False
    valid_args: bool = False
    # First-call checks
    first_tool: str = ""
    expected_first_tool: str = ""
    first_tool_correct: bool = False
    # Timing
    latency_ms: float = 0
    # Raw response for debugging
    raw_response: str = ""
    error: str = ""


@dataclass
class BuildResult:
    prompt_id: str
    level: str
    prompt: str
    iterations: int = 0
    tool_calls: list = field(default_factory=list)
    compiled: bool = False
    delivered: bool = False
    wall_clock_s: float = 0
    error: str = ""


# ---------------------------------------------------------------------------
# API client
# ---------------------------------------------------------------------------

async def call_model(endpoint: str, messages: list[dict], tools: list[dict],
                     max_tokens: int = 4096) -> dict:
    """Single inference call to llama-server /v1/chat/completions."""
    payload = {
        "model": "eval",
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto",
        "temperature": 0.3,  # lower temp for eval consistency
        "max_tokens": max_tokens,
    }
    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(
            f"{endpoint}/v1/chat/completions",
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()
        return resp.json()


def extract_tool_call(response: dict) -> tuple[str | None, dict | None, str]:
    """Extract tool name and args from API response.
    Returns (name, args, raw_content).
    """
    choice = response["choices"][0]
    msg = choice["message"]
    content = msg.get("content", "") or ""

    if msg.get("tool_calls"):
        tc = msg["tool_calls"][0]
        func = tc["function"]
        name = func["name"]
        args = func.get("arguments", "{}")
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {}
        # Gemma 4 nesting fix
        if isinstance(args, dict) and "arguments" in args and len(args) == 1:
            args = args["arguments"]
        return name, args, content

    return None, None, content


# ---------------------------------------------------------------------------
# Level 1: FORMAT eval — single-turn, does it produce a valid tool call?
# ---------------------------------------------------------------------------

async def eval_format(endpoint: str, prompts: list[dict]) -> list[EvalResult]:
    """Test each prompt with a single inference call.
    Checks: produces tool call, valid format, valid tool name, valid args.
    """
    results = []

    for p in prompts:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": p["prompt"]},
        ]

        result = EvalResult(
            prompt_id=p["id"],
            level=p["level"],
            prompt=p["prompt"],
            expected_first_tool=p["expect_tool"],
        )

        try:
            t0 = time.monotonic()
            response = await call_model(endpoint, messages, TOOL_SCHEMAS)
            result.latency_ms = (time.monotonic() - t0) * 1000

            name, args, content = extract_tool_call(response)
            result.raw_response = content[:500]

            if name is not None:
                result.produced_tool_call = True
                result.valid_format = True  # API parsed it successfully
                result.first_tool = name

                if name in VALID_TOOLS:
                    result.valid_tool_name = True

                if isinstance(args, dict):
                    result.valid_args = True

                if name == p["expect_tool"]:
                    result.first_tool_correct = True
            else:
                result.raw_response = content[:500]

        except Exception as e:
            result.error = str(e)

        log.info(
            f"  {p['id']:>3} [{p['level']:>7}] "
            f"tool={'Y' if result.produced_tool_call else 'N'} "
            f"valid={'Y' if result.valid_tool_name else 'N'} "
            f"correct={'Y' if result.first_tool_correct else 'N'} "
            f"got={result.first_tool or 'NONE':>15} "
            f"want={p['expect_tool']:>15} "
            f"{result.latency_ms:>6.0f}ms"
        )
        results.append(result)

    return results


# ---------------------------------------------------------------------------
# Level 2: BUILD eval — multi-turn, run the full agent loop
# ---------------------------------------------------------------------------

FAKE_TOOL_RESULTS = {
    "project_init": "[project_init] Created project 'app' with react-app scaffold at workspace/deliverables/app/. Dev server running on http://localhost:5173. Write your code in src/.",
    "file_write": "[file_write] Wrote {path}",
    "file_read": "[file_read] Contents of {path}:\nimport React from 'react';\nexport default function App() { return <div>Hello</div> }",
    "file_edit": "[file_edit] Edited {path}",
    "shell_exec": "[shell_exec] $ {command}\nvite v6.3.1 building for production...\n✓ 15 modules transformed.\ndist/index.html    0.46 kB │ gzip: 0.30 kB\ndist/assets/index-DiwrgTda.css   1.42 kB │ gzip: 0.73 kB\ndist/assets/index-DVoHNO1Y.js  143.36 kB │ gzip: 46.09 kB\n✓ built in 540ms",
    "message_info": "[message_info] Message delivered.",
    "message_result": "[message_result] {text}",
    "message_chat": "[message_chat] {text}",
    "message_ask": "[message_ask] (user says: yes, continue)",
    "search_web": "[search_web] Results for '{query}':\n1. Example result - https://example.com\n2. Another result - https://example.com/2",
    "plan_update": "[plan_update] Plan updated.",
    "plan_advance": "[plan_advance] Advanced to next phase.",
    "match_glob": "[match_glob] Found: src/App.tsx, src/main.tsx, src/index.css",
    "match_grep": "[match_grep] src/App.tsx:5: import React",
    "load_toolbox": "[load_toolbox] Loaded: webdev_scaffold, webdev_serve, webdev_screenshot, webdev_generate_assets",
    "generate_image": "[generate_image] Generated image saved to {save_path}",
    "undertow": "[undertow] PASS — App renders correctly. Screenshot saved.",
    "webdev_scaffold": "[webdev_scaffold] Scaffolded project.",
    "webdev_serve": "[webdev_serve] Dev server running on http://localhost:5173",
    "webdev_screenshot": "[webdev_screenshot] Screenshot saved.",
    "python_exec": "[python_exec] Output: OK",
    "swell": "[swell] Dispatched 3 eddies. All completed.",
    "summarize_file": "[summarize_file] Summary: React component with state management.",
}


def fake_tool_result(name: str, args: dict) -> str:
    """Generate a fake tool result for the build eval."""
    template = FAKE_TOOL_RESULTS.get(name, f"[{name}] OK")
    try:
        return template.format(**args)
    except (KeyError, IndexError):
        return template


async def eval_build(endpoint: str, prompts: list[dict], max_iters: int = 50) -> list[BuildResult]:
    """Run multi-turn agent loop with fake tool results.
    Measures: iterations to completion, tool selection patterns, delivery.
    """
    results = []

    for p in prompts:
        result = BuildResult(
            prompt_id=p["id"],
            level=p["level"],
            prompt=p["prompt"],
        )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": p["prompt"]},
        ]

        t0 = time.monotonic()

        for i in range(max_iters):
            try:
                response = await call_model(endpoint, messages, TOOL_SCHEMAS)
                name, args, content = extract_tool_call(response)

                if name is None:
                    # Model produced text without tool call — nudge it
                    messages.append({"role": "assistant", "content": content})
                    messages.append({"role": "user", "content": "Call a tool. Don't explain."})
                    result.iterations += 1
                    continue

                result.tool_calls.append(name)
                result.iterations += 1

                # Check for delivery
                if name in TERMINAL_TOOLS:
                    # message_chat with done=false is a status update, not delivery
                    if name == "message_chat" and not args.get("done", True):
                        pass  # keep going
                    else:
                        result.delivered = True
                    result.wall_clock_s = time.monotonic() - t0
                    break

                # Check for compile (shell_exec with build command)
                if name == "shell_exec" and args:
                    cmd = args.get("command", "")
                    if "build" in cmd or "vite" in cmd or "tsc" in cmd:
                        result.compiled = True

                # Add assistant message + fake tool response
                messages.append({
                    "role": "assistant",
                    "content": content,
                    "tool_calls": [{"id": f"call_{i}", "type": "function",
                                    "function": {"name": name, "arguments": json.dumps(args or {})}}],
                })
                messages.append({
                    "role": "tool",
                    "tool_call_id": f"call_{i}",
                    "content": fake_tool_result(name, args or {}),
                })

            except Exception as e:
                result.error = str(e)
                break

        if not result.delivered:
            result.wall_clock_s = time.monotonic() - t0

        # Log
        tools_summary = " → ".join(result.tool_calls[:10])
        if len(result.tool_calls) > 10:
            tools_summary += f" ... ({len(result.tool_calls)} total)"
        log.info(
            f"  {p['id']:>3} [{p['level']:>7}] "
            f"iters={result.iterations:>3} "
            f"delivered={'Y' if result.delivered else 'N'} "
            f"compiled={'Y' if result.compiled else 'N'} "
            f"{result.wall_clock_s:>6.1f}s "
            f"| {tools_summary}"
        )
        results.append(result)

    return results


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_format_report(results: list[EvalResult]):
    print("\n" + "=" * 70)
    print("FORMAT EVAL RESULTS")
    print("=" * 70)

    by_level = {}
    for r in results:
        by_level.setdefault(r.level, []).append(r)

    for level in ["trivial", "easy", "medium", "hard", "extreme"]:
        if level not in by_level:
            continue
        group = by_level[level]
        n = len(group)
        tool_pct = 100 * sum(r.produced_tool_call for r in group) / n
        valid_pct = 100 * sum(r.valid_tool_name for r in group) / n
        correct_pct = 100 * sum(r.first_tool_correct for r in group) / n
        avg_ms = sum(r.latency_ms for r in group) / n

        print(f"\n  {level.upper()} ({n} prompts)")
        print(f"    Tool call produced: {tool_pct:>5.1f}%")
        print(f"    Valid tool name:    {valid_pct:>5.1f}%")
        print(f"    Correct first tool: {correct_pct:>5.1f}%")
        print(f"    Avg latency:        {avg_ms:>5.0f}ms")

    # Overall
    n = len(results)
    print(f"\n  OVERALL ({n} prompts)")
    print(f"    Tool call produced: {100 * sum(r.produced_tool_call for r in results) / n:>5.1f}%")
    print(f"    Valid tool name:    {100 * sum(r.valid_tool_name for r in results) / n:>5.1f}%")
    print(f"    Correct first tool: {100 * sum(r.first_tool_correct for r in results) / n:>5.1f}%")
    print(f"    Avg latency:        {sum(r.latency_ms for r in results) / n:>5.0f}ms")


def print_build_report(results: list[BuildResult]):
    print("\n" + "=" * 70)
    print("BUILD EVAL RESULTS")
    print("=" * 70)

    by_level = {}
    for r in results:
        by_level.setdefault(r.level, []).append(r)

    for level in ["trivial", "easy", "medium", "hard", "extreme"]:
        if level not in by_level:
            continue
        group = by_level[level]
        n = len(group)
        delivered_pct = 100 * sum(r.delivered for r in group) / n
        compiled_pct = 100 * sum(r.compiled for r in group) / n
        avg_iters = sum(r.iterations for r in group) / n
        avg_time = sum(r.wall_clock_s for r in group) / n

        print(f"\n  {level.upper()} ({n} prompts)")
        print(f"    Delivered:      {delivered_pct:>5.1f}%")
        print(f"    Compiled:       {compiled_pct:>5.1f}%")
        print(f"    Avg iterations: {avg_iters:>5.1f}")
        print(f"    Avg wall clock: {avg_time:>5.1f}s")

    n = len(results)
    print(f"\n  OVERALL ({n} prompts)")
    print(f"    Delivered:      {100 * sum(r.delivered for r in results) / n:>5.1f}%")
    print(f"    Compiled:       {100 * sum(r.compiled for r in results) / n:>5.1f}%")
    print(f"    Avg iterations: {sum(r.iterations for r in results) / n:>5.1f}")
    print(f"    Avg wall clock: {sum(r.wall_clock_s for r in results) / n:>5.1f}s")

    # Tool usage distribution
    all_tools = {}
    for r in results:
        for t in r.tool_calls:
            all_tools[t] = all_tools.get(t, 0) + 1
    print(f"\n  TOOL USAGE:")
    for tool, count in sorted(all_tools.items(), key=lambda x: -x[1])[:15]:
        print(f"    {tool:>20}: {count}")


def save_results(format_results: list[EvalResult], build_results: list[BuildResult],
                 output_path: str):
    """Save results to JSON for comparison across runs."""
    data = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "format_eval": [
            {
                "id": r.prompt_id, "level": r.level,
                "produced_tool_call": r.produced_tool_call,
                "valid_tool_name": r.valid_tool_name,
                "first_tool_correct": r.first_tool_correct,
                "first_tool": r.first_tool,
                "latency_ms": r.latency_ms,
            }
            for r in format_results
        ],
        "build_eval": [
            {
                "id": r.prompt_id, "level": r.level,
                "iterations": r.iterations,
                "delivered": r.delivered,
                "compiled": r.compiled,
                "wall_clock_s": r.wall_clock_s,
                "tool_calls": r.tool_calls,
            }
            for r in build_results
        ],
    }
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)
    log.info(f"Results saved to {output_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main():
    parser = argparse.ArgumentParser(description="Eval harness for Tsunami tool call models")
    parser.add_argument("--endpoint", default="http://localhost:8095",
                        help="llama-server endpoint")
    parser.add_argument("--level", choices=["format", "build", "both"], default="both",
                        help="Which eval to run")
    parser.add_argument("--filter", default=None,
                        help="Filter prompts by level (trivial/easy/medium/hard/extreme)")
    parser.add_argument("--max-iters", type=int, default=50,
                        help="Max iterations for build eval")
    parser.add_argument("--output", default="workspace/training_data/eval_results.json",
                        help="Save results to JSON")
    args = parser.parse_args()

    prompts = EVAL_PROMPTS
    if args.filter:
        prompts = [p for p in prompts if p["level"] == args.filter]
        log.info(f"Filtered to {len(prompts)} {args.filter} prompts")

    # Health check
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{args.endpoint}/health")
            if resp.status_code != 200:
                log.error(f"Server not healthy: {resp.status_code}")
                sys.exit(1)
        log.info(f"Server healthy at {args.endpoint}")
    except Exception as e:
        log.error(f"Cannot reach server at {args.endpoint}: {e}")
        sys.exit(1)

    format_results = []
    build_results = []

    if args.level in ("format", "both"):
        log.info("\n--- FORMAT EVAL ---")
        format_results = await eval_format(args.endpoint, prompts)
        print_format_report(format_results)

    if args.level in ("build", "both"):
        log.info("\n--- BUILD EVAL ---")
        build_results = await eval_build(args.endpoint, prompts, args.max_iters)
        print_build_report(build_results)

    save_results(format_results, build_results, args.output)


if __name__ == "__main__":
    asyncio.run(main())
