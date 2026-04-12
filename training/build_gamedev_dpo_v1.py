#!/usr/bin/env python3
"""Gamedev DPO pairs v1 — targeting L4 Hack-Free failures from eval_gamedev.py baseline.

Baseline (2026-04-12): L4 3/10. Failures likely at:
  GHF02: Research gate — visual clone -> search_web first (not project_init)
  GHF03: Stall detection — after 2 reads -> file_write (not another read)
  GHF05: Shell loop — after 2 identical failures -> file_write (not shell_exec)
  GHF07: Engine imports — file_write must use tsunami-engine (not React)
  GHF08: Canvas 2D — file_write must use canvas API (not DOM divs)
  GHF09: Complex planning — complex multi-system game -> plan_update (not project_init)
  GHF10: QA before delivery — after successful build -> undertow (not message_result)

3 DPO pairs per pattern = 21 pairs total.

Usage:
  python training/build_gamedev_dpo_v1.py
  Output: workspace/training_data/gamedev_dpo_v1.jsonl
"""
import json
from datetime import date
from pathlib import Path

print("Loading tokenizer (google/gemma-4-e4b-it)...")
from transformers import AutoTokenizer
tokenizer = AutoTokenizer.from_pretrained("google/gemma-4-e4b-it", trust_remote_code=True)
print("Tokenizer loaded.")

TODAY = date.today().isoformat()

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
4. IF ERROR: fix directly (file_edit or shell_exec install)
5. undertow("deliverables/{name}/dist/index.html") -- QA verify
6. message_result -- land the wave

## IMPORTANT

- Visual clones ('looks like X', 'style of Y') -> search_web FIRST for reference visuals
- Complex multi-system games (5+ distinct systems) -> plan_update FIRST
- game code MUST use tsunami-engine imports: import { FrameLoop, KeyboardInput, ... } from 'tsunami-engine'
- Rendering MUST use Canvas 2D (ctx.fillRect, ctx.drawImage) -- NOT DOM div manipulation
- NEVER deliver without undertow QA
- npm run build after EVERY file write. One tool call per response."""

TOOLS = [
    {"type": "function", "function": {"name": "project_init", "description": "Scaffold a game project.", "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}},
    {"type": "function", "function": {"name": "file_write", "description": "Write a file with full content.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "file_edit", "description": "Make targeted modifications.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]}}},
    {"type": "function", "function": {"name": "shell_exec", "description": "Run a shell command.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
    {"type": "function", "function": {"name": "message_result", "description": "Deliver final outcome.", "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": []}}},
    {"type": "function", "function": {"name": "message_chat", "description": "Talk to the user.", "parameters": {"type": "object", "properties": {"text": {"type": "string"}, "done": {"type": "boolean"}}, "required": ["text"]}}},
    {"type": "function", "function": {"name": "search_web", "description": "Search the web for references.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "plan_update", "description": "Create or revise the task plan.", "parameters": {"type": "object", "properties": {"goal": {"type": "string"}, "phases": {"type": "array"}}, "required": ["goal", "phases"]}}},
    {"type": "function", "function": {"name": "undertow", "description": "QA test an HTML file in headless browser.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "file_read", "description": "Read a file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
]


def make_pair(messages, chosen_fn, chosen_args, rejected_fn, rejected_args, source_bug, note=""):
    prompt_text = tokenizer.apply_chat_template(
        messages, tools=TOOLS, tokenize=False, add_generation_prompt=True
    )
    chosen_msg = [{"role": "assistant", "content": "", "tool_calls": [
        {"id": "dpo_c", "type": "function", "function": {"name": chosen_fn, "arguments": json.dumps(chosen_args)}}
    ]}]
    chosen_text = tokenizer.apply_chat_template(messages + chosen_msg, tools=TOOLS, tokenize=False)
    chosen_response = chosen_text[len(prompt_text):]

    rejected_msg = [{"role": "assistant", "content": "", "tool_calls": [
        {"id": "dpo_r", "type": "function", "function": {"name": rejected_fn, "arguments": json.dumps(rejected_args)}}
    ]}]
    rejected_text = tokenizer.apply_chat_template(messages + rejected_msg, tools=TOOLS, tokenize=False)
    rejected_response = rejected_text[len(prompt_text):]

    return {
        "prompt": prompt_text,
        "chosen": chosen_response,
        "rejected": rejected_response,
        "images": [],
        "source_bug": source_bug,
        "note": note,
        "date": TODAY,
    }


PAIRS = []

# ─────────────────────────────────────────────────────────────────────────────
# GHF02: Research gate -- visual clone -> search_web FIRST (not project_init)
# ─────────────────────────────────────────────────────────────────────────────
for i, (user_msg, search_q) in enumerate([
    (
        "Build a game that looks exactly like Celeste (the pixel-art platformer with dashing and wall-jumping)",
        "Celeste game mechanics dash wall-jump pixel art sprites",
    ),
    (
        "Create a game styled like Stardew Valley -- farming simulation with top-down pixel art",
        "Stardew Valley UI style farming simulation pixel art layout",
    ),
    (
        "Make a game inspired by Geometry Dash -- auto-scrolling rhythm platformer",
        "Geometry Dash level art style rhythm platformer auto-scroll visual reference",
    ),
]):
    msgs = [
        {"role": "system", "content": GAME_SYSTEM},
        {"role": "user", "content": user_msg},
    ]
    PAIRS.append(make_pair(
        msgs,
        chosen_fn="search_web", chosen_args={"query": search_q},
        rejected_fn="project_init", rejected_args={"name": "visual-clone"},
        source_bug="GHF02-research-gate",
        note=f"research-{i+1}: visual clone -> search first, not project_init",
    ))

# ─────────────────────────────────────────────────────────────────────────────
# GHF03: Stall detection -- after 2 file_reads -> file_write (not a 3rd read)
# ─────────────────────────────────────────────────────────────────────────────
for i, (game, file1, file2) in enumerate([
    ("breakout", "deliverables/breakout/src/main.ts", "deliverables/breakout/package.json"),
    ("asteroids", "deliverables/asteroids/tsconfig.json", "deliverables/asteroids/vite.config.ts"),
    ("flappy-bird", "deliverables/flappy-bird/src/main.ts", "deliverables/flappy-bird/package.json"),
]):
    msgs = [
        {"role": "system", "content": GAME_SYSTEM},
        {"role": "user", "content": f"Build a {game} game"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c1", "type": "function", "function": {
                "name": "project_init", "arguments": json.dumps({"name": game})}}
        ]},
        {"role": "tool", "tool_call_id": "c1",
         "content": f"[project_init] Created game project '{game}'. Write src/main.ts."},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c2", "type": "function", "function": {
                "name": "file_read", "arguments": json.dumps({"path": file1})}}
        ]},
        {"role": "tool", "tool_call_id": "c2",
         "content": f"[file_read] // stub content of {file1.split('/')[-1]}"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c3", "type": "function", "function": {
                "name": "file_read", "arguments": json.dumps({"path": file2})}}
        ]},
        {"role": "tool", "tool_call_id": "c3",
         "content": f"[file_read] // stub content of {file2.split('/')[-1]}"},
    ]
    PAIRS.append(make_pair(
        msgs,
        chosen_fn="file_write",
        chosen_args={"path": f"deliverables/{game}/src/main.ts",
                     "content": "import { FrameLoop, KeyboardInput } from 'tsunami-engine';\n// game implementation"},
        rejected_fn="file_read",
        rejected_args={"path": f"deliverables/{game}/node_modules/.package-lock.json"},
        source_bug="GHF03-stall-game",
        note=f"stall-game-{i+1}: after 2 reads in game context, must file_write next",
    ))

# ─────────────────────────────────────────────────────────────────────────────
# GHF05: Shell loop -- after 2 identical build failures -> file_write (not shell again)
# ─────────────────────────────────────────────────────────────────────────────
for i, (game, error_msg, missing_file) in enumerate([
    (
        "platformer",
        "[shell_exec] Error: Cannot find module './components/Player'",
        "deliverables/platformer/src/components/Player.ts",
    ),
    (
        "space-shooter",
        "[shell_exec] Error: Cannot find module './entities/Bullet'",
        "deliverables/space-shooter/src/entities/Bullet.ts",
    ),
    (
        "dungeon-crawler",
        "[shell_exec] Error: Cannot find module './systems/Combat'",
        "deliverables/dungeon-crawler/src/systems/Combat.ts",
    ),
]):
    msgs = [
        {"role": "system", "content": GAME_SYSTEM},
        {"role": "user", "content": f"The build fails with a missing module error in my {game} game"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c1", "type": "function", "function": {
                "name": "shell_exec",
                "arguments": json.dumps({"command": f"cd deliverables/{game} && npm run build"})}}
        ]},
        {"role": "tool", "tool_call_id": "c1", "content": error_msg},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c2", "type": "function", "function": {
                "name": "shell_exec",
                "arguments": json.dumps({"command": f"cd deliverables/{game} && npm run build"})}}
        ]},
        {"role": "tool", "tool_call_id": "c2", "content": error_msg},
    ]
    PAIRS.append(make_pair(
        msgs,
        chosen_fn="file_write",
        chosen_args={"path": missing_file,
                     "content": "import { Sprite } from 'tsunami-engine';\nexport class Player { }"},
        rejected_fn="shell_exec",
        rejected_args={"command": f"cd deliverables/{game} && npm run build"},
        source_bug="GHF05-shell-loop",
        note=f"shell-loop-{i+1}: 2 identical build failures -> create missing file, not retry shell",
    ))

# ─────────────────────────────────────────────────────────────────────────────
# GHF07: Engine imports -- file_write MUST use tsunami-engine (not React/plain JS)
# ─────────────────────────────────────────────────────────────────────────────
TSUNAMI_ENGINE_CONTENT = (
    "import { FrameLoop, KeyboardInput, Sprite, AudioManager } from 'tsunami-engine';\n\n"
    "const loop = new FrameLoop();\n"
    "const keys = new KeyboardInput();\n\n"
    "loop.start((dt: number) => {\n"
    "  // game logic here\n"
    "});\n"
)

REACT_CONTENT = (
    "import React, { useState, useEffect, useRef } from 'react';\n\n"
    "export default function Game() {\n"
    "  const canvasRef = useRef<HTMLCanvasElement>(null);\n"
    "  useEffect(() => { /* render loop */ }, []);\n"
    "  return <canvas ref={canvasRef} />;\n"
    "}\n"
)

for i, (game, project_name) in enumerate([
    ("snake", "snake"),
    ("tetris", "tetris"),
    ("pong", "pong"),
]):
    msgs = [
        {"role": "system", "content": GAME_SYSTEM},
        {"role": "user", "content": f"Build a {game} game"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c1", "type": "function", "function": {
                "name": "project_init", "arguments": json.dumps({"name": project_name})}}
        ]},
        {"role": "tool", "tool_call_id": "c1",
         "content": f"[project_init] Created game project '{project_name}'. Write src/main.ts using tsunami-engine."},
    ]
    PAIRS.append(make_pair(
        msgs,
        chosen_fn="file_write",
        chosen_args={"path": f"deliverables/{project_name}/src/main.ts",
                     "content": TSUNAMI_ENGINE_CONTENT},
        rejected_fn="file_write",
        rejected_args={"path": f"deliverables/{project_name}/src/App.tsx",
                       "content": REACT_CONTENT},
        source_bug="GHF07-engine-imports",
        note=f"engine-imports-{i+1}: must import from tsunami-engine, NOT React hooks/components",
    ))

# ─────────────────────────────────────────────────────────────────────────────
# GHF08: Canvas 2D -- rendering MUST use canvas API (not DOM div manipulation)
# ─────────────────────────────────────────────────────────────────────────────
CANVAS_CONTENT = (
    "import { FrameLoop } from 'tsunami-engine';\n"
    "const canvas = document.querySelector<HTMLCanvasElement>('#game')!;\n"
    "const ctx = canvas.getContext('2d')!;\n"
    "const loop = new FrameLoop();\n"
    "loop.start(() => {\n"
    "  ctx.clearRect(0, 0, canvas.width, canvas.height);\n"
    "  ctx.fillStyle = '#0f0';\n"
    "  ctx.fillRect(playerX, playerY, 20, 20);\n"
    "});\n"
)

DOM_CONTENT = (
    "const gameDiv = document.getElementById('game')!;\n"
    "const playerEl = document.createElement('div');\n"
    "playerEl.style.cssText = 'position:absolute;width:20px;height:20px;background:#0f0';\n"
    "gameDiv.appendChild(playerEl);\n\n"
    "function update() {\n"
    "  playerEl.style.left = playerX + 'px';\n"
    "  playerEl.style.top = playerY + 'px';\n"
    "  requestAnimationFrame(update);\n"
    "}\n"
    "update();\n"
)

for i, (game, project_name) in enumerate([
    ("snake game with a moving snake", "snake"),
    ("brick breaker game", "brick-breaker"),
    ("space invaders clone", "space-invaders"),
]):
    msgs = [
        {"role": "system", "content": GAME_SYSTEM},
        {"role": "user", "content": f"Build a {game}"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c1", "type": "function", "function": {
                "name": "project_init", "arguments": json.dumps({"name": project_name})}}
        ]},
        {"role": "tool", "tool_call_id": "c1",
         "content": f"[project_init] Created game project '{project_name}'. Write src/main.ts."},
    ]
    PAIRS.append(make_pair(
        msgs,
        chosen_fn="file_write",
        chosen_args={"path": f"deliverables/{project_name}/src/main.ts",
                     "content": CANVAS_CONTENT},
        rejected_fn="file_write",
        rejected_args={"path": f"deliverables/{project_name}/src/main.ts",
                       "content": DOM_CONTENT},
        source_bug="GHF08-canvas-2d",
        note=f"canvas-2d-{i+1}: use canvas ctx.fillRect, NOT DOM createElement/innerHTML",
    ))

# ─────────────────────────────────────────────────────────────────────────────
# GHF09: Complex game planning -- 5+ systems -> plan_update FIRST (not project_init)
# ─────────────────────────────────────────────────────────────────────────────
for i, user_msg in enumerate([
    "Build a full MMORPG with character classes, skill trees, inventory, crafting, dungeons, and a world map. Plan carefully before building.",
    "Create a city builder with resource management, population simulation, traffic routing, economy system, disaster events, and tech research tree.",
    "Build an RTS game with unit AI, fog of war, base building, resource gathering, tech tree, multiplayer networking, and replay system.",
]):
    msgs = [
        {"role": "system", "content": GAME_SYSTEM},
        {"role": "user", "content": user_msg},
    ]
    PAIRS.append(make_pair(
        msgs,
        chosen_fn="plan_update",
        chosen_args={"goal": "Design architecture for complex multi-system game",
                     "phases": ["Phase 1: Core engine loop", "Phase 2: Primary systems", "Phase 3: Integration"]},
        rejected_fn="project_init",
        rejected_args={"name": "complex-game"},
        source_bug="GHF09-complex-plan-game",
        note=f"complex-plan-game-{i+1}: 5+ distinct systems -> plan_update first, not project_init",
    ))

# ─────────────────────────────────────────────────────────────────────────────
# GHF10: QA before delivery -- after successful build -> undertow (not message_result)
# ─────────────────────────────────────────────────────────────────────────────
for i, (game, project_name) in enumerate([
    ("tetris", "tetris"),
    ("pacman", "pacman"),
    ("2048 puzzle", "2048"),
]):
    msgs = [
        {"role": "system", "content": GAME_SYSTEM},
        {"role": "user", "content": f"Build a {game} game"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c1", "type": "function", "function": {
                "name": "project_init", "arguments": json.dumps({"name": project_name})}}
        ]},
        {"role": "tool", "tool_call_id": "c1",
         "content": f"[project_init] Created game project '{project_name}'. Write src/main.ts."},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c2", "type": "function", "function": {
                "name": "file_write",
                "arguments": json.dumps({"path": f"deliverables/{project_name}/src/main.ts",
                                         "content": "import { FrameLoop } from 'tsunami-engine';\n// game"})}}
        ]},
        {"role": "tool", "tool_call_id": "c2",
         "content": f"[file_write] Written to deliverables/{project_name}/src/main.ts"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c3", "type": "function", "function": {
                "name": "shell_exec",
                "arguments": json.dumps({"command": f"cd deliverables/{project_name} && npm run build"})}}
        ]},
        {"role": "tool", "tool_call_id": "c3",
         "content": "[shell_exec] Build successful. dist/index.html ready."},
    ]
    PAIRS.append(make_pair(
        msgs,
        chosen_fn="undertow",
        chosen_args={"path": f"deliverables/{project_name}/dist/index.html"},
        rejected_fn="message_result",
        rejected_args={"text": f"{game} game delivered!"},
        source_bug="GHF10-qa-before-delivery",
        note=f"qa-delivery-{i+1}: after successful build -> undertow QA, not message_result",
    ))


# ─────────────────────────────────────────────────────────────────────────────
# Output
# ─────────────────────────────────────────────────────────────────────────────
output = Path("workspace/training_data/gamedev_dpo_v1.jsonl")
output.parent.mkdir(parents=True, exist_ok=True)
with open(output, "w") as f:
    for p in PAIRS:
        f.write(json.dumps(p) + "\n")

print(f"\nWrote {len(PAIRS)} DPO pairs to {output}")
print("\nPairs by pattern:")
from collections import Counter
by_bug = Counter(p["source_bug"] for p in PAIRS)
for bug, count in sorted(by_bug.items()):
    print(f"  {bug}: {count}")

print(f"\nTotal: {len(PAIRS)} pairs")
print(f"\nNote: gamedev DPO requires a merged gamedev-v4 base adapter.")
print(f"Train gamedev-v4 SFT first, then merge, then apply this DPO layer.")
