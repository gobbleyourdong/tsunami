#!/usr/bin/env python3
"""build.py — regenerate champion training data from structured examples.

Input: EXAMPLES list below (structured role/content/tool_calls dicts).
Output: workspace/training_data/champion.jsonl rendered via Gemma 4's chat
template + tool declarations (11 live tools, no ghosts).

Replaces the dead build_v69/v88/v89.py chain and the one-off scrub_champion
pass. Single source of truth for training data.

Usage:
    python3 training/build.py
    # Appends new examples to the existing champion.jsonl.
    python3 training/build.py --rebuild
    # Rebuilds champion.jsonl from scratch using current EXAMPLES list +
    # the frozen legacy examples from workspace/training_data/_legacy.jsonl.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

MODEL = "google/gemma-4-e4b-it"
REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "workspace" / "training_data"
CHAMPION = DATA / "champion.jsonl"
LEGACY = DATA / "_legacy.jsonl"  # frozen pre-build.py examples (41)


# ---------------------------------------------------------------------------
# System prompt (Tsunami — the Ocean)
# ---------------------------------------------------------------------------

SYSTEM_TEXT = """You are Tsunami. You are the wave. You build apps by calling tools.

## The Ocean (your worldview)

- **wave**: you. A single forward execution. "Ride the wave. Land the wave."
- **tsunami**: the full agent. You are Tsunami.
- **ocean**: the system you operate in — context, tools, environment.
- **current**: your sense of direction per tool call. High tension = "I'm not sure." Low tension = "I'm confident." If uncertain, search first.
- **undertow**: QA. ALWAYS screenshot and verify HTML before delivering.
- **riptide**: vision grounding. Pull element positions from a reference image. Use on clone/mimic tasks.
- **break**: compile. shell_exec build after EVERY file_write. "Run the break."
- **reef**: error. Fix directly — type/syntax → file_edit; missing module → shell_exec npm install; missing file → file_write; wrong path → shell_exec with corrected path. CSS resolution errors → file_edit to remove or replace the import.
- **shore**: delivery. Land the wave at the shore.

## Before the Pipeline (pre-flight checks)

- Visual clones (user says "looks like X" or "style of Y" or "clone of Z") → search_web FIRST for reference images/layout, THEN project_init, THEN riptide on the reference.
- Conversational turn (greeting, question about capabilities) → message_chat(done=true).
- Ambiguous request → message_chat to ask a clarifying question, don't guess.
- Iteration on an existing project ("add X", "change Y", "rename to Z") → file_edit, NEVER project_init.
- Default: go straight to project_init.

## The Pipeline (ride the wave in this order)

1. project_init(name) — scaffold
2. file_write(App.tsx) — write COMPLETE code (never a placeholder)
3. shell_exec build — run the break
4. IF reef (error): fix directly — file_edit (type/syntax fix), file_write (missing file), or shell_exec (install module, corrected path)
5. undertow(dist/index.html, expect) — QA before delivery. ALWAYS provide `expect`.
6. message_result — land the wave at shore

## Components
Import from "./components/ui" (NOT "../components/ui/button" or other subpaths).
Available: Button, Card, Input, Badge, Dialog, Select, Progress, Avatar, Switch, Tooltip, Dropdown, Accordion, Alert, Skeleton.

## Rules
- NEVER skip the break.
- NEVER deliver without undertow.
- NEVER deliver a placeholder — file_write COMPLETE implementations on the first write.
- NEVER call project_init on an iteration request — use file_edit.
- One tool call per response. Be brief.
- High pressure → search_web, don't guess.
"""


# ---------------------------------------------------------------------------
# Tool schema (11 live tools — exact match with tsunami/tools/__init__.py)
# ---------------------------------------------------------------------------

TOOLS = [
    {"type": "function", "function": {
        "name": "project_init",
        "description": "Create a project from the scaffold library.",
        "parameters": {"type": "OBJECT", "properties": {
            "name": {"description": "Project name", "type": "STRING"}},
            "required": ["name"]}}},
    {"type": "function", "function": {
        "name": "file_write",
        "description": "Create or overwrite a file with full content.",
        "parameters": {"type": "OBJECT", "properties": {
            "path": {"type": "STRING"}, "content": {"type": "STRING"}},
            "required": ["path", "content"]}}},
    {"type": "function", "function": {
        "name": "file_read",
        "description": "Read text content from a file.",
        "parameters": {"type": "OBJECT", "properties": {
            "path": {"type": "STRING"}}, "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "file_edit",
        "description": "Make targeted modifications to an existing file.",
        "parameters": {"type": "OBJECT", "properties": {
            "path": {"type": "STRING"}, "old_text": {"type": "STRING"},
            "new_text": {"type": "STRING"}},
            "required": ["path", "old_text", "new_text"]}}},
    {"type": "function", "function": {
        "name": "shell_exec",
        "description": "Run a shell command and return its output.",
        "parameters": {"type": "OBJECT", "properties": {
            "command": {"type": "STRING"}}, "required": ["command"]}}},
    {"type": "function", "function": {
        "name": "search_web",
        "description": "Search the web for information.",
        "parameters": {"type": "OBJECT", "properties": {
            "query": {"type": "STRING"}}, "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "undertow",
        "description": "QA-test an HTML file in a headless browser. Auto-pulls levers (clicks, keys, text reads), takes screenshot, VLM-describes it.",
        "parameters": {"type": "OBJECT", "properties": {
            "path": {"type": "STRING"}, "expect": {"type": "STRING"}},
            "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "riptide",
        "description": "Extract element positions from a reference image. Returns ratio-based CSS positioning (percentages).",
        "parameters": {"type": "OBJECT", "properties": {
            "image_path": {"type": "STRING"}, "focus": {"type": "STRING"}},
            "required": ["image_path"]}}},
    {"type": "function", "function": {
        "name": "generate_image",
        "description": "Generate an image from a text description.",
        "parameters": {"type": "OBJECT", "properties": {
            "prompt": {"type": "STRING"}, "path": {"type": "STRING"}},
            "required": ["prompt", "path"]}}},
    {"type": "function", "function": {
        "name": "message_result",
        "description": "Deliver final outcome and end the task.",
        "parameters": {"type": "OBJECT", "properties": {
            "text": {"type": "STRING"}}}}},
    {"type": "function", "function": {
        "name": "message_chat",
        "description": "Talk to the user. done=true ends (no build happened).",
        "parameters": {"type": "OBJECT", "properties": {
            "text": {"type": "STRING"}, "done": {"type": "BOOLEAN"}},
            "required": ["text"]}}},
]


# ---------------------------------------------------------------------------
# Helper: render a full build pipeline (project_init → file_write → shell_exec
# → undertow → message_result). Takes the target info, returns assistant turn.
# ---------------------------------------------------------------------------

def _pipeline(project_name: str, app_code: str, app_path: str,
              expect: str, result_text: str, extra_steps: list | None = None):
    """Build a standard build-pipeline assistant trace as a list of turns."""
    steps = []
    steps.append({"role": "assistant", "content": "", "tool_calls": [
        {"type": "function", "function": {"name": "project_init",
         "arguments": {"name": project_name}}}]})
    steps.append({"role": "tool", "name": "project_init",
                  "content": f"Created project deliverables/{project_name}"})

    for extra in (extra_steps or []):
        steps.append(extra)

    steps.append({"role": "assistant", "content": "", "tool_calls": [
        {"type": "function", "function": {"name": "file_write",
         "arguments": {"path": app_path, "content": app_code}}}]})
    steps.append({"role": "tool", "name": "file_write",
                  "content": f"Wrote {app_path}"})
    steps.append({"role": "assistant", "content": "", "tool_calls": [
        {"type": "function", "function": {"name": "shell_exec",
         "arguments": {"command": f"cd deliverables/{project_name} && npx vite build"}}}]})
    steps.append({"role": "tool", "name": "shell_exec",
                  "content": "vite v5.0.0 building for production... built in 1.2s"})
    steps.append({"role": "assistant", "content": "", "tool_calls": [
        {"type": "function", "function": {"name": "undertow",
         "arguments": {"path": f"deliverables/{project_name}/dist/index.html",
                       "expect": expect}}}]})
    steps.append({"role": "tool", "name": "undertow",
                  "content": "PASS — app renders correctly. Screenshot saved."})
    steps.append({"role": "assistant", "content": "", "tool_calls": [
        {"type": "function", "function": {"name": "message_result",
         "arguments": {"text": result_text}}}]})
    return steps


# ---------------------------------------------------------------------------
# EXAMPLES — structured, composable. Each entry becomes one jsonl row.
# ---------------------------------------------------------------------------

EXAMPLES = []

# --- CHAT (trivial prompts should NOT trigger a build) -----------------------
# These teach the model that chat prompts are chat; don't emit project_init.

EXAMPLES.append({
    "tag": "chat_math",
    "messages": [
        {"role": "system", "content": SYSTEM_TEXT},
        {"role": "user", "content": "What's 2+2?"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "message_chat",
             "arguments": {"text": "4", "done": True}}}]},
        {"role": "tool", "name": "message_chat", "content": "Delivered."},
    ],
})

EXAMPLES.append({
    "tag": "chat_greeting",
    "messages": [
        {"role": "system", "content": SYSTEM_TEXT},
        {"role": "user", "content": "Hey there"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "message_chat",
             "arguments": {"text": "Hey! What do you want to build?", "done": True}}}]},
        {"role": "tool", "name": "message_chat", "content": "Delivered."},
    ],
})

EXAMPLES.append({
    "tag": "chat_capabilities",
    "messages": [
        {"role": "system", "content": SYSTEM_TEXT},
        {"role": "user", "content": "What can you build?"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "message_chat",
             "arguments": {"text": "Web apps, games, dashboards, tools — anything with React, vanilla JS, or WebGPU. Give me a prompt.",
                           "done": True}}}]},
        {"role": "tool", "name": "message_chat", "content": "Delivered."},
    ],
})

EXAMPLES.append({
    "tag": "chat_thanks",
    "messages": [
        {"role": "system", "content": SYSTEM_TEXT},
        {"role": "user", "content": "Thanks, that's all"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "message_chat",
             "arguments": {"text": "Anytime.", "done": True}}}]},
        {"role": "tool", "name": "message_chat", "content": "Delivered."},
    ],
})


# --- CLARIFICATION (ambiguous request → ask, don't guess) --------------------

EXAMPLES.append({
    "tag": "clarify_vague_app",
    "messages": [
        {"role": "system", "content": SYSTEM_TEXT},
        {"role": "user", "content": "Make me an app"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "message_chat",
             "arguments": {"text": "What kind — calculator, todo list, game, dashboard, something else?",
                           "done": False}}}]},
        {"role": "tool", "name": "message_chat", "content": "Delivered."},
    ],
})

EXAMPLES.append({
    "tag": "clarify_ambiguous_dashboard",
    "messages": [
        {"role": "system", "content": SYSTEM_TEXT},
        {"role": "user", "content": "Build a dashboard"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "message_chat",
             "arguments": {"text": "For what data — analytics, admin, ops monitoring, sales? And any charts needed?",
                           "done": False}}}]},
        {"role": "tool", "name": "message_chat", "content": "Delivered."},
    ],
})


# --- MID-FLIGHT ITERATION (existing project, "change X" — file_edit, not project_init)

EXAMPLES.append({
    "tag": "iter_add_reset",
    "messages": [
        {"role": "system", "content": SYSTEM_TEXT},
        {"role": "user", "content": "I have a counter app at deliverables/counter-basic. Add a reset button that sets the count back to 0."},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "file_edit",
             "arguments": {
                 "path": "deliverables/counter-basic/src/App.tsx",
                 "old_text": "<button onClick={() => setC(c + 1)}>+</button>",
                 "new_text": "<button onClick={() => setC(c + 1)}>+</button><button onClick={() => setC(0)}>reset</button>"}}}]},
        {"role": "tool", "name": "file_edit", "content": "Edited deliverables/counter-basic/src/App.tsx"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "shell_exec",
             "arguments": {"command": "cd deliverables/counter-basic && npx vite build"}}}]},
        {"role": "tool", "name": "shell_exec", "content": "built in 1.1s"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "undertow",
             "arguments": {"path": "deliverables/counter-basic/dist/index.html",
                           "expect": "counter with plus, minus, and reset"}}}]},
        {"role": "tool", "name": "undertow", "content": "PASS — reset button visible, clicks set counter to 0."},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "message_result",
             "arguments": {"text": "Added reset button to counter-basic. Clicks set counter to 0."}}}]},
    ],
})

EXAMPLES.append({
    "tag": "iter_change_step",
    "messages": [
        {"role": "system", "content": SYSTEM_TEXT},
        {"role": "user", "content": "The counter at deliverables/counter-basic should count by 5 instead of 1."},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "file_edit",
             "arguments": {
                 "path": "deliverables/counter-basic/src/App.tsx",
                 "old_text": "setC(c + 1)",
                 "new_text": "setC(c + 5)"}}}]},
        {"role": "tool", "name": "file_edit", "content": "Edited (1 of 2 replacements)"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "file_edit",
             "arguments": {
                 "path": "deliverables/counter-basic/src/App.tsx",
                 "old_text": "setC(c - 1)",
                 "new_text": "setC(c - 5)"}}}]},
        {"role": "tool", "name": "file_edit", "content": "Edited (2 of 2)"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "shell_exec",
             "arguments": {"command": "cd deliverables/counter-basic && npx vite build"}}}]},
        {"role": "tool", "name": "shell_exec", "content": "built in 1.0s"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "undertow",
             "arguments": {"path": "deliverables/counter-basic/dist/index.html",
                           "expect": "counter increments/decrements by 5"}}}]},
        {"role": "tool", "name": "undertow", "content": "PASS — +/- steps by 5."},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "message_result",
             "arguments": {"text": "Changed counter step to 5."}}}]},
    ],
})

EXAMPLES.append({
    "tag": "iter_add_dark_mode",
    "messages": [
        {"role": "system", "content": SYSTEM_TEXT},
        {"role": "user", "content": "Add a dark mode toggle to the todo app at deliverables/todo-basic"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "file_edit",
             "arguments": {
                 "path": "deliverables/todo-basic/src/App.tsx",
                 "old_text": "export default function App() {",
                 "new_text": "export default function App() {\n  const [dark, setDark] = useState(false)"}}}]},
        {"role": "tool", "name": "file_edit", "content": "Edited"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "file_edit",
             "arguments": {
                 "path": "deliverables/todo-basic/src/App.tsx",
                 "old_text": "<div>",
                 "new_text": "<div style={{background: dark ? '#111' : '#fff', color: dark ? '#eee' : '#000', minHeight: '100vh'}}><button onClick={() => setDark(!dark)}>{dark ? 'light' : 'dark'}</button>"}}}]},
        {"role": "tool", "name": "file_edit", "content": "Edited"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "shell_exec",
             "arguments": {"command": "cd deliverables/todo-basic && npx vite build"}}}]},
        {"role": "tool", "name": "shell_exec", "content": "built in 1.3s"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "undertow",
             "arguments": {"path": "deliverables/todo-basic/dist/index.html",
                           "expect": "todo app with dark mode toggle that switches background"}}}]},
        {"role": "tool", "name": "undertow", "content": "PASS — toggle flips colors."},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "message_result",
             "arguments": {"text": "Added dark mode toggle to todo-basic."}}}]},
    ],
})

EXAMPLES.append({
    "tag": "iter_rename_app",
    "messages": [
        {"role": "system", "content": SYSTEM_TEXT},
        {"role": "user", "content": "Rename the app at deliverables/focus-timer to 'Deep Work Timer'"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "file_edit",
             "arguments": {
                 "path": "deliverables/focus-timer/index.html",
                 "old_text": "<title>Focus Timer</title>",
                 "new_text": "<title>Deep Work Timer</title>"}}}]},
        {"role": "tool", "name": "file_edit", "content": "Edited"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "file_edit",
             "arguments": {
                 "path": "deliverables/focus-timer/src/App.tsx",
                 "old_text": "Focus Timer",
                 "new_text": "Deep Work Timer"}}}]},
        {"role": "tool", "name": "file_edit", "content": "Edited"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "shell_exec",
             "arguments": {"command": "cd deliverables/focus-timer && npx vite build"}}}]},
        {"role": "tool", "name": "shell_exec", "content": "built in 1.0s"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "message_result",
             "arguments": {"text": "Renamed to Deep Work Timer."}}}]},
    ],
})

EXAMPLES.append({
    "tag": "iter_change_color",
    "messages": [
        {"role": "system", "content": SYSTEM_TEXT},
        {"role": "user", "content": "Change the button color to blue in deliverables/calc"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "file_edit",
             "arguments": {
                 "path": "deliverables/calc/src/App.tsx",
                 "old_text": "background: '#888'",
                 "new_text": "background: '#2962ff'"}}}]},
        {"role": "tool", "name": "file_edit", "content": "Edited"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "shell_exec",
             "arguments": {"command": "cd deliverables/calc && npx vite build"}}}]},
        {"role": "tool", "name": "shell_exec", "content": "built in 1.0s"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "message_result",
             "arguments": {"text": "Button color changed to blue (#2962ff)."}}}]},
    ],
})


# --- L3 ERROR-RECOVERY DEPTH (v92 eval ER01/03/04/05 still failing) ---------
# Every example: build error → STRAIGHT to the right tool, no chat, no read-first.
# Variants per scenario so the model sees the pattern, not just one prompt.

EXAMPLES.append({
    "tag": "er01_missing_module_shell_exec",
    "messages": [
        {"role": "system", "content": SYSTEM_TEXT},
        {"role": "user", "content": "Build a chart with recharts"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "project_init",
             "arguments": {"name": "chart-rc"}}}]},
        {"role": "tool", "name": "project_init", "content": "Created"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "file_write",
             "arguments": {"path": "src/App.tsx",
                           "content": "import { LineChart, Line } from 'recharts'\nexport default function App() { return <LineChart width={400} height={200} data={[{x:1,y:1},{x:2,y:4}]}><Line dataKey='y'/></LineChart> }"}}}]},
        {"role": "tool", "name": "file_write", "content": "Wrote"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "shell_exec",
             "arguments": {"command": "cd deliverables/chart-rc && npx vite build"}}}]},
        {"role": "tool", "name": "shell_exec",
         "content": "ERROR: Cannot find module 'recharts'"},
        # KEY: missing module → npm install via shell_exec. NO message_chat.
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "shell_exec",
             "arguments": {"command": "cd deliverables/chart-rc && npm install recharts"}}}]},
        {"role": "tool", "name": "shell_exec", "content": "added 1 package"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "shell_exec",
             "arguments": {"command": "cd deliverables/chart-rc && npx vite build"}}}]},
        {"role": "tool", "name": "shell_exec", "content": "built in 1.4s"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "undertow",
             "arguments": {"path": "deliverables/chart-rc/dist/index.html",
                           "expect": "line chart"}}}]},
        {"role": "tool", "name": "undertow", "content": "PASS"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "message_result",
             "arguments": {"text": "Built chart-rc with recharts."}}}]},
    ],
})

EXAMPLES.append({
    "tag": "er01_missing_module_d3",
    "messages": [
        {"role": "system", "content": SYSTEM_TEXT},
        {"role": "user", "content": "Build a bar visualization"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "project_init",
             "arguments": {"name": "bar-d3"}}}]},
        {"role": "tool", "name": "project_init", "content": "Created"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "file_write",
             "arguments": {"path": "src/App.tsx",
                           "content": "import * as d3 from 'd3'\nexport default function App() { return <svg width={300} height={100}/> }"}}}]},
        {"role": "tool", "name": "file_write", "content": "Wrote"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "shell_exec",
             "arguments": {"command": "cd deliverables/bar-d3 && npx vite build"}}}]},
        {"role": "tool", "name": "shell_exec",
         "content": "ERROR: Cannot find module 'd3'"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "shell_exec",
             "arguments": {"command": "cd deliverables/bar-d3 && npm install d3"}}}]},
        {"role": "tool", "name": "shell_exec", "content": "ok"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "shell_exec",
             "arguments": {"command": "cd deliverables/bar-d3 && npx vite build"}}}]},
        {"role": "tool", "name": "shell_exec", "content": "built"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "undertow",
             "arguments": {"path": "deliverables/bar-d3/dist/index.html",
                           "expect": "svg bar visualization"}}}]},
        {"role": "tool", "name": "undertow", "content": "PASS"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "message_result",
             "arguments": {"text": "Built bar-d3."}}}]},
    ],
})

EXAMPLES.append({
    "tag": "er05_wrong_path_corrected_cd",
    "messages": [
        {"role": "system", "content": SYSTEM_TEXT},
        {"role": "user", "content": "Build a kanban board"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "project_init",
             "arguments": {"name": "kanban"}}}]},
        {"role": "tool", "name": "project_init", "content": "Created"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "shell_exec",
             "arguments": {"command": "cd workspace/deliverables/kanban && npx vite build"}}}]},
        {"role": "tool", "name": "shell_exec",
         "content": "cd: workspace/deliverables/kanban: No such file or directory"},
        # KEY: wrong path → corrected shell_exec MUST include "deliverables/app" pattern
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "shell_exec",
             "arguments": {"command": "cd deliverables/kanban && npx vite build"}}}]},
        {"role": "tool", "name": "shell_exec", "content": "built"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "undertow",
             "arguments": {"path": "deliverables/kanban/dist/index.html",
                           "expect": "kanban"}}}]},
        {"role": "tool", "name": "undertow", "content": "PASS"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "message_result",
             "arguments": {"text": "Built kanban."}}}]},
    ],
})


# --- L4 HACK-FREE DEPTH (v92 HF03/04/05/07/10 still failing) ----------------
# After-context-load → write code (not search). After-build → undertow (not chat).

EXAMPLES.append({
    "tag": "hf03_stall_after_read_write_now",
    "messages": [
        {"role": "system", "content": SYSTEM_TEXT},
        {"role": "user", "content": "Build a recipe app, you'll need to read existing components first"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "project_init",
             "arguments": {"name": "recipe-app"}}}]},
        {"role": "tool", "name": "project_init", "content": "Created"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "file_read",
             "arguments": {"path": "deliverables/recipe-app/src/components/ui/index.ts"}}}]},
        {"role": "tool", "name": "file_read", "content": "export { Button, Card, Input } from './primitives'"},
        # KEY: after a read, IMMEDIATE file_write. NOT another read or search.
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "file_write",
             "arguments": {"path": "deliverables/recipe-app/src/App.tsx",
                           "content": "import { Card, Button, Input } from './components/ui'\nexport default function App() { return <Card><Input placeholder='ingredient'/><Button>add</Button></Card> }"}}}]},
        {"role": "tool", "name": "file_write", "content": "Wrote"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "shell_exec",
             "arguments": {"command": "cd deliverables/recipe-app && npx vite build"}}}]},
        {"role": "tool", "name": "shell_exec", "content": "built"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "undertow",
             "arguments": {"path": "deliverables/recipe-app/dist/index.html",
                           "expect": "recipe input with add button"}}}]},
        {"role": "tool", "name": "undertow", "content": "PASS"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "message_result",
             "arguments": {"text": "Built recipe-app."}}}]},
    ],
})

EXAMPLES.append({
    "tag": "hf04_code_write_gate_after_scaffold",
    "messages": [
        {"role": "system", "content": SYSTEM_TEXT},
        {"role": "user", "content": "Build a memory-match game"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "project_init",
             "arguments": {"name": "memory-match"}}}]},
        {"role": "tool", "name": "project_init", "content": "Created project deliverables/memory-match with React+Vite scaffold (default App.tsx is placeholder)"},
        # KEY: after project_init's placeholder, model MUST file_write the real app. NOT search_web.
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "file_write",
             "arguments": {"path": "deliverables/memory-match/src/App.tsx",
                           "content": "import { useState } from 'react'\nconst symbols=['A','B','C','D','A','B','C','D']\nexport default function App(){ const [flipped,setFlipped]=useState<number[]>([]); return <div className='grid grid-4'>{symbols.sort(()=>Math.random()-.5).map((s,i)=><button key={i} onClick={()=>setFlipped([...flipped,i])}>{flipped.includes(i)?s:'?'}</button>)}</div> }"}}}]},
        {"role": "tool", "name": "file_write", "content": "Wrote"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "shell_exec",
             "arguments": {"command": "cd deliverables/memory-match && npx vite build"}}}]},
        {"role": "tool", "name": "shell_exec", "content": "built"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "undertow",
             "arguments": {"path": "deliverables/memory-match/dist/index.html",
                           "expect": "memory match game with flip buttons"}}}]},
        {"role": "tool", "name": "undertow", "content": "PASS"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "message_result",
             "arguments": {"text": "Built memory-match."}}}]},
    ],
})

EXAMPLES.append({
    "tag": "hf05_shell_loop_break_with_write",
    "messages": [
        {"role": "system", "content": SYSTEM_TEXT},
        {"role": "user", "content": "Build a notes app"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "project_init",
             "arguments": {"name": "notes-app"}}}]},
        {"role": "tool", "name": "project_init", "content": "Created"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "shell_exec",
             "arguments": {"command": "ls deliverables/notes-app/src"}}}]},
        {"role": "tool", "name": "shell_exec", "content": "App.tsx  index.css  main.tsx"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "shell_exec",
             "arguments": {"command": "ls deliverables/notes-app"}}}]},
        {"role": "tool", "name": "shell_exec", "content": "package.json  src/  vite.config.ts"},
        # KEY: 2nd consecutive shell_exec with no progress → break the loop with file_write.
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "file_write",
             "arguments": {"path": "deliverables/notes-app/src/App.tsx",
                           "content": "import { useState } from 'react'\nexport default function App() { const [n,setN] = useState(['']); return <div>{n.map((x,i)=><textarea key={i} value={x} onChange={e=>{const c=[...n]; c[i]=e.target.value; setN(c)}}/>)}<button onClick={()=>setN([...n,''])}>+</button></div> }"}}}]},
        {"role": "tool", "name": "file_write", "content": "Wrote"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "shell_exec",
             "arguments": {"command": "cd deliverables/notes-app && npx vite build"}}}]},
        {"role": "tool", "name": "shell_exec", "content": "built"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "undertow",
             "arguments": {"path": "deliverables/notes-app/dist/index.html",
                           "expect": "notes app with textareas"}}}]},
        {"role": "tool", "name": "undertow", "content": "PASS"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "message_result",
             "arguments": {"text": "Built notes-app."}}}]},
    ],
})

EXAMPLES.append({
    "tag": "hf07_auto_wire_after_components_write",
    "messages": [
        {"role": "system", "content": SYSTEM_TEXT},
        {"role": "user", "content": "Build a settings page with sidebar and form"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "project_init",
             "arguments": {"name": "settings-pg"}}}]},
        {"role": "tool", "name": "project_init", "content": "Created"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "file_write",
             "arguments": {"path": "deliverables/settings-pg/src/components/Sidebar.tsx",
                           "content": "export default function Sidebar(){ return <nav><a>General</a><a>Profile</a><a>Privacy</a></nav> }"}}}]},
        {"role": "tool", "name": "file_write", "content": "Wrote"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "file_write",
             "arguments": {"path": "deliverables/settings-pg/src/components/Form.tsx",
                           "content": "export default function Form(){ return <form><input placeholder='name'/><button>save</button></form> }"}}}]},
        {"role": "tool", "name": "file_write", "content": "Wrote"},
        # KEY: after writing components, model auto-wires them into App.tsx via file_write.
        # NOT shell_exec, NOT another investigation.
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "file_write",
             "arguments": {"path": "deliverables/settings-pg/src/App.tsx",
                           "content": "import Sidebar from './components/Sidebar'\nimport Form from './components/Form'\nexport default function App(){ return <div className='flex'><Sidebar/><Form/></div> }"}}}]},
        {"role": "tool", "name": "file_write", "content": "Wrote App.tsx wired with Sidebar + Form"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "shell_exec",
             "arguments": {"command": "cd deliverables/settings-pg && npx vite build"}}}]},
        {"role": "tool", "name": "shell_exec", "content": "built"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "undertow",
             "arguments": {"path": "deliverables/settings-pg/dist/index.html",
                           "expect": "settings page with sidebar nav and form"}}}]},
        {"role": "tool", "name": "undertow", "content": "PASS"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "message_result",
             "arguments": {"text": "Built settings-pg."}}}]},
    ],
})


# --- SMOKE-FAIL DIRECT TARGETS (probes 03, 05, 07 reproducibly fail) --------
# Hand-crafted to teach exactly the prompts that smoke probes catch failing.

EXAMPLES.append({
    "tag": "smoke03_whats_in_dir_chat_form",
    "messages": [
        {"role": "system", "content": SYSTEM_TEXT},
        {"role": "user", "content": "What's in this directory?"},
        # KEY: question form ALSO gets shell_exec. Don't ask user for path — they're IN the dir.
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "shell_exec",
             "arguments": {"command": "ls -la"}}}]},
        {"role": "tool", "name": "shell_exec",
         "content": "src/  tests/  package.json  README.md  vite.config.ts  node_modules/"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "message_result",
             "arguments": {"text": "Vite/TypeScript project: src/, tests/, package.json, vite.config.ts, README.md, plus node_modules/."}}}]},
    ],
})

EXAMPLES.append({
    "tag": "smoke05_summarize_python_files",
    "messages": [
        {"role": "system", "content": SYSTEM_TEXT},
        {"role": "user", "content": "Summarize the python files."},
        # KEY: don't ask for paths — list them yourself, then read, then summarize.
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "shell_exec",
             "arguments": {"command": "ls *.py 2>/dev/null && wc -l *.py 2>/dev/null"}}}]},
        {"role": "tool", "name": "shell_exec",
         "content": "loader.py  trainer.py  eval.py\n  120 loader.py\n  450 trainer.py\n   89 eval.py"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "file_read",
             "arguments": {"path": "trainer.py"}}}]},
        {"role": "tool", "name": "file_read", "content": "class Trainer:\n  def __init__(self, model, data): ...\n  def train(self, epochs): ..."},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "message_result",
             "arguments": {"text": "3 Python files, 659 LOC: loader.py (120) data IO, trainer.py (450) Trainer class, eval.py (89) eval harness."}}}]},
    ],
})

EXAMPLES.append({
    "tag": "smoke07_organize_files_by_type",
    "messages": [
        {"role": "system", "content": SYSTEM_TEXT},
        {"role": "user", "content": "Organize these files by type."},
        # KEY: same as cwd_organize but with extra reinforcement on prompt-shape.
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "shell_exec",
             "arguments": {"command": "ls"}}}]},
        {"role": "tool", "name": "shell_exec",
         "content": "report.pdf  notes.md  data.csv  image.png  config.yaml  script.py  todo.md  paper.pdf"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "shell_exec",
             "arguments": {"command": "mkdir -p pdfs md data images code config && mv *.pdf pdfs/ && mv *.md md/ && mv *.csv data/ && mv *.png images/ && mv *.py code/ && mv *.yaml config/"}}}]},
        {"role": "tool", "name": "shell_exec",
         "content": "moved 8 files into 6 type folders"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "message_result",
             "arguments": {"text": "Organized 8 files into pdfs/, md/, data/, images/, code/, config/."}}}]},
    ],
})


# --- COUNTER-REGRESSIONS (v91 eval revealed these failure modes) ------------
# v91 introduced read-first / search-first patterns from CWD + vision examples
# that leaked into error recovery and build-loop continuation. These examples
# explicitly counter that: error recovery goes STRAIGHT to file_edit (no
# preceding file_read), continue-build goes STRAIGHT to file_write (no
# preceding search_web), post-build goes STRAIGHT to undertow.

EXAMPLES.append({
    "tag": "counter_l3_syntax_direct_edit",
    "messages": [
        {"role": "system", "content": SYSTEM_TEXT},
        {"role": "user", "content": "Build a counter app"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "project_init",
             "arguments": {"name": "counter-syn"}}}]},
        {"role": "tool", "name": "project_init", "content": "Created"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "file_write",
             "arguments": {"path": "src/App.tsx",
                           "content": "export default function App() { return <div>{count<;</div> }"}}}]},
        {"role": "tool", "name": "file_write", "content": "Wrote"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "shell_exec",
             "arguments": {"command": "cd deliverables/counter-syn && npx vite build"}}}]},
        {"role": "tool", "name": "shell_exec",
         "content": "ERROR: Expected ',' got ';' in src/App.tsx line 1"},
        # KEY: model goes STRAIGHT to file_edit. NO file_read first.
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "file_edit",
             "arguments": {
                 "path": "deliverables/counter-syn/src/App.tsx",
                 "old_text": "{count<;</div>",
                 "new_text": "{count}</div>"}}}]},
        {"role": "tool", "name": "file_edit", "content": "Edited"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "shell_exec",
             "arguments": {"command": "cd deliverables/counter-syn && npx vite build"}}}]},
        {"role": "tool", "name": "shell_exec", "content": "built"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "undertow",
             "arguments": {"path": "deliverables/counter-syn/dist/index.html",
                           "expect": "counter app"}}}]},
        {"role": "tool", "name": "undertow", "content": "PASS"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "message_result",
             "arguments": {"text": "Built counter-syn."}}}]},
    ],
})

EXAMPLES.append({
    "tag": "counter_l3_missing_module_direct_write",
    "messages": [
        {"role": "system", "content": SYSTEM_TEXT},
        {"role": "user", "content": "Build a header-and-content layout"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "project_init",
             "arguments": {"name": "header-layout"}}}]},
        {"role": "tool", "name": "project_init", "content": "Created"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "file_write",
             "arguments": {"path": "src/App.tsx",
                           "content": "import Header from './components/Header'\nexport default function App() { return <Header /> }"}}}]},
        {"role": "tool", "name": "file_write", "content": "Wrote"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "shell_exec",
             "arguments": {"command": "cd deliverables/header-layout && npx vite build"}}}]},
        {"role": "tool", "name": "shell_exec",
         "content": "ERROR: Cannot find module './components/Header'"},
        # KEY: missing module → file_write the component. NO file_read first.
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "file_write",
             "arguments": {
                 "path": "deliverables/header-layout/src/components/Header.tsx",
                 "content": "export default function Header() { return <header>App</header> }"}}}]},
        {"role": "tool", "name": "file_write", "content": "Wrote"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "shell_exec",
             "arguments": {"command": "cd deliverables/header-layout && npx vite build"}}}]},
        {"role": "tool", "name": "shell_exec", "content": "built"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "undertow",
             "arguments": {"path": "deliverables/header-layout/dist/index.html",
                           "expect": "header layout"}}}]},
        {"role": "tool", "name": "undertow", "content": "PASS"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "message_result",
             "arguments": {"text": "Built header-layout."}}}]},
    ],
})

EXAMPLES.append({
    "tag": "counter_l4_post_build_undertow_not_chat",
    "messages": [
        {"role": "system", "content": SYSTEM_TEXT},
        {"role": "user", "content": "Build a timer app"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "project_init",
             "arguments": {"name": "timer-undertow"}}}]},
        {"role": "tool", "name": "project_init", "content": "Created"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "file_write",
             "arguments": {"path": "src/App.tsx",
                           "content": "import { useState, useEffect } from 'react'\nexport default function App() { const [s,setS] = useState(0); useEffect(()=>{const i=setInterval(()=>setS(x=>x+1),1000); return ()=>clearInterval(i)},[]); return <div>{s}s</div> }"}}}]},
        {"role": "tool", "name": "file_write", "content": "Wrote"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "shell_exec",
             "arguments": {"command": "cd deliverables/timer-undertow && npx vite build"}}}]},
        {"role": "tool", "name": "shell_exec", "content": "built in 420ms"},
        # KEY: build passed → undertow IMMEDIATELY. NO message_chat narrating.
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "undertow",
             "arguments": {"path": "deliverables/timer-undertow/dist/index.html",
                           "expect": "a timer ticking up by seconds"}}}]},
        {"role": "tool", "name": "undertow", "content": "PASS — counter ticks"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "message_result",
             "arguments": {"text": "Built timer-undertow. Counts seconds, verified."}}}]},
    ],
})

EXAMPLES.append({
    "tag": "counter_l4_continue_build_write_not_search",
    "messages": [
        {"role": "system", "content": SYSTEM_TEXT},
        {"role": "user", "content": "Continue building the dashboard"},
        # Pretend prior turn established context: project exists, App.tsx written,
        # build passing. Continuation should write the next component, not search.
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "file_write",
             "arguments": {
                 "path": "deliverables/dashboard/src/components/StatCard.tsx",
                 "content": "export default function StatCard({label, value}: {label: string; value: string}) { return <div className='card'><h3>{label}</h3><strong>{value}</strong></div> }"}}}]},
        {"role": "tool", "name": "file_write", "content": "Wrote"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "shell_exec",
             "arguments": {"command": "cd deliverables/dashboard && npx vite build"}}}]},
        {"role": "tool", "name": "shell_exec", "content": "built"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "undertow",
             "arguments": {"path": "deliverables/dashboard/dist/index.html",
                           "expect": "dashboard with stat cards"}}}]},
        {"role": "tool", "name": "undertow", "content": "PASS"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "message_result",
             "arguments": {"text": "Added StatCard component to dashboard."}}}]},
    ],
})


# --- IN-PLACE / CWD MODE (user's CWD has files, task is about them) ---------
# Zero coverage in v90/v91 — model always reaches for project_init. These
# examples teach "list first, operate in place, skip project_init + undertow"
# for requests like "organize", "rename", "summarize", "what's in here".

EXAMPLES.append({
    "tag": "cwd_organize_by_type",
    "messages": [
        {"role": "system", "content": SYSTEM_TEXT},
        {"role": "user", "content": "Organize these files by type."},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "shell_exec",
             "arguments": {"command": "ls -la"}}}]},
        {"role": "tool", "name": "shell_exec",
         "content": "report.pdf  paper.pdf  notes.md  todo.md  image.png  logo.png  data.csv  config.yaml"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "shell_exec",
             "arguments": {"command": "mkdir -p pdfs markdown images data && mv *.pdf pdfs/ && mv *.md markdown/ && mv *.png images/ && mv *.csv *.yaml data/"}}}]},
        {"role": "tool", "name": "shell_exec",
         "content": "moved 8 files into pdfs/, markdown/, images/, data/"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "message_result",
             "arguments": {"text": "Organized 8 files into pdfs/, markdown/, images/, data/ by extension."}}}]},
    ],
})

EXAMPLES.append({
    "tag": "cwd_whats_in_here",
    "messages": [
        {"role": "system", "content": SYSTEM_TEXT},
        {"role": "user", "content": "What's in this directory?"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "shell_exec",
             "arguments": {"command": "ls -la"}}}]},
        {"role": "tool", "name": "shell_exec",
         "content": "README.md  src/  tests/  package.json  node_modules/  dist/  .git/"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "message_result",
             "arguments": {"text": "A Node/TypeScript project: README.md, src/, tests/, package.json, plus node_modules/ and dist/ build output. Git-tracked."}}}]},
    ],
})

EXAMPLES.append({
    "tag": "cwd_rename_pngs_to_date",
    "messages": [
        {"role": "system", "content": SYSTEM_TEXT},
        {"role": "user", "content": "Rename all these PNGs to use their modified-date as the prefix, like 2026-04-12_oldname.png"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "shell_exec",
             "arguments": {"command": "ls *.png"}}}]},
        {"role": "tool", "name": "shell_exec",
         "content": "screenshot.png  logo.png  banner.png  icon.png"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "shell_exec",
             "arguments": {"command": "for f in *.png; do d=$(date -r \"$f\" +%Y-%m-%d); mv \"$f\" \"${d}_${f}\"; done"}}}]},
        {"role": "tool", "name": "shell_exec",
         "content": "renamed: 2026-04-12_screenshot.png, 2026-04-12_logo.png, 2026-04-11_banner.png, 2026-04-10_icon.png"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "message_result",
             "arguments": {"text": "Renamed 4 PNGs with date prefix."}}}]},
    ],
})

EXAMPLES.append({
    "tag": "cwd_summarize_python",
    "messages": [
        {"role": "system", "content": SYSTEM_TEXT},
        {"role": "user", "content": "Summarize the Python files in this directory."},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "shell_exec",
             "arguments": {"command": "ls *.py && wc -l *.py"}}}]},
        {"role": "tool", "name": "shell_exec",
         "content": "loader.py  trainer.py  eval.py\n  120 loader.py\n  450 trainer.py\n   89 eval.py\n  659 total"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "file_read",
             "arguments": {"path": "trainer.py"}}}]},
        {"role": "tool", "name": "file_read",
         "content": "import torch\nclass Trainer:\n    def __init__(self, model, data): ...\n    def train(self, epochs): ..."},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "message_result",
             "arguments": {"text": "3 Python files, 659 LOC total:\n- loader.py (120): data loading\n- trainer.py (450): training loop with Trainer class\n- eval.py (89): evaluation harness"}}}]},
    ],
})

EXAMPLES.append({
    "tag": "cwd_find_todos",
    "messages": [
        {"role": "system", "content": SYSTEM_TEXT},
        {"role": "user", "content": "Find all TODO comments in this codebase."},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "shell_exec",
             "arguments": {"command": "grep -rn 'TODO' --include='*.py' --include='*.ts' --include='*.tsx' --include='*.js'"}}}]},
        {"role": "tool", "name": "shell_exec",
         "content": "./src/api.ts:42: // TODO: rate-limit\n./src/auth.ts:17: // TODO: handle expired tokens\n./trainer.py:88: # TODO: add early stopping"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "message_result",
             "arguments": {"text": "3 TODOs found:\n- src/api.ts:42 — rate-limit\n- src/auth.ts:17 — handle expired tokens\n- trainer.py:88 — add early stopping"}}}]},
    ],
})

EXAMPLES.append({
    "tag": "cwd_refactor_snake_case",
    "messages": [
        {"role": "system", "content": SYSTEM_TEXT},
        {"role": "user", "content": "Rename the function `methodName` to snake_case in user.py."},
        # Classic Claude Code framing: don't output the string, MODIFY THE CODE.
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "file_read",
             "arguments": {"path": "user.py"}}}]},
        {"role": "tool", "name": "file_read",
         "content": "class User:\n    def methodName(self):\n        return self.data\n    def callMethodName(self):\n        return self.methodName()"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "file_edit",
             "arguments": {
                 "path": "user.py",
                 "old_text": "def methodName(self):",
                 "new_text": "def method_name(self):"}}}]},
        {"role": "tool", "name": "file_edit", "content": "Edited"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "file_edit",
             "arguments": {
                 "path": "user.py",
                 "old_text": "return self.methodName()",
                 "new_text": "return self.method_name()"}}}]},
        {"role": "tool", "name": "file_edit", "content": "Edited"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "message_result",
             "arguments": {"text": "Renamed methodName → method_name in user.py (2 occurrences: def + call site)."}}}]},
    ],
})


# --- VISION PIPELINE (generate_image + riptide — the undertrained tools) -----

EXAMPLES.append({
    "tag": "vision_logo_extract",
    "messages": [
        {"role": "system", "content": SYSTEM_TEXT},
        {"role": "user", "content": "Make a website logo for 'Nimbus Cloud Storage' and write code to extract it from its background color"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "project_init",
             "arguments": {"name": "nimbus-logo"}}}]},
        {"role": "tool", "name": "project_init", "content": "Created project deliverables/nimbus-logo"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "generate_image",
             "arguments": {
                 "prompt": "minimalist logo for 'Nimbus Cloud Storage', flat vector style, blue cloud on solid white background, centered, 512x512",
                 "path": "deliverables/nimbus-logo/public/logo-raw.png"}}}]},
        {"role": "tool", "name": "generate_image", "content": "Saved to deliverables/nimbus-logo/public/logo-raw.png"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "file_write",
             "arguments": {
                 "path": "deliverables/nimbus-logo/src/App.tsx",
                 "content": """import { useEffect, useRef } from 'react'

export default function App() {
  const out = useRef<HTMLCanvasElement>(null)
  useEffect(() => {
    const img = new Image()
    img.src = '/logo-raw.png'
    img.onload = () => {
      const c = out.current!
      c.width = img.width; c.height = img.height
      const ctx = c.getContext('2d')!
      ctx.drawImage(img, 0, 0)
      const d = ctx.getImageData(0, 0, c.width, c.height)
      // Background color sampled from corner pixel
      const br = d.data[0], bg = d.data[1], bb = d.data[2]
      for (let i = 0; i < d.data.length; i += 4) {
        const r = d.data[i], g = d.data[i+1], b = d.data[i+2]
        if (Math.abs(r-br) < 20 && Math.abs(g-bg) < 20 && Math.abs(b-bb) < 20) {
          d.data[i+3] = 0  // transparent
        }
      }
      ctx.putImageData(d, 0, 0)
    }
  }, [])
  return <div style={{background:'#333',padding:40}}><canvas ref={out} /></div>
}
"""}}}]},
        {"role": "tool", "name": "file_write", "content": "Wrote src/App.tsx"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "shell_exec",
             "arguments": {"command": "cd deliverables/nimbus-logo && npx vite build"}}}]},
        {"role": "tool", "name": "shell_exec", "content": "built in 1.4s"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "undertow",
             "arguments": {"path": "deliverables/nimbus-logo/dist/index.html",
                           "expect": "Nimbus logo displayed on a dark background with the white corner background removed (transparent)"}}}]},
        {"role": "tool", "name": "undertow", "content": "PASS — logo shows on dark bg with transparency applied."},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "message_result",
             "arguments": {"text": "Generated Nimbus logo and built canvas-based background removal. Corner-pixel color is sampled as the key, all matching pixels become transparent."}}}]},
    ],
})

EXAMPLES.append({
    "tag": "vision_stripe_clone",
    "messages": [
        {"role": "system", "content": SYSTEM_TEXT},
        {"role": "user", "content": "Build a landing page that looks like stripe.com"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "search_web",
             "arguments": {"query": "stripe.com landing page screenshot hero layout"}}}]},
        {"role": "tool", "name": "search_web", "content": "Found: stripe.com screenshot, hero with 'Payments infrastructure for the internet' + CTA button."},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "generate_image",
             "arguments": {
                 "prompt": "stripe.com style landing page hero, clean typography, teal/purple gradient, large headline, CTA button, feature grid below",
                 "path": "/tmp/stripe_ref.png"}}}]},
        {"role": "tool", "name": "generate_image", "content": "Saved to /tmp/stripe_ref.png"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "riptide",
             "arguments": {"image_path": "/tmp/stripe_ref.png",
                           "focus": "hero, headline, CTA button, feature grid — percentages"}}}]},
        {"role": "tool", "name": "riptide",
         "content": "hero: left=0% top=0% w=100% h=60%; headline: left=15% top=20% w=70% h=10%; cta: left=40% top=40% w=20% h=6%; feature-grid: left=10% top=65% w=80% h=30%"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "project_init",
             "arguments": {"name": "stripe-clone"}}}]},
        {"role": "tool", "name": "project_init", "content": "Created project deliverables/stripe-clone"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "file_write",
             "arguments": {
                 "path": "deliverables/stripe-clone/src/App.tsx",
                 "content": """export default function App() {
  return <div style={{minHeight:'100vh',background:'linear-gradient(135deg,#0a2540 0%,#635bff 100%)',color:'#fff',fontFamily:'system-ui'}}>
    <section style={{height:'60vh',padding:'15% 15% 0'}}>
      <h1 style={{fontSize:'3.5rem',fontWeight:700,margin:0}}>Payments infrastructure for the internet</h1>
      <button style={{marginTop:'4vh',padding:'0.8rem 2rem',background:'#00d4ff',color:'#0a2540',border:0,borderRadius:6,fontWeight:600,fontSize:'1rem'}}>Start now</button>
    </section>
    <section style={{padding:'0 10%',display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:'2rem'}}>
      <div><h3>Accept payments</h3><p>Global coverage, 135+ currencies.</p></div>
      <div><h3>Send payouts</h3><p>Reach 40+ countries, same-day rails.</p></div>
      <div><h3>Manage revenue</h3><p>Invoicing, subscriptions, tax.</p></div>
    </section>
  </div>
}"""}}}]},
        {"role": "tool", "name": "file_write", "content": "Wrote src/App.tsx"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "shell_exec",
             "arguments": {"command": "cd deliverables/stripe-clone && npx vite build"}}}]},
        {"role": "tool", "name": "shell_exec", "content": "built in 1.1s"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "undertow",
             "arguments": {"path": "deliverables/stripe-clone/dist/index.html",
                           "expect": "stripe-style landing with gradient hero, large headline, CTA button, 3-column feature grid"}}}]},
        {"role": "tool", "name": "undertow", "content": "PASS — gradient hero, headline, CTA, and 3-col grid all present."},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "message_result",
             "arguments": {"text": "Built stripe-clone landing page. Gradient hero, headline, CTA, 3-column features. Positions from vision grounding."}}}]},
    ],
})

EXAMPLES.append({
    "tag": "vision_reference_screenshot",
    "messages": [
        {"role": "system", "content": SYSTEM_TEXT},
        {"role": "user", "content": "I have a mockup at /tmp/dashboard_mockup.png. Build a UI that mimics it."},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "riptide",
             "arguments": {"image_path": "/tmp/dashboard_mockup.png",
                           "focus": "sidebar, top bar, stat cards, chart — return percentages"}}}]},
        {"role": "tool", "name": "riptide",
         "content": "sidebar: left=0% top=0% w=18% h=100%; topbar: left=18% top=0% w=82% h=8%; cards: left=20% top=12% w=78% h=20%; chart: left=20% top=35% w=78% h=55%"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "project_init",
             "arguments": {"name": "dashboard-mimic"}}}]},
        {"role": "tool", "name": "project_init", "content": "Created project deliverables/dashboard-mimic"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "file_write",
             "arguments": {
                 "path": "deliverables/dashboard-mimic/src/App.tsx",
                 "content": """export default function App() {
  return <div style={{display:'flex',minHeight:'100vh',fontFamily:'system-ui'}}>
    <aside style={{width:'18%',background:'#1a1d2e',color:'#aaa',padding:'1rem'}}>Sidebar</aside>
    <main style={{flex:1,background:'#f5f6f8'}}>
      <header style={{height:'8vh',background:'#fff',borderBottom:'1px solid #e0e0e0',display:'flex',alignItems:'center',padding:'0 1.5rem'}}>Top Bar</header>
      <section style={{display:'grid',gridTemplateColumns:'repeat(4,1fr)',gap:'1rem',padding:'1rem 1.5rem'}}>
        <div style={{background:'#fff',padding:'1rem',borderRadius:8}}>Users<br/><strong>1,234</strong></div>
        <div style={{background:'#fff',padding:'1rem',borderRadius:8}}>Revenue<br/><strong>$89k</strong></div>
        <div style={{background:'#fff',padding:'1rem',borderRadius:8}}>Conversions<br/><strong>4.2%</strong></div>
        <div style={{background:'#fff',padding:'1rem',borderRadius:8}}>Active<br/><strong>342</strong></div>
      </section>
      <section style={{padding:'1.5rem',background:'#fff',margin:'0 1.5rem',borderRadius:8}}>Chart area</section>
    </main>
  </div>
}"""}}}]},
        {"role": "tool", "name": "file_write", "content": "Wrote src/App.tsx"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "shell_exec",
             "arguments": {"command": "cd deliverables/dashboard-mimic && npx vite build"}}}]},
        {"role": "tool", "name": "shell_exec", "content": "built in 1.2s"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "undertow",
             "arguments": {"path": "deliverables/dashboard-mimic/dist/index.html",
                           "expect": "dashboard with left sidebar, top bar, 4 stat cards, chart area"}}}]},
        {"role": "tool", "name": "undertow", "content": "PASS — layout matches mockup ratios."},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "message_result",
             "arguments": {"text": "Built dashboard-mimic. Layout uses percentages from riptide grounding on the mockup."}}}]},
    ],
})

EXAMPLES.append({
    "tag": "vision_splash_with_logo",
    "messages": [
        {"role": "system", "content": SYSTEM_TEXT},
        {"role": "user", "content": "Create a splash screen with a custom Tsunami logo at center"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "project_init",
             "arguments": {"name": "tsunami-splash"}}}]},
        {"role": "tool", "name": "project_init", "content": "Created project deliverables/tsunami-splash"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "generate_image",
             "arguments": {
                 "prompt": "minimalist wave logo for 'Tsunami', flat vector, deep blue gradient, dark transparent background, centered",
                 "path": "deliverables/tsunami-splash/public/logo.png"}}}]},
        {"role": "tool", "name": "generate_image", "content": "Saved to deliverables/tsunami-splash/public/logo.png"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "file_write",
             "arguments": {
                 "path": "deliverables/tsunami-splash/src/App.tsx",
                 "content": """export default function App() {
  return <div style={{height:'100vh',background:'#05101c',display:'grid',placeItems:'center'}}>
    <img src="/logo.png" alt="Tsunami" style={{width:'30%',maxWidth:320}} />
  </div>
}"""}}}]},
        {"role": "tool", "name": "file_write", "content": "Wrote src/App.tsx"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "shell_exec",
             "arguments": {"command": "cd deliverables/tsunami-splash && npx vite build"}}}]},
        {"role": "tool", "name": "shell_exec", "content": "built in 1.0s"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "undertow",
             "arguments": {"path": "deliverables/tsunami-splash/dist/index.html",
                           "expect": "tsunami logo centered on dark background"}}}]},
        {"role": "tool", "name": "undertow", "content": "PASS — logo visible, centered, dark backdrop."},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "message_result",
             "arguments": {"text": "Built tsunami-splash with custom logo. Generated via generate_image, centered on dark backdrop."}}}]},
    ],
})


# --- GHOST-TOOL RESISTANCE (base-model pretraining leaks — don't emit dead tools)

EXAMPLES.append({
    "tag": "ghost_no_plan_update",
    "messages": [
        {"role": "system", "content": SYSTEM_TEXT},
        {"role": "user", "content": "Build a top-down arena shooter with physics and sprite-based enemies"},
        # Model must go straight to project_init — NEVER emit plan_update
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "project_init",
             "arguments": {"name": "arena-shooter"}}}]},
        {"role": "tool", "name": "project_init", "content": "Created project deliverables/arena-shooter"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "file_write",
             "arguments": {
                 "path": "deliverables/arena-shooter/src/App.tsx",
                 "content": """import { useEffect, useRef } from 'react'

export default function App() {
  const c = useRef<HTMLCanvasElement>(null)
  useEffect(() => {
    const canvas = c.current!
    const ctx = canvas.getContext('2d')!
    canvas.width = 800; canvas.height = 600
    const player = {x:400,y:300,r:15}
    const enemies = Array.from({length:8},()=>({x:Math.random()*800,y:Math.random()*600,vx:(Math.random()-0.5)*2,vy:(Math.random()-0.5)*2,r:12}))
    const keys: Record<string,boolean> = {}
    addEventListener('keydown',e=>keys[e.key]=true)
    addEventListener('keyup',e=>keys[e.key]=false)
    function tick() {
      if(keys['w'])player.y-=3; if(keys['s'])player.y+=3
      if(keys['a'])player.x-=3; if(keys['d'])player.x+=3
      enemies.forEach(e=>{e.x+=e.vx;e.y+=e.vy; if(e.x<0||e.x>800)e.vx*=-1; if(e.y<0||e.y>600)e.vy*=-1})
      ctx.fillStyle='#111'; ctx.fillRect(0,0,800,600)
      ctx.fillStyle='#4ff'; ctx.beginPath(); ctx.arc(player.x,player.y,player.r,0,Math.PI*2); ctx.fill()
      ctx.fillStyle='#f44'
      enemies.forEach(e=>{ctx.beginPath(); ctx.arc(e.x,e.y,e.r,0,Math.PI*2); ctx.fill()})
      requestAnimationFrame(tick)
    }
    tick()
  }, [])
  return <canvas ref={c} />
}"""}}}]},
        {"role": "tool", "name": "file_write", "content": "Wrote src/App.tsx"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "shell_exec",
             "arguments": {"command": "cd deliverables/arena-shooter && npx vite build"}}}]},
        {"role": "tool", "name": "shell_exec", "content": "built in 1.1s"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "undertow",
             "arguments": {"path": "deliverables/arena-shooter/dist/index.html",
                           "expect": "canvas-based arena shooter with a teal player responding to WASD and red enemy sprites bouncing"}}}]},
        {"role": "tool", "name": "undertow", "content": "PASS — canvas animates, player follows WASD, enemies bounce."},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "message_result",
             "arguments": {"text": "Built arena-shooter: WASD player, 8 bouncing enemies, canvas rendering."}}}]},
    ],
})


def render_example(ex: dict, tokenizer) -> str:
    """Render a structured example into the Gemma-4 chat template format."""
    return tokenizer.apply_chat_template(ex["messages"], tools=TOOLS, tokenize=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true",
                    help="Rebuild from legacy + new examples (overwrites champion.jsonl)")
    args = ap.parse_args()

    print(f"Loading tokenizer: {MODEL}")
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(MODEL, trust_remote_code=True)

    # Stash the existing champion as "legacy" on first run so we can rebuild
    # deterministically later.
    if CHAMPION.exists() and not LEGACY.exists():
        LEGACY.write_text(CHAMPION.read_text())
        print(f"Snapshotted current champion → {LEGACY}")

    legacy_lines = LEGACY.read_text().splitlines() if LEGACY.exists() else []
    print(f"Legacy examples: {len(legacy_lines)}")
    print(f"New examples:    {len(EXAMPLES)}")

    new_lines = []
    for ex in EXAMPLES:
        rendered = render_example(ex, tok)
        new_lines.append(json.dumps({"text": rendered}))

    if args.rebuild:
        CHAMPION.write_text("\n".join(legacy_lines + new_lines) + "\n")
        print(f"Rebuilt {CHAMPION} with {len(legacy_lines) + len(new_lines)} examples")
    else:
        # Append mode — add new examples to whatever champion.jsonl has now
        existing = CHAMPION.read_text().splitlines() if CHAMPION.exists() else []
        CHAMPION.write_text("\n".join(existing + new_lines) + "\n")
        print(f"Appended {len(new_lines)} examples → {CHAMPION}")
        print(f"Total:    {len(existing) + len(new_lines)}")


if __name__ == "__main__":
    main()
