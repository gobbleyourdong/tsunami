#!/usr/bin/env python3
"""Run the full eval pyramid and produce a single report.

  Layer 1: Format (40 prompts, fake results, ~2 min)
  Layer 2: Scaffold Selection (12 prompts, single turn, ~1 min)
  Layer 3: Error Recovery (6 scenarios, single turn, ~1 min)
  Layer 4: Hack-Free (10 scenarios, single turn, ~1 min)
  Layer 5: Integration (9 prompts, full agent loop, ~30 min)

Usage:
  # Quick (layers 1-4, ~5 min)
  python training/eval.py --endpoint http://localhost:8095 --quick

  # Full (all 5 layers, ~35 min)
  python training/eval.py --endpoint http://localhost:8095

  # Compare to previous run
  python training/eval.py --endpoint http://localhost:8095 --quick --compare workspace/training_data/eval_previous.json
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Fix imports — add training/ to path
sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("eval")


def generate_markdown_report(report, prev, format_detail, scaffold_detail,
                             recovery_detail, hackfree_detail, int_detail):
    """Generate a full markdown eval report."""
    lines = []
    w = lines.append

    ts = report["timestamp"]
    elapsed = report.get("elapsed_s", 0)
    w(f"# Tsunami Eval Report")
    w(f"")
    w(f"**Date**: {ts}  ")
    w(f"**Endpoint**: {report.get('endpoint', 'unknown')}  ")
    w(f"**Elapsed**: {elapsed:.0f}s  ")
    w(f"**Layers**: {', '.join(report.get('layers_run', []))}")
    w(f"")

    # --- SCOREBOARD ---
    w(f"## Scoreboard")
    w(f"")
    w(f"| Layer | Score | Pct | Delta |")
    w(f"|-------|-------|-----|-------|")
    layer_order = ["format", "scaffold", "recovery", "hackfree", "integration"]
    for layer in layer_order:
        if layer not in report:
            continue
        d = report[layer]
        p, t = d["passed"], d["total"]
        delta = ""
        if prev and layer in prev:
            diff = p - prev[layer]["passed"]
            if diff > 0:
                delta = f"+{diff}"
            elif diff < 0:
                delta = str(diff)
            else:
                delta = "="
        w(f"| {layer} | {p}/{t} | {d['pct']} | {delta} |")
    w(f"")

    # --- LAYER 1: FORMAT ---
    if format_detail:
        w(f"## L1: Format")
        w(f"")
        d = report["format"]
        w(f"- **Tool call produced**: {d['passed']}/{d['total']}")
        w(f"- **Valid tool name**: {d['valid_name']}/{d['total']}")
        w(f"- **Correct first tool**: {d['correct_first']}/{d['total']}")
        w(f"")

        # Group by level
        by_level = {}
        for r in format_detail:
            by_level.setdefault(r["level"], []).append(r)

        for level in ["trivial", "easy", "medium", "hard", "extreme"]:
            group = by_level.get(level, [])
            if not group:
                continue
            n = len(group)
            ok = sum(1 for r in group if r["pass"])
            w(f"### {level.upper()} ({ok}/{n})")
            w(f"")
            w(f"| ID | Prompt | Pass | Got | Expected | ms |")
            w(f"|----|--------|------|-----|----------|----|")
            for r in group:
                status = "PASS" if r["pass"] else "FAIL"
                prompt = r["prompt"][:45]
                w(f"| {r['id']} | {prompt} | {status} | {r['tool']} | {r['expected']} | {r['latency_ms']} |")
            w(f"")

        # Failures summary
        fails = [r for r in format_detail if not r["pass"]]
        if fails:
            w(f"### Failures ({len(fails)})")
            w(f"")
            for r in fails:
                w(f"- **{r['id']}** `{r['prompt'][:50]}` — got `{r['tool']}`, expected `{r['expected']}`{' ERROR: ' + r['error'] if r['error'] else ''}")
            w(f"")

    # --- LAYER 2: SCAFFOLD ---
    if scaffold_detail:
        w(f"## L2: Scaffold Selection")
        w(f"")
        d = report["scaffold"]
        w(f"**Score**: {d['passed']}/{d['total']} ({d['pct']})")
        w(f"")
        w(f"| ID | Prompt | Pass | Expected | Got Name | Deps |")
        w(f"|----|--------|------|----------|----------|------|")
        for r in scaffold_detail:
            prompt = r.get("prompt", "")[:40]
            deps = ", ".join(r.get("dependencies", [])[:3])
            w(f"| {r['id']} | {prompt} | {r['status']} | {r['expected']} | {r.get('project_name', '')} | {deps} |")
        w(f"")

        fails = [r for r in scaffold_detail if r["status"] == "FAIL"]
        if fails:
            w(f"### Failures")
            w(f"")
            for r in fails:
                w(f"- **{r['id']}**: {r.get('reason', '')}")
            w(f"")

    # --- LAYER 3: ERROR RECOVERY ---
    if recovery_detail:
        w(f"## L3: Error Recovery")
        w(f"")
        d = report["recovery"]
        w(f"**Score**: {d['passed']}/{d['total']} ({d['pct']})")
        w(f"")
        w(f"| ID | Scenario | Pass | Expected | Got | Issue |")
        w(f"|----|----------|------|----------|-----|-------|")
        for r in recovery_detail:
            issue = r.get("reason", "")[:50]
            w(f"| {r['id']} | {r['name']} | {r['status']} | {r['expected_tool']} | {r.get('actual_tool', 'NONE')} | {issue} |")
        w(f"")

        fails = [r for r in recovery_detail if r["status"] == "FAIL"]
        if fails:
            w(f"### Failures")
            w(f"")
            for r in fails:
                bad = " (retried without fixing)" if r.get("bad_retry") else ""
                w(f"- **{r['id']} {r['name']}**: {r.get('reason', '')}{bad}")
            w(f"")

    # --- LAYER 4: HACK-FREE ---
    if hackfree_detail:
        w(f"## L4: Hack-Free Behavior")
        w(f"")
        d = report["hackfree"]
        w(f"**Score**: {d['passed']}/{d['total']} ({d['pct']})")
        w(f"")
        w(f"| ID | Hack | Pass | Expected | Got | Issue |")
        w(f"|----|------|------|----------|-----|-------|")
        for r in hackfree_detail:
            issue = r.get("reason", "")[:50]
            w(f"| {r['id']} | {r['hack']} | {r['status']} | {r['expected']} | {r.get('actual', 'NONE')} | {issue} |")
        w(f"")

        still = d.get("still_needs_hacks", [])
        if still:
            w(f"### Still Needs Hacks")
            w(f"")
            for hack in still:
                w(f"- {hack}")
            w(f"")

    # --- LAYER 5: INTEGRATION ---
    if int_detail:
        w(f"## L5: Integration")
        w(f"")
        d = report["integration"]
        w(f"**Score**: {d['passed']}/{d['total']} ({d['pct']})  ")
        w(f"**Avg iters**: {d['avg_iters']}  ")
        w(f"**Avg time**: {d['avg_time_s']}s")
        w(f"")

        w(f"### Per-Build Results")
        w(f"")
        w(f"| ID | Level | Prompt | Pass | Iters | Time | Files | Failure |")
        w(f"|----|-------|--------|------|-------|------|-------|---------|")
        for r in int_detail:
            status = "PASS" if r["pass"] else "FAIL"
            prompt = r["prompt"][:35]
            fail = r["failure"][:40] if r["failure"] else ""
            w(f"| {r['id']} | {r['level']} | {prompt} | {status} | {r['iters']} | {r['time_s']}s | {r['files']} | {fail} |")
        w(f"")

        # Tool sequences for each build
        w(f"### Tool Sequences")
        w(f"")
        for r in int_detail:
            status = "PASS" if r["pass"] else "FAIL"
            seq = " -> ".join(r["tools"][:15])
            if len(r["tools"]) > 15:
                seq += f" ... ({len(r['tools'])} total)"
            w(f"- **{r['id']}** [{status}]: `{seq}`")
        w(f"")

        # Diagnostics
        diags = d.get("diagnostics", {})
        w(f"### Agentic Diagnostics")
        w(f"")
        w(f"| Metric | Value | Status |")
        w(f"|--------|-------|--------|")
        for key in ["path_errors", "shell_loops", "edit_failures", "missing_qa", "build_fail_rate"]:
            val = diags.get(key, 0)
            if key == "build_fail_rate":
                bad = val != "0%"
            elif key == "missing_qa":
                bad = val > len(int_detail) // 2
            else:
                bad = val > 0
            status = "BAD" if bad else "OK"
            w(f"| {key} | {val} | {status} |")
        w(f"")

        # Per-build diagnostics detail
        has_issues = [r for r in int_detail if r.get("diagnostics")]
        if has_issues:
            w(f"### Per-Build Diagnostics")
            w(f"")
            for r in has_issues:
                diag = r["diagnostics"]
                issues = []
                if diag.get("path_errors"): issues.append(f"path_errors={diag['path_errors']}")
                if diag.get("shell_exec_loops"): issues.append(f"shell_loops={diag['shell_exec_loops']}")
                if diag.get("edit_failures"): issues.append(f"edit_fails={diag['edit_failures']}")
                if diag.get("missing_qa"): issues.append("missing_qa")
                if diag.get("stalls"): issues.append(f"stalls={diag['stalls']}")
                if diag.get("build_failures"):
                    issues.append(f"build_fail={diag['build_failures']}/{diag.get('build_attempts', '?')}")
                features = []
                if diag.get("used_plan"): features.append("plan")
                if diag.get("used_swell"): features.append("swell")
                if diag.get("used_undertow"): features.append("undertow")
                if diag.get("used_search"): features.append("search")

                status = "PASS" if r["pass"] else "FAIL"
                issue_str = ", ".join(issues) if issues else "clean"
                feat_str = ", ".join(features) if features else "basic"
                w(f"- **{r['id']}** [{status}] issues=[{issue_str}] features=[{feat_str}]")
            w(f"")

        # Failure analysis
        fails = d.get("failures", [])
        if fails:
            w(f"### Failure Analysis")
            w(f"")
            for f in fails:
                w(f"- **{f['id']}**: {f['mode']}")
            w(f"")

    # --- COMPARISON ---
    if prev:
        w(f"## Comparison vs Previous")
        w(f"")
        w(f"**Previous run**: {prev.get('timestamp', 'unknown')}")
        w(f"")
        w(f"| Layer | Before | After | Delta |")
        w(f"|-------|--------|-------|-------|")
        for layer in layer_order:
            if layer in report and layer in prev:
                curr = report[layer]["passed"]
                prev_v = prev[layer]["passed"]
                total = report[layer]["total"]
                diff = curr - prev_v
                arrow = "+" if diff > 0 else "" if diff < 0 else ""
                w(f"| {layer} | {prev_v}/{total} | {curr}/{total} | {arrow}{diff} |")
        w(f"")

    # --- TRAINING DATA SIGNALS ---
    # Extract actionable signals for training data improvement
    signals = []
    if format_detail:
        wrong_tool = [r for r in format_detail if r["pass"] and not r["correct"]]
        if wrong_tool:
            signals.append(f"L1: {len(wrong_tool)} prompts got a tool call but wrong tool — add training examples for these")
        no_tool = [r for r in format_detail if not r["pass"]]
        if no_tool:
            signals.append(f"L1: {len(no_tool)} prompts produced no tool call — model not triggering on these prompt patterns")

    if hackfree_detail:
        still = [r for r in hackfree_detail if r["status"] == "FAIL"]
        for r in still:
            signals.append(f"L4: Hack still needed: {r['hack']} — add training examples for {r['desc']}")

    if int_detail:
        for r in int_detail:
            if not r["pass"] and r["failure"]:
                signals.append(f"L5: {r['id']} failed: {r['failure'][:80]}")
            diag = r.get("diagnostics", {})
            if diag.get("shell_exec_loops", 0) >= 2:
                signals.append(f"L5: {r['id']} shell loop — add rewrite-after-error examples")
            if diag.get("edit_failures", 0) > 0:
                signals.append(f"L5: {r['id']} edit hallucination — train on file_write instead of file_edit after errors")
            if diag.get("path_errors", 0) > 0:
                signals.append(f"L5: {r['id']} path errors — standardize to cd deliverables/X in training data")

    if signals:
        w(f"## Training Data Signals")
        w(f"")
        w(f"Actions to improve the next training round:")
        w(f"")
        for s in signals:
            w(f"- {s}")
        w(f"")

    w(f"---")
    w(f"*Generated by eval.py*")

    return "\n".join(lines)




# =====================================================================
# MERGED LAYERS (was separate submodules)
# =====================================================================

# --- eval_toolcall ---
import re
import subprocess
from dataclasses import dataclass, field

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
    "- User explicitly asks for a plan (\"plan needed\", \"plan carefully\") -> plan_update FIRST\n"
    "- Default: go straight to project_init\n\n"
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
    # Router / routing checks
    routed_to: str = ""          # adapter the router actually picked
    routed_correct: bool = False # did the router pick the expected adapter
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
                     max_tokens: int = 4096, adapter: str | None = None) -> dict:
    """Single inference call to /v1/chat/completions.

    If `adapter` is provided, routes through that adapter for the request
    ("none" = base model, "<name>" = that LoRA). None = leave server default.
    """
    payload = {
        "model": "eval",
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto",
        "temperature": 0.3,  # lower temp for eval consistency
        "max_tokens": max_tokens,
    }
    if adapter is not None:
        payload["adapter"] = adapter
    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(
            f"{endpoint}/v1/chat/completions",
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()
        return resp.json()


def _route_prompt(prompt: str) -> str:
    """Run the production adapter_router against a prompt and return the
    adapter name it picked. Returns 'none' for chat or 'tsunami-adapter'
    (or whatever the router is configured to yield) for build intent."""
    try:
        import sys
        from pathlib import Path as _P
        _repo = _P(__file__).resolve().parent.parent
        if str(_repo) not in sys.path:
            sys.path.insert(0, str(_repo))
        from tsunami.adapter_router import pick_adapter
        picked, _ = pick_adapter(prompt, current="")
        return picked
    except Exception:
        return "none"


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

        # Route through the production adapter_router — chat prompts go to
        # base Gemma (adapter=none), build prompts to the specialized adapter.
        # Expected route: TRIVIAL tier = chat (none), others = build (adapter).
        expected_route = "none" if p["level"] == "trivial" else "tsunami-adapter"
        picked = _route_prompt(p["prompt"])
        result.routed_to = picked
        result.routed_correct = (picked == expected_route)

        try:
            t0 = time.monotonic()
            response = await call_model(endpoint, messages, TOOL_SCHEMAS, adapter=picked)
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

            # When the router sent this to base chat (none), the base model
            # answering in natural language OR a chat-shaped tool call IS the
            # correct behavior. Promote any of:
            #   - non-empty natural content
            #   - message_chat / message_result
            # to "correct" so the scoreboard reflects the production path.
            if picked == "none" and not result.first_tool_correct:
                if name in ("message_chat", "message_result"):
                    result.first_tool_correct = True
                elif content and content.strip():
                    result.first_tool_correct = True
                    result.produced_tool_call = True  # reframe: "produced a response"
                    result.valid_tool_name = True
                    result.valid_args = True
                    result.first_tool = "(chat-response)"

        except Exception as e:
            result.error = str(e)

        log.info(
            f"  {p['id']:>3} [{p['level']:>7}] "
            f"route={'Y' if result.routed_correct else 'N'}→{picked} "
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

# --- eval_scaffold_selection ---

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
    "You are Tsunami. You are the wave. You build apps by calling tools.\n\n"
    "THE PIPELINE (every build follows this EXACTLY):\n"
    "1. project_init(name)\n"
    "2. file_write(App.tsx) -- write COMPLETE code\n"
    "3. shell_exec -- run the break\n"
    "4. undertow -- QA before delivery\n"
    "5. message_result -- land the wave\n\n"
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


# --- eval_error_recovery ---
import re

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
    "- current: your sense of direction. If uncertain, search first.\n"
    "- circulation: routing. Low tension=deliver. High tension=search or refuse.\n"
    "- pressure: sustained uncertainty. 2 failures=search. 4 failures=ask the user.\n"
    "- eddies: parallel workers. 3+ components=dispatch swell.\n"
    "- undertow: QA. ALWAYS verify before delivering.\n"
    "- break: compile. shell_exec build after EVERY file_write.\n"
    "- reef: error. Fix it directly with the right tool. "
    "Type/syntax errors → file_edit. Missing module → shell_exec npm install. "
    "Missing file → file_write. Wrong path (cd fails) → shell_exec with corrected path (NEVER message_chat — just fix it). "
    "CSS resolution errors → file_edit to remove or replace the import (the error tells you the line — don't file_read first).\n\n"
    "THE PIPELINE (every build follows this EXACTLY):\n"
    "1. project_init(name)\n"
    "2. file_write(App.tsx) -- write COMPLETE code\n"
    "3. shell_exec -- run the break\n"
    "4. IF ERROR: fix it directly — file_edit (single-line fix), file_write (missing file or full rewrite), or shell_exec (install module / corrected path)\n"
    "5. undertow -- QA before delivery\n"
    "6. message_result -- land the wave\n\n"
    "NEVER skip the break. NEVER deliver without building. One tool call per response. Be brief."
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
    # Fallback: 31B puts tool calls in content as response:name{...}
    content = msg.get("content", "")
    if content:
        m = re.match(r"(?:response:|call:)?(\w+)\{", content.strip())
        if m:
            return m.group(1), {"raw": content}
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


# --- eval_hack_free ---

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


# --- eval_integration ---
import shutil
from dataclasses import dataclass, field

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("eval_integration")

INT_PROMPTS = [
    # Easy — single component, should complete in <10 iters
    {"id": "IE01", "level": "easy", "prompt": "Build a counter app with plus and minus buttons"},
    {"id": "IE02", "level": "easy", "prompt": "Build a digital clock"},
    {"id": "IE03", "level": "easy", "prompt": "Build a color picker"},

    # Medium — multiple components, state management
    {"id": "IM01", "level": "medium", "prompt": "Build a todo app with add, delete, and mark complete"},
    {"id": "IM02", "level": "medium", "prompt": "Build a pomodoro timer with start, pause, reset"},
    {"id": "IM03", "level": "medium", "prompt": "Build a quiz app with 5 questions and a score"},

    # Hard — multi-file, complex logic
    {"id": "IH01", "level": "hard", "prompt": "Build a kanban board with 3 columns and draggable cards"},
    {"id": "IH02", "level": "hard", "prompt": "Build a markdown editor with live preview"},
    {"id": "IH03", "level": "hard", "prompt": "Build an expense tracker with categories and a chart"},
]


@dataclass
class IntegrationResult:
    prompt_id: str
    level: str
    prompt: str
    # Core outcomes
    scaffolded: bool = False
    files_written: int = 0
    compiled: bool = False
    delivered: bool = False
    iterations: int = 0
    wall_clock_s: float = 0
    tool_sequence: list = field(default_factory=list)
    tool_args: list = field(default_factory=list)  # (tool_name, args_dict) per call
    tool_results: list = field(default_factory=list)  # (tool_name, result_text) per call
    errors: list = field(default_factory=list)
    failure_mode: str = ""
    # Agentic diagnostics
    diagnostics: dict = field(default_factory=dict)


async def run_agent_build(endpoint: str, prompt: str, timeout: int = 180,
                          workspace: str = "/tmp/tsunami_eval") -> IntegrationResult:
    """Run a real Tsunami agent build and capture everything."""
    result = IntegrationResult(prompt_id="", level="", prompt=prompt)

    # Clean workspace (ignore errors from node_modules permission issues)
    ws = Path(workspace)
    if ws.exists():
        shutil.rmtree(ws, ignore_errors=True)
    ws.mkdir(parents=True, exist_ok=True)

    t0 = time.monotonic()

    try:
        # Import and configure Tsunami

        from tsunami.config import TsunamiConfig
        from tsunami.agent import Agent

        config = TsunamiConfig(
            model_backend="api",
            model_name="eval",
            model_endpoint=endpoint,
            eddy_endpoint=endpoint,
            workspace_dir=str(ws),
            max_iterations=60,
            temperature=0.1,
        )

        agent = Agent(config)

        # Monkey-patch to capture tool calls, args, and results
        original_step = agent._step
        tool_log = []
        tool_args_log = []
        tool_results_log = []

        # Wrap tool execution to capture args + results
        original_registry_get = agent.registry.get
        def tracking_get(name):
            tool = original_registry_get(name)
            if tool is None:
                return None
            original_execute = tool.execute
            async def tracked_execute(**kwargs):
                tool_args_log.append((name, dict(kwargs)))
                r = await original_execute(**kwargs)
                tool_results_log.append((name, str(r.content)[:500] if r else ""))
                return r
            tool.execute = tracked_execute
            return tool
        agent.registry.get = tracking_get

        async def tracking_step():
            r = await original_step()
            if agent._tool_history:
                last = agent._tool_history[-1]
                tool_log.append(last)
            return r

        agent._step = tracking_step

        # Run with timeout
        try:
            output = await asyncio.wait_for(
                agent.run(prompt),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            output = "TIMEOUT"
            result.failure_mode = f"Timed out after {timeout}s"

        result.wall_clock_s = time.monotonic() - t0
        result.iterations = agent.state.iteration
        result.tool_sequence = tool_log
        result.tool_args = tool_args_log
        result.tool_results = tool_results_log
        result.delivered = agent.state.task_complete

        # Check what happened
        deliverables = ws / "deliverables"
        if deliverables.exists():
            projects = sorted(
                [d for d in deliverables.iterdir() if d.is_dir() and (d / "package.json").exists()],
                key=lambda p: p.stat().st_mtime, reverse=True,
            )
            if projects:
                result.scaffolded = True
                project = projects[0]

                # Count files written
                src = project / "src"
                if src.exists():
                    result.files_written = sum(1 for f in src.rglob("*.tsx") if f.is_file())
                    result.files_written += sum(1 for f in src.rglob("*.ts") if f.is_file())

                # Check if it compiled
                dist = project / "dist"
                if dist.exists() and (dist / "index.html").exists():
                    result.compiled = True

                # Check for build errors in the tool sequence
                # (would need to capture tool results too — simplified here)

        # === AGENTIC DIAGNOSTICS ===
        diag = {}

        # 1. PATH PROBLEMS — wrong cd paths in shell_exec
        path_errors = 0
        bad_paths = []
        for name, args in result.tool_args:
            if name == "shell_exec":
                cmd = args.get("command", "") if isinstance(args, dict) else str(args)
                # Catch: cd workspace/deliverables (should be cd deliverables/)
                if "cd workspace/deliverables" in cmd and "cd ./workspace" not in cmd:
                    path_errors += 1
                    bad_paths.append(cmd[:80])
                # Catch: cd /home/.../workspace (absolute path to workspace)
                if "/workspace/deliverables" in cmd and cmd.startswith("cd /"):
                    path_errors += 1
                    bad_paths.append(cmd[:80])
        diag["path_errors"] = path_errors
        if bad_paths:
            diag["bad_paths"] = bad_paths

        # 2. SYNTAX ERRORS — vite build failures from tool results
        build_attempts = 0
        build_failures = 0
        vite_errors = []
        for name, res_text in result.tool_results:
            if name == "shell_exec" and ("vite build" in str(res_text) or "npx vite" in str(res_text)):
                build_attempts += 1
                if "Error" in str(res_text) or "error" in str(res_text):
                    build_failures += 1
                    # Extract the error
                    err = str(res_text)[:200]
                    vite_errors.append(err)
        diag["build_attempts"] = build_attempts
        diag["build_failures"] = build_failures
        diag["build_success_rate"] = f"{(build_attempts-build_failures)/max(build_attempts,1)*100:.0f}%"
        if vite_errors:
            diag["vite_errors"] = vite_errors

        # 3. ERROR RECOVERY — did the model fix errors or just retry?
        shell_loop = 0
        prev_was_shell = False
        for name in result.tool_sequence:
            if name == "shell_exec":
                if prev_was_shell:
                    shell_loop += 1
                prev_was_shell = True
            else:
                prev_was_shell = False
        diag["shell_exec_loops"] = shell_loop  # consecutive shell_exec without file_edit between

        # Check if file_edit follows build failure (good recovery)
        recovery_attempts = 0
        for j in range(len(result.tool_results) - 1):
            name, res = result.tool_results[j]
            if name == "shell_exec" and "Error" in str(res):
                # What's the next tool?
                if j + 1 < len(result.tool_sequence):
                    next_tool = result.tool_sequence[j + 1] if j + 1 < len(result.tool_sequence) else ""
                    if next_tool in ("file_edit", "file_write", "file_read"):
                        recovery_attempts += 1
        diag["error_recovery_attempts"] = recovery_attempts

        # 4. MISSING QA — delivered without undertow
        used_undertow = "undertow" in result.tool_sequence
        diag["used_undertow"] = used_undertow
        if result.delivered and not used_undertow:
            diag["missing_qa"] = True

        # 5. MISSING PARAMS — file_write without path or content
        missing_params = 0
        for name, args in result.tool_args:
            if isinstance(args, dict):
                if name == "file_write" and ("path" not in args or "content" not in args):
                    missing_params += 1
                if name == "file_edit" and ("path" not in args or "old_text" not in args):
                    missing_params += 1
        diag["missing_params"] = missing_params

        # 6. TOOL DIVERSITY — how many unique tools used
        unique_tools = len(set(result.tool_sequence))
        diag["unique_tools"] = unique_tools
        diag["used_plan"] = "plan_update" in result.tool_sequence
        diag["used_swell"] = "swell" in result.tool_sequence
        diag["used_search"] = "search_web" in result.tool_sequence
        diag["used_message_chat"] = "message_chat" in result.tool_sequence

        # 7. STALL DETECTION — same tool called 3+ times consecutively
        stalls = []
        if len(result.tool_sequence) >= 3:
            for j in range(2, len(result.tool_sequence)):
                if (result.tool_sequence[j] == result.tool_sequence[j-1] == result.tool_sequence[j-2]):
                    stalls.append(f"{result.tool_sequence[j]} x3 at iter {j}")
        diag["stalls"] = stalls

        # 8. file_edit HALLUCINATION — edit failures
        edit_failures = 0
        for name, res in result.tool_results:
            if name == "file_edit" and ("not found" in str(res).lower() or "0 matches" in str(res).lower()):
                edit_failures += 1
        diag["edit_failures"] = edit_failures

        # 9. LINTING — did model react to vite error feedback?
        lint_reacted = 0
        for j in range(len(result.tool_results)):
            name, res = result.tool_results[j]
            if name == "shell_exec" and "Error" in str(res) and j + 1 < len(result.tool_sequence):
                next_tool = result.tool_sequence[j + 1]
                if next_tool in ("file_edit", "file_write", "file_read", "message_chat"):
                    lint_reacted += 1
        diag["lint_reactions"] = lint_reacted

        result.diagnostics = diag

        # Classify failure mode with richer diagnostics
        if not result.delivered:
            if not result.scaffolded:
                result.failure_mode = result.failure_mode or "Never scaffolded"
            elif result.files_written == 0:
                result.failure_mode = result.failure_mode or "Scaffolded but never wrote code"
            elif path_errors > 0:
                result.failure_mode = result.failure_mode or f"Path errors ({path_errors}): {bad_paths[0]}"
            elif build_failures > 0 and shell_loop >= 2:
                result.failure_mode = result.failure_mode or f"Shell loop ({shell_loop}x): retried build without fixing code"
            elif build_failures > 0 and recovery_attempts == 0:
                result.failure_mode = result.failure_mode or "Build failed, no error recovery attempted"
            elif not result.compiled:
                result.failure_mode = result.failure_mode or f"Build failed ({build_failures}/{build_attempts}): {vite_errors[0][:100] if vite_errors else 'unknown'}"
            else:
                result.failure_mode = result.failure_mode or "Compiled but didn't deliver"

    except Exception as e:
        result.wall_clock_s = time.monotonic() - t0
        result.failure_mode = f"Exception: {str(e)[:200]}"
        result.errors.append(str(e))

    return result


async def main():
    parser = argparse.ArgumentParser(description="Full eval pyramid")
    parser.add_argument("--endpoint", default="http://localhost:8095")
    parser.add_argument("--quick", action="store_true", help="Skip integration eval")
    parser.add_argument("--layers", default=None,
                        help="Comma-separated: format,scaffold,recovery,hackfree,integration")
    parser.add_argument("--output", default="workspace/training_data/eval_report.json")
    parser.add_argument("--compare", default=None, help="Previous report JSON to compare against")
    args = parser.parse_args()

    layers = set()
    if args.layers:
        layers = set(args.layers.split(","))
    elif args.quick:
        layers = {"format", "scaffold", "recovery", "hackfree"}
    else:
        layers = {"format", "scaffold", "recovery", "hackfree", "integration"}

    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "endpoint": args.endpoint,
        "layers_run": sorted(layers),
    }
    t0 = time.monotonic()

    # Keep per-test details for the report
    format_detail = []
    scaffold_detail = []
    recovery_detail = []
    hackfree_detail = []
    int_detail = []

    # Layer 1: Format
    if "format" in layers:
        print(f"\n{'='*60}")
        print(f"  LAYER 1: FORMAT EVAL")
        print(f"{'='*60}")

        format_results = await eval_format(args.endpoint, EVAL_PROMPTS)
        n = len(format_results)
        passed = sum(1 for r in format_results if r.produced_tool_call)
        report["format"] = {
            "total": n, "passed": passed,
            "pct": f"{100*passed/n:.0f}%",
            "valid_name": sum(1 for r in format_results if r.valid_tool_name),
            "correct_first": sum(1 for r in format_results if r.first_tool_correct),
        }
        format_detail = [
            {"id": r.prompt_id, "level": r.level, "prompt": r.prompt,
             "pass": r.produced_tool_call, "tool": r.first_tool or "NONE",
             "expected": r.expected_first_tool, "correct": r.first_tool_correct,
             "latency_ms": round(r.latency_ms), "error": r.error}
            for r in format_results
        ]

    # Layer 2: Scaffold Selection
    if "scaffold" in layers:
        print(f"\n{'='*60}")
        print(f"  LAYER 2: SCAFFOLD SELECTION")
        print(f"{'='*60}")

        scaffold_results = await eval_scaffolds(args.endpoint)
        n = len(scaffold_results)
        passed = sum(1 for r in scaffold_results if r["status"] == "PASS")
        report["scaffold"] = {"total": n, "passed": passed, "pct": f"{100*passed/n:.0f}%"}
        scaffold_detail = scaffold_results

    # Layer 3: Error Recovery
    if "recovery" in layers:
        print(f"\n{'='*60}")
        print(f"  LAYER 3: ERROR RECOVERY")
        print(f"{'='*60}")

        recovery_results = await eval_recovery(args.endpoint)
        n = len(recovery_results)
        passed = sum(1 for r in recovery_results if r["status"] == "PASS")
        report["recovery"] = {"total": n, "passed": passed, "pct": f"{100*passed/n:.0f}%"}
        recovery_detail = recovery_results

    # Layer 4: Hack-Free
    if "hackfree" in layers:
        print(f"\n{'='*60}")
        print(f"  LAYER 4: HACK-FREE BEHAVIOR")
        print(f"{'='*60}")

        hackfree_results = await eval_hack_free(args.endpoint)
        n = len(hackfree_results)
        passed = sum(1 for r in hackfree_results if r["status"] == "PASS")
        report["hackfree"] = {
            "total": n, "passed": passed, "pct": f"{100*passed/n:.0f}%",
            "still_needs_hacks": [r["hack"] for r in hackfree_results if r["status"] == "FAIL"],
        }
        hackfree_detail = hackfree_results

    # Layer 5: Integration
    if "integration" in layers:
        print(f"\n{'='*60}")
        print(f"  LAYER 5: INTEGRATION (real builds)")
        print(f"{'='*60}")

        int_results = []
        for p in INT_PROMPTS:
            log.info(f"  Building: {p['prompt'][:50]}...")
            r = await run_agent_build(args.endpoint, p["prompt"], timeout=180)
            r.prompt_id = p["id"]
            r.level = p["level"]
            int_results.append(r)
            status = "PASS" if r.delivered and r.compiled else "FAIL"
            log.info(f"    {status} | {r.iterations} iters | {r.wall_clock_s:.0f}s | {r.failure_mode or 'OK'}")

        n = len(int_results)
        passed = sum(1 for r in int_results if r.delivered and r.compiled)
        report["integration"] = {
            "total": n, "passed": passed, "pct": f"{100*passed/n:.0f}%",
            "avg_iters": round(sum(r.iterations for r in int_results) / n, 1),
            "avg_time_s": round(sum(r.wall_clock_s for r in int_results) / n, 1),
            "diagnostics": {
                "path_errors": sum(r.diagnostics.get("path_errors", 0) for r in int_results),
                "shell_loops": sum(r.diagnostics.get("shell_exec_loops", 0) for r in int_results),
                "edit_failures": sum(r.diagnostics.get("edit_failures", 0) for r in int_results),
                "missing_qa": sum(1 for r in int_results if r.diagnostics.get("missing_qa")),
                "build_fail_rate": f"{100*sum(r.diagnostics.get('build_failures',0) for r in int_results)/max(sum(r.diagnostics.get('build_attempts',0) for r in int_results),1):.0f}%",
            },
            "failures": [
                {"id": r.prompt_id, "mode": r.failure_mode}
                for r in int_results if not (r.delivered and r.compiled)
            ],
        }
        int_detail = [
            {"id": r.prompt_id, "level": r.level, "prompt": r.prompt,
             "pass": r.delivered and r.compiled,
             "scaffolded": r.scaffolded, "files": r.files_written,
             "compiled": r.compiled, "delivered": r.delivered,
             "iters": r.iterations, "time_s": round(r.wall_clock_s, 1),
             "failure": r.failure_mode or "",
             "tools": r.tool_sequence[:20],
             "diagnostics": r.diagnostics}
            for r in int_results
        ]

    elapsed = time.monotonic() - t0
    report["elapsed_s"] = round(elapsed, 1)

    # Load previous run for comparison
    prev = None
    if args.compare and Path(args.compare).exists():
        with open(args.compare) as f:
            prev = json.load(f)

    # === CONSOLE SUMMARY ===
    print(f"\n{'='*60}")
    print(f"  TSUNAMI EVAL REPORT")
    print(f"  {report['timestamp']} | {elapsed:.0f}s")
    print(f"{'='*60}\n")

    layer_order = ["format", "scaffold", "recovery", "hackfree", "integration"]
    for layer in layer_order:
        if layer in report:
            data = report[layer]
            p = data["passed"]
            t = data["total"]
            pct = data["pct"]
            bar = "█" * (p * 20 // t) + "░" * (20 - p * 20 // t)
            delta_str = ""
            if prev and layer in prev:
                d = p - prev[layer]["passed"]
                if d != 0:
                    delta_str = f"  \033[{'32' if d > 0 else '31'}m{'↑' if d > 0 else '↓'}{'+' if d > 0 else ''}{d}\033[0m"
            print(f"  {layer:<13} {bar} {p}/{t} ({pct}){delta_str}")

    # === GENERATE MARKDOWN REPORT ===
    md = generate_markdown_report(
        report, prev, format_detail, scaffold_detail,
        recovery_detail, hackfree_detail, int_detail,
    )

    # Save JSON
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(report, f, indent=2, default=str)

    # Save per-test details in JSON (for future comparisons)
    detail_data = {**report, "details": {
        "format": format_detail, "scaffold": scaffold_detail,
        "recovery": recovery_detail, "hackfree": hackfree_detail,
        "integration": int_detail,
    }}
    detail_path = args.output.replace(".json", "_detail.json")
    with open(detail_path, "w") as f:
        json.dump(detail_data, f, indent=2, default=str)

    # Save markdown report
    report_path = args.output.replace(".json", ".md")
    with open(report_path, "w") as f:
        f.write(md)

    log.info(f"\n  JSON:   {args.output}")
    log.info(f"  Detail: {detail_path}")
    log.info(f"  Report: {report_path}")
    log.info(f"  Compare next time with: --compare {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
