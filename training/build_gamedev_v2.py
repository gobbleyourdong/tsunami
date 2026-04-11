#!/usr/bin/env python3
"""Gamedev training data — tokenizer-based pipeline (matches v89 app-builder).

Reads game code from training/gamedev_examples/*.ts and builds training JSONL
using tokenizer.apply_chat_template() for proper Gemma-4 format.

14 games + 3 error recovery = 17 examples.
Uses gamedev-specific SYSTEM_TEXT and TOOLS (game scaffold, main.ts, engine API).

Usage:
  python training/build_gamedev_v2.py
  # Outputs: workspace/training_data/gamedev_toolcall_train_v2.jsonl
"""
import json
import os
import sys
from pathlib import Path

from transformers import AutoTokenizer

MODEL = "google/gemma-4-e4b-it"
OUT_PATH = "workspace/training_data/gamedev_toolcall_train_v2.jsonl"
EXAMPLES_DIR = Path(__file__).parent / "gamedev_examples"

SYSTEM_TEXT = """You are Tsunami. You are the wave. You build games by calling tools.

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
3. shell_exec("cd deliverables/{name} && npx vite build") -- run the break
4. IF reef: fix directly -- file_edit for syntax, shell_exec for missing modules
5. undertow(dist/index.html) -- QA before delivery
6. message_result -- land the wave

## Engine API (import from '@engine/...')

Input: KeyboardInput, ActionMap -- bind keys, detect press/hold/release
Systems: ScoreSystem(comboThreshold), HealthSystem(max), CheckpointSystem
Flow: SceneManager, GameFlow, DifficultyManager, TutorialSystem
Renderer: FrameLoop -- onUpdate(stats) gives dt, use requestAnimationFrame pattern
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

TOOLS = [
    {"type": "function", "function": {
        "name": "project_init",
        "description": "Create a game project from the scaffold library.",
        "parameters": {"type": "OBJECT", "properties": {
            "name": {"description": "Project name", "type": "STRING"},
        }, "required": ["name"]},
    }},
    {"type": "function", "function": {
        "name": "file_write",
        "description": "Create or overwrite a file with full content.",
        "parameters": {"type": "OBJECT", "properties": {
            "path": {"description": "Path to write to", "type": "STRING"},
            "content": {"description": "Full file content", "type": "STRING"},
        }, "required": ["path", "content"]},
    }},
    {"type": "function", "function": {
        "name": "file_read",
        "description": "Read text content from a file.",
        "parameters": {"type": "OBJECT", "properties": {
            "path": {"description": "Path to the file to read", "type": "STRING"},
        }, "required": ["path"]},
    }},
    {"type": "function", "function": {
        "name": "file_edit",
        "description": "Make targeted modifications to an existing file.",
        "parameters": {"type": "OBJECT", "properties": {
            "path": {"description": "Path to the file", "type": "STRING"},
            "old_text": {"description": "Exact text to find and replace", "type": "STRING"},
            "new_text": {"description": "Replacement text", "type": "STRING"},
        }, "required": ["path", "old_text", "new_text"]},
    }},
    {"type": "function", "function": {
        "name": "shell_exec",
        "description": "Run a shell command and return its output.",
        "parameters": {"type": "OBJECT", "properties": {
            "command": {"description": "Command to run", "type": "STRING"},
        }, "required": ["command"]},
    }},
    {"type": "function", "function": {
        "name": "undertow",
        "description": "QA -- test an HTML file by screenshot. Always run before delivery.",
        "parameters": {"type": "OBJECT", "properties": {
            "path": {"description": "Path to HTML file", "type": "STRING"},
            "expect": {"description": "What the game should look like", "type": "STRING"},
        }, "required": ["path"]},
    }},
    {"type": "function", "function": {
        "name": "message_result",
        "description": "Deliver final outcome and end the task.",
        "parameters": {"type": "OBJECT", "properties": {
            "text": {"description": "Final result to deliver", "type": "STRING"},
        }, "required": []},
    }},
    {"type": "function", "function": {
        "name": "message_chat",
        "description": "Talk to the user. done=true ends task.",
        "parameters": {"type": "OBJECT", "properties": {
            "text": {"description": "Message", "type": "STRING"},
            "done": {"description": "true=end, false=continue", "type": "BOOLEAN"},
        }, "required": ["text"]},
    }},
    {"type": "function", "function": {
        "name": "search_web",
        "description": "Search the web for information.",
        "parameters": {"type": "OBJECT", "properties": {
            "query": {"description": "Search query", "type": "STRING"},
        }, "required": ["query"]},
    }},
]


def build_messages(user_prompt, turns):
    """Build message list from user prompt and tool call turns."""
    messages = [
        {"role": "system", "content": SYSTEM_TEXT},
        {"role": "user", "content": user_prompt},
    ]
    for name, args, response in turns:
        messages.append({
            "role": "assistant",
            "content": "",
            "tool_calls": [{
                "type": "function",
                "function": {"name": name, "arguments": args},
            }],
        })
        messages.append({
            "role": "tool",
            "name": name,
            "content": (response[:500] if response else "OK"),
        })
    return messages


# Game definitions
SIMPLE_GAMES = [
    ("Build a snake game", "snake-game", "01_snake.ts",
     "Snake with WASD, food, score, game over"),
    ("Build a pong game", "pong-game", "02_pong.ts",
     "Pong with AI paddle, ball physics, score"),
    ("Build a flappy bird game", "flappy-bird", "04_flappy.ts",
     "Flappy with gravity, pipes, score, game over"),
    ("Build an asteroids game", "asteroids-game", "05_asteroids.ts",
     "Ship rotation, thrust, shooting, asteroid splitting"),
    ("Build a space invaders game", "space-invaders", "06_space_invaders.ts",
     "Alien grid, player ship, bullets, score, lives"),
    ("Build a platformer game", "platformer-game", "07_platformer.ts",
     "Character, gravity, platforms, jump, coins"),
    ("Build a missile command game", "missile-command", "08_missile_command.ts",
     "Cities, incoming missiles, player fires interceptors"),
    ("Build a whack-a-mole game", "whack-a-mole", "09_whack_a_mole.ts",
     "Grid of holes, moles pop up, click to score, timer"),
    ("Build a rhythm game", "rhythm-game", "10_rhythm.ts",
     "Notes fall, press key on beat, combo system, score"),
    ("Build a racing game", "racing-game", "14_racing.ts",
     "Top-down racing with AI traffic, score"),
]

MEDIUM_GAMES = [
    ("Build a tower defense game", "tower-defense", "12_tower_defense.ts",
     "Path, waves, towers, upgrades",
     "Property 'hp' does not exist on type 'never'",
     "let enemies: Enemy[]",
     "interface Enemy { x: number; y: number; hp: number }\nlet enemies: Enemy[]"),
    ("Build a top-down shooter", "top-down-shooter", "13_topdown_shooter.ts",
     "WASD move, mouse aim, enemies, health",
     "Cannot find name 'mouseX'",
     "let mouseX = W / 2, mouseY = 0",
     "let mouseX = W / 2, mouseY = H / 2"),
    ("Build an infinite runner", "infinite-runner", "15_infinite_runner.ts",
     "Auto-scroll, jump/duck, obstacles, speed",
     "'GRAVITY' is not defined",
     "vy += GRAVITY * dt",
     "const GRAVITY = 1400\nvy += GRAVITY * dt"),
    ("Build a match-3 puzzle game", "match-3-puzzle", "16_match3.ts",
     "Grid swap, match detection, cascade, combo",
     "Cannot find module '@engine/systems/score'",
     "from '@engine/systems/score'",
     "from '@engine/systems/score'"),
]

BARE_ERRORS = [
    {
        "initial_cmd": "cd deliverables/game && npx vite build",
        "error": "Cannot resolve '@engine/input/keyboard'. Did you mean '@engine/input'?",
        "fix_tool": "file_edit",
        "fix_args": {
            "path": "deliverables/game/src/main.ts",
            "old_text": "from '@engine/input/keyboard'",
            "new_text": "from '@engine/input'",
        },
    },
    {
        "initial_cmd": "cd deliverables/game && npx vite build",
        "error": "src/main.ts(63,1): Expected ')' but found '}'",
        "fix_tool": "file_edit",
        "fix_args": {
            "path": "deliverables/game/src/main.ts",
            "old_text": "))})",
            "new_text": "))\n  )",
        },
    },
    {
        "initial_cmd": "cd deliverables/game && npx vite build",
        "error": "'score' is not defined. Did you forget to declare it?",
        "fix_tool": "file_edit",
        "fix_args": {
            "path": "deliverables/game/src/main.ts",
            "old_text": "score.addKill()",
            "new_text": "const score = new ScoreSystem()\nscore.addKill()",
        },
    },
]


def build_simple_game(prompt, name, code, desc):
    turns = [
        ("project_init", {"name": name}, f"Created project deliverables/{name}"),
        ("file_write", {"path": "src/main.ts", "content": code}, "Wrote src/main.ts"),
        ("shell_exec", {"command": f"cd deliverables/{name} && npx vite build"},
         "vite v5.0.0 building... built in 65ms"),
        ("undertow", {"path": f"deliverables/{name}/dist/index.html", "expect": desc},
         "QA passed: canvas renders, game loop running"),
        ("message_result", {"text": f"Built {name}: {desc}."}, "Delivered."),
    ]
    return build_messages(prompt, turns)


def build_medium_game(prompt, name, code, desc, error, old_text, new_text):
    turns = [
        ("project_init", {"name": name}, f"Created project deliverables/{name}"),
        ("file_write", {"path": "src/main.ts", "content": code}, "Wrote src/main.ts"),
        ("shell_exec", {"command": f"cd deliverables/{name} && npx vite build"},
         f"Build failed: {error}"),
        ("file_edit", {
            "path": f"deliverables/{name}/src/main.ts",
            "old_text": old_text, "new_text": new_text,
        }, "OK"),
        ("shell_exec", {"command": f"cd deliverables/{name} && npx vite build"},
         "vite v5.0.0 building... built in 68ms"),
        ("undertow", {"path": f"deliverables/{name}/dist/index.html", "expect": desc},
         "QA passed: canvas renders, game loop running"),
        ("message_result", {"text": f"Built {name}: {desc}. Fixed build error."},
         "Delivered."),
    ]
    return build_messages(prompt, turns)


def bare_error(initial_cmd, error, fix_tool, fix_args):
    return [
        {"role": "system", "content": SYSTEM_TEXT},
        {"role": "user", "content": "The build just failed. Fix it."},
        {"role": "assistant", "content": "", "tool_calls": [{
            "type": "function",
            "function": {"name": "shell_exec", "arguments": {"command": initial_cmd}},
        }]},
        {"role": "tool", "name": "shell_exec",
         "content": f"[shell_exec] Error: {error}"[:500]},
        {"role": "assistant", "content": "", "tool_calls": [{
            "type": "function",
            "function": {"name": fix_tool, "arguments": fix_args},
        }]},
    ]


def main():
    print(f"Loading: {MODEL}")
    tokenizer = AutoTokenizer.from_pretrained(MODEL, trust_remote_code=True)

    examples = []

    # Simple games (10)
    for prompt, name, filename, desc in SIMPLE_GAMES:
        path = EXAMPLES_DIR / filename
        if not path.exists():
            print(f"  SKIP {filename}")
            continue
        code = path.read_text()
        msgs = build_simple_game(prompt, name, code, desc)
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})
        print(f"  [simple] {name} ({len(code)} chars)")

    # Medium games with error recovery (4)
    for prompt, name, filename, desc, error, old, new in MEDIUM_GAMES:
        path = EXAMPLES_DIR / filename
        if not path.exists():
            print(f"  SKIP {filename}")
            continue
        code = path.read_text()
        msgs = build_medium_game(prompt, name, code, desc, error, old, new)
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})
        print(f"  [medium] {name} ({len(code)} chars)")

    # Bare error recovery (3)
    for sc in BARE_ERRORS:
        msgs = bare_error(sc["initial_cmd"], sc["error"], sc["fix_tool"], sc["fix_args"])
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})
        print(f"  [error]  {sc['error'][:50]}")

    # Summary
    print(f"\nTotal: {len(examples)} examples")
    print(f"  {len(SIMPLE_GAMES)} simple games (happy path)")
    print(f"  {len(MEDIUM_GAMES)} medium games (with error recovery)")
    print(f"  {len(BARE_ERRORS)} bare error recovery")

    starts_bos = sum(1 for ex in examples if ex["text"].startswith("<bos>"))
    print(f"Starts with <bos>: {starts_bos}/{len(examples)}")

    os.makedirs(os.path.dirname(OUT_PATH) if os.path.dirname(OUT_PATH) else ".", exist_ok=True)
    with open(OUT_PATH, "w") as f:
        for ex in examples:
            f.write(json.dumps(ex) + "\n")
    print(f"\nWrote {len(examples)} examples to {OUT_PATH}")


if __name__ == "__main__":
    main()
