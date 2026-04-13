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
