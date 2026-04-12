#!/usr/bin/env python3
"""Gamedev DPO pairs v2 -- targeting L1 failures on extreme/routing prompts.

Baseline (2026-04-12): L1 10/12. Failures at:
  GX01: "Build multiplayer battle royale" -> project_init (NOT message_chat)
  GX02: "Build 3D WebGPU dungeon crawler" -> project_init (NOT message_chat)

Also covers GR01/GR02 routing (prompts without "game" keyword) since those
were added after the baseline and may fail on older adapter.

3 DPO pairs per pattern = 12 pairs total.

Usage:
  python training/build_gamedev_dpo_v2.py
  Output: workspace/training_data/gamedev_dpo_v2.jsonl
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
- **undertow**: QA. ALWAYS verify before delivering.
- **break**: compile. shell_exec build after EVERY file_write.
- **reef**: error. Fix directly.

## The Pipeline (every game follows this EXACTLY)

1. project_init(name) -- scaffold the game project
2. file_write(src/main.ts) -- write COMPLETE game code in one file
3. shell_exec("cd deliverables/{name} && npm run build") -- run the break
4. undertow("deliverables/{name}/dist/index.html") -- QA verify
5. message_result -- land the wave

## IMPORTANT: Graceful Degradation

- Multiplayer games require server infrastructure -> build single-player first, note limitation.
- 3D/WebGPU games require advanced runtime -> build 2D canvas version first, note limitation.
- NEVER refuse to build. ALWAYS project_init. Degrade, don't refuse.
- WASD/keyboard/canvas prompts ARE game prompts even without the word "game".

One tool call per response. Be brief."""

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
# GX01: Multiplayer -> degrade to single-player + project_init (NOT message_chat)
# ─────────────────────────────────────────────────────────────────────────────
for i, user_msg in enumerate([
    "Build a multiplayer battle royale game in the browser",
    "Create a 2-player online chess game with matchmaking",
    "Build a real-time multiplayer shooter with rooms and lobbies",
]):
    msgs = [
        {"role": "system", "content": GAME_SYSTEM},
        {"role": "user", "content": user_msg},
    ]
    # Chosen: degrade + project_init (build single-player version)
    game_name = ["battle-royale", "chess", "shooter"][i]
    PAIRS.append(make_pair(
        msgs,
        chosen_fn="project_init",
        chosen_args={"name": game_name},
        rejected_fn="message_chat",
        rejected_args={"text": "Multiplayer games require server infrastructure which is not available in this environment. I cannot build a multiplayer game.", "done": False},
        source_bug="GX01-multiplayer-degrade",
        note=f"multiplayer-{i+1}: degrade to single-player + project_init, NOT message_chat refusal",
    ))

# ─────────────────────────────────────────────────────────────────────────────
# GX02: 3D/WebGPU -> degrade to 2D canvas + project_init (NOT message_chat)
# ─────────────────────────────────────────────────────────────────────────────
for i, user_msg in enumerate([
    "Build a 3D first-person dungeon crawler using WebGPU",
    "Create a 3D racing game with physics using Three.js",
    "Build a 3D city builder with WebGL rendering",
]):
    msgs = [
        {"role": "system", "content": GAME_SYSTEM},
        {"role": "user", "content": user_msg},
    ]
    game_name = ["dungeon-crawler", "racing", "city-builder"][i]
    PAIRS.append(make_pair(
        msgs,
        chosen_fn="project_init",
        chosen_args={"name": game_name},
        rejected_fn="message_chat",
        rejected_args={"text": "3D WebGPU games require advanced rendering infrastructure not available here.", "done": False},
        source_bug="GX02-3d-degrade",
        note=f"3d-degrade-{i+1}: degrade to 2D canvas + project_init, NOT message_chat refusal",
    ))

# ─────────────────────────────────────────────────────────────────────────────
# GR01/GR02: Routing — game prompts WITHOUT "game" keyword -> project_init
# ─────────────────────────────────────────────────────────────────────────────
for i, (user_msg, game_name) in enumerate([
    ("Build a walkable first-person 3D maze with WASD controls", "fps-maze"),
    ("Build an endless runner with obstacles and score tracking", "endless-runner"),
    ("Create a physics sandbox where you can drop objects and watch them bounce", "physics-sandbox"),
    ("Build a top-down shooter with WASD movement and spacebar to fire", "top-down-shooter"),
    ("Make a canvas-based simulation of bouncing balls with gravity", "bouncing-balls"),
    ("Build a tile-based dungeon with procedural room generation", "dungeon-gen"),
]):
    msgs = [
        {"role": "system", "content": GAME_SYSTEM},
        {"role": "user", "content": user_msg},
    ]
    PAIRS.append(make_pair(
        msgs,
        chosen_fn="project_init",
        chosen_args={"name": game_name},
        rejected_fn="message_chat",
        rejected_args={"text": "I'm not sure what kind of project you'd like me to build.", "done": False},
        source_bug="GR01-routing-no-game-word",
        note=f"routing-{i+1}: game prompt without 'game' keyword -> project_init, NOT message_chat",
    ))


# ─────────────────────────────────────────────────────────────────────────────
# Output
# ─────────────────────────────────────────────────────────────────────────────
output = Path("workspace/training_data/gamedev_dpo_v2.jsonl")
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

# Combine v1+v2 into gamedev_dpo_combined_v1.jsonl
v1_path = Path("workspace/training_data/gamedev_dpo_v1.jsonl")
combined_path = Path("workspace/training_data/gamedev_dpo_combined_v1.jsonl")
v1_lines = v1_path.read_text().splitlines()
v2_lines = [line for line in output.read_text().splitlines() if line.strip()]
with open(combined_path, "w") as f:
    for line in v1_lines + v2_lines:
        if line.strip():
            f.write(line + "\n")
total = len([l for l in v1_lines + v2_lines if l.strip()])
print(f"\nCombined: {total} pairs -> {combined_path}")
print(f"  v1: {len(v1_lines)} + v2: {len(v2_lines)} = {total}")
