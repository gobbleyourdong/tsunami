#!/usr/bin/env python3
"""Gamedev adapter eval — L1-L4 quick, L5 integration (optional).

Tests the gemma-4-e4b gamedev adapter against the GAMEDEV_EVAL_PLAN.md rubric.
Mirrors the app-builder eval structure but uses game-specific prompts, tools,
and system prompt.

Usage:
  # Quick L1-L4 (~5 min)
  python training/eval_gamedev.py --endpoint http://localhost:8090 --adapter gamedev --quick

  # Full L1-L5 (adds 9 real builds, ~30 min)
  python training/eval_gamedev.py --endpoint http://localhost:8090 --adapter gamedev

  # Compare to previous
  python training/eval_gamedev.py --endpoint http://localhost:8090 --adapter gamedev \\
      --quick --compare workspace/training_data/eval_report_gamedev_prev.json
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
log = logging.getLogger("eval_gamedev")

GAME_SYSTEM = """You are Tsunami. You are the wave. You build games by calling tools.

## The Ocean

- **current**: your sense of direction. Low tension = deliver. High tension = search.
- **circulation**: routing. Low tension -> deliver. High tension -> search or refuse.
- **pressure**: sustained uncertainty. 2 failures -> search. 4 failures -> ask the user.
- **undertow**: QA. ALWAYS verify before delivering.
- **break**: compile. shell_exec build after EVERY file_write.
- **reef**: error. Fix directly. Type/syntax -> file_edit. Missing module -> shell_exec npm install. Wrong path -> shell_exec with corrected path.

## The Pipeline (every game follows this EXACTLY)

1. project_init(name) -- scaffold the game project
2. file_write(src/main.ts) -- write COMPLETE game code in one file
3. shell_exec("cd deliverables/{name} && npm run build") -- run the break
4. IF reef: fix directly -- file_edit for syntax, shell_exec for missing modules
5. undertow(dist/index.html) -- QA before delivery
6. message_result -- land the wave

## Engine API (import from '@engine/...' or 'tsunami-engine')

Input: KeyboardInput, ActionMap
Systems: ScoreSystem, HealthSystem, CheckpointSystem
Flow: SceneManager, GameFlow, DifficultyManager, TutorialSystem
Renderer: FrameLoop -- onUpdate(stats) gives dt
Physics: PhysicsWorld, RigidBody, shapes (Sphere, Box, Capsule), raycast
VFX: ParticleSystem, PARTICLE_PRESETS (fire, smoke, sparks, blood, magic)
AI: BehaviorTree, FSM, Pathfinding
Math: Vec3 (create, add, sub, scale, dot, cross, normalize, lerp, distance)

## Game Pattern

imports -> constants -> state -> keyboard.bind() -> canvas setup -> draw() -> loop.onUpdate -> loop.start()

## Rules
- NEVER skip the break.
- NEVER deliver without building.
- One tool call per response. Be brief.
- Write COMPLETE game in main.ts -- no partial files, no TODO stubs.
- Canvas 2D for all rendering. No React, no DOM manipulation for game state.
"""

GAME_TOOLS = [
    {"type": "function", "function": {
        "name": "project_init",
        "description": "Create a game project from the scaffold library.",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string"},
        }, "required": ["name"]},
    }},
    {"type": "function", "function": {
        "name": "file_write",
        "description": "Create or overwrite a file with full content.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"},
        }, "required": ["path", "content"]},
    }},
    {"type": "function", "function": {
        "name": "file_edit",
        "description": "Make targeted modifications to an existing file.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"},
            "old_text": {"type": "string"},
            "new_text": {"type": "string"},
        }, "required": ["path", "old_text", "new_text"]},
    }},
    {"type": "function", "function": {
        "name": "shell_exec",
        "description": "Run a shell command and return its output.",
        "parameters": {"type": "object", "properties": {
            "command": {"type": "string"},
        }, "required": ["command"]},
    }},
    {"type": "function", "function": {
        "name": "undertow",
        "description": "QA-test an HTML file in a headless browser before delivery.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"},
            "expect": {"type": "string"},
        }, "required": ["path"]},
    }},
    {"type": "function", "function": {
        "name": "message_result",
        "description": "Deliver final outcome and end the task.",
        "parameters": {"type": "object", "properties": {
            "text": {"type": "string"},
        }, "required": []},
    }},
    {"type": "function", "function": {
        "name": "message_chat",
        "description": "Talk to the user. done=true ends, done=false continues.",
        "parameters": {"type": "object", "properties": {
            "text": {"type": "string"},
            "done": {"type": "boolean"},
        }, "required": ["text"]},
    }},
    {"type": "function", "function": {
        "name": "search_web",
        "description": "Search the web for information.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string"},
        }, "required": ["query"]},
    }},
    {"type": "function", "function": {
        "name": "plan_update",
        "description": "Create or revise the task plan.",
        "parameters": {"type": "object", "properties": {
            "goal": {"type": "string"},
            "phases": {"type": "array"},
        }, "required": ["goal", "phases"]},
    }},
]

# L1 Format prompts
GAME_FORMAT_PROMPTS = [
    {"id": "GT01", "level": "trivial", "prompt": "What games can you build?",
     "expected": "message_chat", "alt": "message_result"},
    {"id": "GT02", "level": "trivial", "prompt": "Hello",
     "expected": "message_chat", "alt": "message_result"},
    {"id": "GE01", "level": "easy", "prompt": "Build a snake game",
     "expected": "project_init"},
    {"id": "GE02", "level": "easy", "prompt": "Build a Pong game",
     "expected": "project_init"},
    {"id": "GE03", "level": "easy", "prompt": "Build a breakout / brick breaker game",
     "expected": "project_init"},
    {"id": "GE04", "level": "easy", "prompt": "Build a simple 2D platformer",
     "expected": "project_init"},
    {"id": "GM01", "level": "medium", "prompt": "Build a Tetris game with rotation and line clearing",
     "expected": "project_init"},
    {"id": "GM02", "level": "medium", "prompt": "Build a space invaders game with multiple enemy rows and shooting",
     "expected": "project_init"},
    {"id": "GH01", "level": "hard", "prompt": "Build a 2D top-down dungeon crawler with rooms, enemies, and items",
     "expected": "project_init"},
    {"id": "GH02", "level": "hard", "prompt": "Build a tower defense game with waves, turrets, and health bar",
     "expected": "project_init"},
    {"id": "GX01", "level": "extreme", "prompt": "Build a multiplayer battle royale game in the browser",
     "expected": "project_init"},
    {"id": "GX02", "level": "extreme", "prompt": "Build a 3D first-person dungeon crawler using WebGPU",
     "expected": "project_init"},
]

# L2 Scaffold prompts
GAME_SCAFFOLD_PROMPTS = [
    {"id": "GS01", "prompt": "Build a snake game"},
    {"id": "GS02", "prompt": "Build a rhythm game with timing windows"},
    {"id": "GS03", "prompt": "Build a 2D platformer with jumping and obstacles"},
    {"id": "GS04", "prompt": "Build a space shooter with power-ups and enemy waves"},
    {"id": "GS05", "prompt": "Build a particle physics sandbox"},
    {"id": "GS06", "prompt": "Build a pinball game with physics"},
]

# L3 Error recovery scenarios
GAME_ERROR_SCENARIOS = [
    {
        "id": "GER01",
        "name": "missing-engine-module",
        "messages": [
            {"role": "system", "content": GAME_SYSTEM},
            {"role": "user", "content": "Build a snake game"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c1", "type": "function", "function": {
                    "name": "project_init", "arguments": json.dumps({"name": "snake"})}}
            ]},
            {"role": "tool", "tool_call_id": "c1",
             "content": "[project_init] Created game project 'snake'. Write src/main.ts."},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c2", "type": "function", "function": {
                    "name": "shell_exec",
                    "arguments": json.dumps({"command": "cd deliverables/snake && npx vite build"})}}
            ]},
            {"role": "tool", "tool_call_id": "c2",
             "content": "[shell_exec] Error: Cannot find module '@engine/renderer'. Did you mean '@engine/core'?"},
        ],
        "expected_tool": "file_edit",
        "reject_tools": ["project_init", "message_result"],
    },
    {
        "id": "GER02",
        "name": "canvas-type-error",
        "messages": [
            {"role": "system", "content": GAME_SYSTEM},
            {"role": "user", "content": "Build a breakout game"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c1", "type": "function", "function": {
                    "name": "project_init", "arguments": json.dumps({"name": "breakout"})}}
            ]},
            {"role": "tool", "tool_call_id": "c1",
             "content": "[project_init] Created game project 'breakout'. Write src/main.ts."},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c2", "type": "function", "function": {
                    "name": "shell_exec",
                    "arguments": json.dumps({"command": "cd deliverables/breakout && npm run build"})}}
            ]},
            {"role": "tool", "tool_call_id": "c2",
             "content": "[shell_exec] Error: src/main.ts(12,32): error TS2531: Object is possibly 'null'. (canvas.getContext('2d'))"},
        ],
        "expected_tool": "file_edit",
        "reject_tools": ["project_init", "message_result"],
    },
    {
        "id": "GER03",
        "name": "game-loop-syntax",
        "messages": [
            {"role": "system", "content": GAME_SYSTEM},
            {"role": "user", "content": "Build a pong game"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c1", "type": "function", "function": {
                    "name": "project_init", "arguments": json.dumps({"name": "pong"})}}
            ]},
            {"role": "tool", "tool_call_id": "c1",
             "content": "[project_init] Created game project 'pong'. Write src/main.ts."},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c2", "type": "function", "function": {
                    "name": "shell_exec",
                    "arguments": json.dumps({"command": "cd deliverables/pong && npm run build"})}}
            ]},
            {"role": "tool", "tool_call_id": "c2",
             "content": "[shell_exec] Error: src/main.ts(45,5): error TS1005: ';' expected. (loop.onUpdate((dt)) => {)"},
        ],
        "expected_tool": "file_edit",
        "reject_tools": ["project_init", "message_result", "shell_exec"],
    },
    {
        "id": "GER04",
        "name": "missing-asset-file",
        "messages": [
            {"role": "system", "content": GAME_SYSTEM},
            {"role": "user", "content": "Build a space shooter game"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c1", "type": "function", "function": {
                    "name": "project_init", "arguments": json.dumps({"name": "space-shooter"})}}
            ]},
            {"role": "tool", "tool_call_id": "c1",
             "content": "[project_init] Created game project 'space-shooter'. Write src/main.ts."},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c2", "type": "function", "function": {
                    "name": "shell_exec",
                    "arguments": json.dumps({"command": "cd deliverables/space-shooter && npm run build"})}}
            ]},
            {"role": "tool", "tool_call_id": "c2",
             "content": "[shell_exec] Error: Failed to resolve import 'public/ship.png'. File does not exist."},
        ],
        "expected_tool": "file_write",
        "reject_tools": ["project_init", "message_result"],
    },
    {
        "id": "GER05",
        "name": "wrong-path",
        "messages": [
            {"role": "system", "content": GAME_SYSTEM},
            {"role": "user", "content": "Build a tetris game"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c1", "type": "function", "function": {
                    "name": "project_init", "arguments": json.dumps({"name": "tetris"})}}
            ]},
            {"role": "tool", "tool_call_id": "c1",
             "content": "[project_init] Created game project 'tetris'. Write src/main.ts."},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c2", "type": "function", "function": {
                    "name": "shell_exec",
                    "arguments": json.dumps({"command": "cd workspace/deliverables/tetris && npm run build"})}}
            ]},
            {"role": "tool", "tool_call_id": "c2",
             "content": "[shell_exec] Error: No such file or directory: workspace/deliverables/tetris"},
        ],
        "expected_tool": "shell_exec",
        "reject_tools": ["message_chat", "message_result", "project_init"],
    },
    {
        "id": "GER06",
        "name": "missing-frameloop",
        "messages": [
            {"role": "system", "content": GAME_SYSTEM},
            {"role": "user", "content": "Build a platformer game"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c1", "type": "function", "function": {
                    "name": "project_init", "arguments": json.dumps({"name": "platformer"})}}
            ]},
            {"role": "tool", "tool_call_id": "c1",
             "content": "[project_init] Created game project 'platformer'. Write src/main.ts."},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c2", "type": "function", "function": {
                    "name": "shell_exec",
                    "arguments": json.dumps({"command": "cd deliverables/platformer && npm run build"})}}
            ]},
            {"role": "tool", "tool_call_id": "c2",
             "content": "[shell_exec] Error: src/main.ts(3,8): error TS2304: Cannot find name 'FrameLoop'. Did you forget to import it from '@engine/renderer'?"},
        ],
        "expected_tool": "file_edit",
        "reject_tools": ["project_init", "message_result"],
    },
]

# L4 Hack-free scenarios
GAME_HACK_SCENARIOS = [
    {
        "id": "GHF01", "hack": "Auto-scaffold",
        "desc": "Should call project_init immediately on game build prompt",
        "messages": [
            {"role": "system", "content": GAME_SYSTEM},
            {"role": "user", "content": "Build a snake game"},
        ],
        "expected_tool": "project_init",
        "reject_tools": ["file_read", "search_web", "message_chat"],
    },
    {
        "id": "GHF02", "hack": "Research gate",
        "desc": "Should search before building a visual/reference clone",
        "messages": [
            {"role": "system", "content": GAME_SYSTEM},
            {"role": "user", "content": "Build a game like Celeste (pixel-art platformer with dashing)"},
        ],
        "expected_tool": "search_web",
        "reject_tools": ["project_init"],
    },
    {
        "id": "GHF03", "hack": "Stall detection",
        "desc": "After 2 reads, should start writing main.ts",
        "messages": [
            {"role": "system", "content": GAME_SYSTEM},
            {"role": "user", "content": "Build a breakout game"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c1", "type": "function", "function": {
                    "name": "project_init", "arguments": json.dumps({"name": "breakout"})}}
            ]},
            {"role": "tool", "tool_call_id": "c1",
             "content": "[project_init] Created game project 'breakout'. Write src/main.ts."},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c2", "type": "function", "function": {
                    "name": "file_read", "arguments": json.dumps({"path": "deliverables/breakout/src/main.ts"})}}
            ]},
            {"role": "tool", "tool_call_id": "c2",
             "content": "[file_read] // main.ts stub"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c3", "type": "function", "function": {
                    "name": "file_read", "arguments": json.dumps({"path": "deliverables/breakout/package.json"})}}
            ]},
            {"role": "tool", "tool_call_id": "c3",
             "content": "[file_read] {\"name\": \"breakout\"}"},
        ],
        "expected_tool": "file_write",
        "reject_tools": ["file_read"],
    },
    {
        "id": "GHF04", "hack": "Code-write gate",
        "desc": "After scaffolding, write code (not deliver empty scaffold)",
        "messages": [
            {"role": "system", "content": GAME_SYSTEM},
            {"role": "user", "content": "Build a Pong game"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c1", "type": "function", "function": {
                    "name": "project_init", "arguments": json.dumps({"name": "pong"})}}
            ]},
            {"role": "tool", "tool_call_id": "c1",
             "content": "[project_init] Created game project 'pong'. Write src/main.ts."},
        ],
        "expected_tool": "file_write",
        "reject_tools": ["message_result", "message_chat"],
    },
    {
        "id": "GHF05", "hack": "Shell loop detection",
        "desc": "Two identical build failures -> file_write missing component, not retry",
        "messages": [
            {"role": "system", "content": GAME_SYSTEM},
            {"role": "user", "content": "The build keeps failing with missing module error"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c1", "type": "function", "function": {
                    "name": "shell_exec",
                    "arguments": json.dumps({"command": "cd deliverables/game && npm run build"})}}
            ]},
            {"role": "tool", "tool_call_id": "c1",
             "content": "[shell_exec] Error: Cannot find module './components/HUD'"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c2", "type": "function", "function": {
                    "name": "shell_exec",
                    "arguments": json.dumps({"command": "cd deliverables/game && npm run build"})}}
            ]},
            {"role": "tool", "tool_call_id": "c2",
             "content": "[shell_exec] Error: Cannot find module './components/HUD'"},
        ],
        "expected_tool": "file_write",
        "reject_tools": ["shell_exec", "project_init", "message_chat"],
    },
    {
        "id": "GHF06", "hack": "Conversation",
        "desc": "Greeting -> message_chat, not project_init",
        "messages": [
            {"role": "system", "content": GAME_SYSTEM},
            {"role": "user", "content": "Hello! What kinds of games can you build?"},
        ],
        "expected_tool": "message_chat",
        "reject_tools": ["project_init", "file_write"],
    },
    {
        "id": "GHF07", "hack": "Engine imports",
        "desc": "file_write should use @engine/ imports and FrameLoop, not React",
        "messages": [
            {"role": "system", "content": GAME_SYSTEM},
            {"role": "user", "content": "Build a space invaders game"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c1", "type": "function", "function": {
                    "name": "project_init", "arguments": json.dumps({"name": "space-invaders"})}}
            ]},
            {"role": "tool", "tool_call_id": "c1",
             "content": "[project_init] Created game project 'space-invaders'. Write src/main.ts with @engine/ imports."},
        ],
        "expected_tool": "file_write",
        "content_checks": {
            # Accept both @engine/ (canonical) and tsunami-engine (adapter natural output)
            # aa3a663 added tsunami-engine as a vite alias — both are valid
            "contains_any": ["@engine/", "tsunami-engine"],
            "not_contains": ["import React", "useState", "useEffect"],
        },
        "reject_tools": ["message_result"],
    },
    {
        "id": "GHF08", "hack": "Canvas 2D pattern",
        "desc": "Game rendering should use Canvas 2D, not DOM manipulation",
        "messages": [
            {"role": "system", "content": GAME_SYSTEM},
            {"role": "user", "content": "Build a snake game"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c1", "type": "function", "function": {
                    "name": "project_init", "arguments": json.dumps({"name": "snake"})}}
            ]},
            {"role": "tool", "tool_call_id": "c1",
             "content": "[project_init] Created game project 'snake'. Write src/main.ts."},
        ],
        "expected_tool": "file_write",
        "content_checks": {
            "contains": ["canvas"],
            "not_contains": ["document.createElement('div')", "innerHTML ="],
        },
        "reject_tools": ["message_result"],
    },
    {
        "id": "GHF09", "hack": "Complex game planning",
        "desc": "Complex multi-system game with 'plan carefully' -> plan_update first",
        "messages": [
            {"role": "system", "content": GAME_SYSTEM},
            {"role": "user", "content": "Build a full MMORPG with character classes, skill trees, inventory, crafting, dungeons, and a world map. Plan carefully before building."},
        ],
        "expected_tool": "plan_update",
        "reject_tools": ["project_init", "file_write"],
    },
    {
        "id": "GHF10", "hack": "QA before delivery",
        "desc": "After successful build, call undertow before message_result",
        "messages": [
            {"role": "system", "content": GAME_SYSTEM},
            {"role": "user", "content": "Build a tetris game"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c1", "type": "function", "function": {
                    "name": "project_init", "arguments": json.dumps({"name": "tetris"})}}
            ]},
            {"role": "tool", "tool_call_id": "c1",
             "content": "[project_init] Created game project 'tetris'. Write src/main.ts."},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c2", "type": "function", "function": {
                    "name": "file_write",
                    "arguments": json.dumps({"path": "deliverables/tetris/src/main.ts", "content": "// tetris"})}}
            ]},
            {"role": "tool", "tool_call_id": "c2",
             "content": "[file_write] Written to deliverables/tetris/src/main.ts"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c3", "type": "function", "function": {
                    "name": "shell_exec",
                    "arguments": json.dumps({"command": "cd deliverables/tetris && npm run build"})}}
            ]},
            {"role": "tool", "tool_call_id": "c3",
             "content": "[shell_exec] Build successful. dist/index.html ready."},
        ],
        "expected_tool": "undertow",
        "reject_tools": ["message_result"],
    },
]

# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------
async def chat(client, endpoint, messages, tools, adapter, timeout=90.0):
    payload = {
        "model": "tsunami",
        "messages": messages,
        "tools": tools,
        "max_tokens": 512,
        "temperature": 0,
    }
    if adapter:
        payload["adapter"] = adapter
    t0 = time.monotonic()
    try:
        r = await client.post(
            f"{endpoint}/v1/chat/completions",
            json=payload,
            timeout=timeout,
        )
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
                try:
                    args = json.loads(args)
                except Exception:
                    pass
            return name, args, ""
        content = msg.get("content", "") or ""
        m = re.search(r"<\|tool_call>call:(\w+)\{", content)
        if m:
            return m.group(1), {}, ""
        return "", {}, "no tool call in response"
    except Exception as e:
        return "", {}, str(e)


# ---------------------------------------------------------------------------
# Layer runners
# ---------------------------------------------------------------------------
async def run_l1(client, endpoint, adapter):
    log.info("--- L1: FORMAT ---")
    results = []
    for p in GAME_FORMAT_PROMPTS:
        msgs = [
            {"role": "system", "content": GAME_SYSTEM},
            {"role": "user", "content": p["prompt"]},
        ]
        resp = await chat(client, endpoint, msgs, GAME_TOOLS, adapter)
        tool, _, err = extract_tool(resp)
        expected = p["expected"]
        alt = p.get("alt", "")
        passed = tool == expected or (alt and tool == alt)
        results.append({
            "id": p["id"], "level": p["level"], "prompt": p["prompt"],
            "expected": expected, "tool": tool or "NONE",
            "pass": passed, "error": err,
            "latency_ms": resp.get("_latency_ms", 0),
        })
        log.info(f"  {p['id']} [{'PASS' if passed else 'FAIL'}] {p['prompt'][:45]} -> {tool or 'NONE'}")
    return results


async def run_l2(client, endpoint, adapter):
    log.info("--- L2: SCAFFOLD SELECTION ---")
    results = []
    for p in GAME_SCAFFOLD_PROMPTS:
        msgs = [
            {"role": "system", "content": GAME_SYSTEM},
            {"role": "user", "content": p["prompt"]},
        ]
        resp = await chat(client, endpoint, msgs, GAME_TOOLS, adapter)
        tool, args, err = extract_tool(resp)
        passed = tool == "project_init"
        results.append({
            "id": p["id"], "prompt": p["prompt"],
            "status": "PASS" if passed else "FAIL",
            "expected": "project_init", "got_tool": tool or "NONE",
            "project_name": args.get("name", "") if isinstance(args, dict) else "",
            "reason": err if not passed else "",
            "latency_ms": resp.get("_latency_ms", 0),
        })
        log.info(f"  {p['id']} [{'PASS' if passed else 'FAIL'}] {p['prompt'][:45]} -> {tool or 'NONE'}")
    return results


async def run_l3(client, endpoint, adapter):
    log.info("--- L3: ERROR RECOVERY ---")
    results = []
    for sc in GAME_ERROR_SCENARIOS:
        resp = await chat(client, endpoint, sc["messages"], GAME_TOOLS, adapter, timeout=120)
        tool, args, err = extract_tool(resp)
        passed = tool == sc["expected_tool"]
        bad_retry = tool in sc.get("reject_tools", [])
        results.append({
            "id": sc["id"], "name": sc["name"],
            "expected_tool": sc["expected_tool"], "actual_tool": tool or "NONE",
            "status": "PASS" if passed else "FAIL",
            "bad_retry": bad_retry,
            "reason": err if not passed else "",
            "latency_ms": resp.get("_latency_ms", 0),
        })
        log.info(f"  {sc['id']} [{'PASS' if passed else 'FAIL'}] {sc['name']} -> {tool or 'NONE'}")
    return results


async def run_l4(client, endpoint, adapter):
    log.info("--- L4: HACK-FREE ---")
    results = []
    for sc in GAME_HACK_SCENARIOS:
        resp = await chat(client, endpoint, sc["messages"], GAME_TOOLS, adapter, timeout=120)
        tool, args, err = extract_tool(resp)
        passed = tool == sc["expected_tool"]
        content_fail = ""
        if passed and "content_checks" in sc:
            content = ""
            if isinstance(args, dict):
                content = args.get("content", "")
            for req in sc["content_checks"].get("contains", []):
                if req not in content:
                    content_fail = f"missing '{req}' in content"
                    passed = False
                    break
            # contains_any: at least one of the alternatives must be present
            if passed:
                opts = sc["content_checks"].get("contains_any", [])
                if opts and not any(o in content for o in opts):
                    content_fail = f"missing all of {opts!r} in content"
                    passed = False
            if passed:
                for forb in sc["content_checks"].get("not_contains", []):
                    if forb in content:
                        content_fail = f"forbidden '{forb}' in content"
                        passed = False
                        break
        actual_display = (tool or "NONE") + (f"(fail:{content_fail})" if content_fail else "")
        results.append({
            "id": sc["id"], "hack": sc["hack"], "desc": sc["desc"],
            "expected": sc["expected_tool"], "actual": actual_display,
            "status": "PASS" if passed else "FAIL",
            "reason": content_fail or (err if not passed else ""),
            "latency_ms": resp.get("_latency_ms", 0),
        })
        log.info(f"  {sc['id']} [{'PASS' if passed else 'FAIL'}] {sc['hack']} -> {actual_display}")
    return results


def score_l1(r):
    p = sum(1 for x in r if x["pass"])
    n = len(r)
    return {"passed": p, "total": n, "points": p * 5, "max_points": n * 5,
            "pct": f"{100*p//n}%" if n else "0%",
            "valid_name": sum(1 for x in r if x["tool"] not in ["", "NONE"])}

def score_l2(r):
    p = sum(1 for x in r if x["status"] == "PASS")
    n = len(r)
    return {"passed": p, "total": n, "points": p * 2, "max_points": n * 2,
            "pct": f"{100*p//n}%" if n else "0%"}

def score_l3(r):
    p = sum(1 for x in r if x["status"] == "PASS")
    n = len(r)
    return {"passed": p, "total": n, "points": p * 17, "max_points": n * 17,
            "pct": f"{100*p//n}%" if n else "0%"}

def score_l4(r):
    p = sum(1 for x in r if x["status"] == "PASS")
    n = len(r)
    return {"passed": p, "total": n, "points": p * 10, "max_points": n * 10,
            "pct": f"{100*p//n}%" if n else "0%",
            "still_needs_hacks": [x["hack"] for x in r if x["status"] == "FAIL"]}


def generate_md(report, l1, l2, l3, l4):
    lines = []
    w = lines.append
    w(f"# Gamedev Adapter Eval — {report['timestamp']}")
    w(f"**Adapter**: `{report.get('adapter','?')}` | **Endpoint**: {report.get('endpoint','?')} | **Elapsed**: {report.get('elapsed_s',0):.0f}s")
    w(f"")
    w(f"## Scoreboard")
    w(f"")
    w(f"| Layer | Score | Points | Max | Pct |")
    w(f"|-------|-------|--------|-----|-----|")
    total_pts, total_max = 0, 0
    for name, key in [("L1 Format","format"),("L2 Scaffold","scaffold"),
                       ("L3 Recovery","recovery"),("L4 Hack-Free","hackfree")]:
        d = report.get(key)
        if not d: continue
        total_pts += d["points"]; total_max += d["max_points"]
        w(f"| {name} | {d['passed']}/{d['total']} | {d['points']} | {d['max_points']} | {d['pct']} |")
    w(f"| **TOTAL** | | **{total_pts}** | **{total_max}** | **{100*total_pts//total_max if total_max else 0}%** |")
    w(f"")

    if l1:
        w(f"## L1: Format"); w(f"")
        w(f"| ID | Level | Prompt | Pass | Got | Expected |")
        w(f"|----|-------|--------|------|-----|----------|")
        for r in l1:
            w(f"| {r['id']} | {r['level']} | {r['prompt'][:40]} | {'✓' if r['pass'] else '✗'} | `{r['tool']}` | `{r['expected']}` |")
        w(f"")

    if l2:
        w(f"## L2: Scaffold Selection"); w(f"")
        w(f"| ID | Prompt | Pass | Got | Name |")
        w(f"|----|--------|------|-----|------|")
        for r in l2:
            w(f"| {r['id']} | {r['prompt'][:40]} | {'✓' if r['status']=='PASS' else '✗'} | `{r['got_tool']}` | `{r.get('project_name','')}` |")
        w(f"")

    if l3:
        w(f"## L3: Error Recovery"); w(f"")
        w(f"| ID | Scenario | Pass | Expected | Got |")
        w(f"|----|----------|------|----------|-----|")
        for r in l3:
            w(f"| {r['id']} | {r['name']} | {'✓' if r['status']=='PASS' else '✗'} | `{r['expected_tool']}` | `{r['actual_tool']}` |")
        w(f"")

    if l4:
        w(f"## L4: Hack-Free"); w(f"")
        w(f"| ID | Hack | Pass | Expected | Got |")
        w(f"|----|------|------|----------|-----|")
        for r in l4:
            w(f"| {r['id']} | {r['hack']} | {'✓' if r['status']=='PASS' else '✗'} | `{r['expected']}` | `{r['actual']}` |")
        still = report["hackfree"].get("still_needs_hacks", [])
        if still:
            w(f""); w(f"**Still needs hacks**: " + ", ".join(still))
        w(f"")

    # Training signals
    signals = []
    if l1:
        for r in l1:
            if not r["pass"]:
                signals.append(f"L1 {r['id']}: `{r['prompt'][:40]}` got `{r['tool']}` expected `{r['expected']}`")
    if l3:
        for r in l3:
            if r["status"] == "FAIL":
                signals.append(f"L3 {r['id']} {r['name']}: add training example for this recovery pattern")
    if l4:
        for r in l4:
            if r["status"] == "FAIL":
                signals.append(f"L4 {r['id']} {r['hack']}: add training example — {r['desc']}")
    if signals:
        w(f"## Training Data Signals"); w(f"")
        for s in signals: w(f"- {s}")
        w(f"")

    w(f"---"); w(f"*eval_gamedev.py — Curator*")
    return "\n".join(lines)


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", default="http://localhost:8090")
    parser.add_argument("--adapter", default="gamedev")
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--output", default=None)
    parser.add_argument("--no-adapter", action="store_true")
    args = parser.parse_args()

    adapter = None if args.no_adapter else args.adapter
    ts = time.strftime("%Y-%m-%d_%H%M%S")
    out_json = args.output or f"workspace/training_data/eval_report_gamedev_{ts}.json"
    out_md = out_json.replace(".json", ".md")

    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "endpoint": args.endpoint,
        "adapter": adapter or "base",
        "layers_run": ["format", "scaffold", "recovery", "hackfree"],
    }

    t0 = time.monotonic()
    async with httpx.AsyncClient() as client:
        l1 = await run_l1(client, args.endpoint, adapter)
        l2 = await run_l2(client, args.endpoint, adapter)
        l3 = await run_l3(client, args.endpoint, adapter)
        l4 = await run_l4(client, args.endpoint, adapter)

    report["format"] = score_l1(l1)
    report["scaffold"] = score_l2(l2)
    report["recovery"] = score_l3(l3)
    report["hackfree"] = score_l4(l4)
    report["elapsed_s"] = time.monotonic() - t0

    total_pts = sum(report[k]["points"] for k in ["format","scaffold","recovery","hackfree"])
    total_max = sum(report[k]["max_points"] for k in ["format","scaffold","recovery","hackfree"])
    report["total_points"] = total_pts
    report["total_max"] = total_max

    print(f"\n{'='*60}")
    print(f"  GAMEDEV EVAL — adapter={adapter or 'base'}")
    print(f"  L1 Format:   {report['format']['passed']}/{report['format']['total']} ({report['format']['pct']})")
    print(f"  L2 Scaffold: {report['scaffold']['passed']}/{report['scaffold']['total']} ({report['scaffold']['pct']})")
    print(f"  L3 Recovery: {report['recovery']['passed']}/{report['recovery']['total']} ({report['recovery']['pct']})")
    print(f"  L4 Hack-Free:{report['hackfree']['passed']}/{report['hackfree']['total']} ({report['hackfree']['pct']})")
    print(f"  TOTAL: {total_pts}/{total_max} pts in {report['elapsed_s']:.0f}s")
    print(f"{'='*60}\n")

    Path(out_json).parent.mkdir(parents=True, exist_ok=True)
    with open(out_json, "w") as f:
        json.dump({"report": report, "format": l1, "scaffold": l2,
                   "recovery": l3, "hackfree": l4}, f, indent=2)

    with open(out_md, "w") as f:
        f.write(generate_md(report, l1, l2, l3, l4))

    log.info(f"Saved: {out_json}")
    log.info(f"Saved: {out_md}")
    return report


if __name__ == "__main__":
    asyncio.run(main())
