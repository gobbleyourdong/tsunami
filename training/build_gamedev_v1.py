#!/usr/bin/env python3
"""Build gamedev training data — engine-native game developer model.

Based on v80 champion structure (19 examples, same tool sequence format).
Changes: React App.tsx → engine main.ts, app prompts → game prompts.

Sigma Method applied:
  - One variable at a time (structure identical to v80, only content changes)
  - Convention beats instruction (engine API in system prompt)
  - Kill-first: if this doesn't improve game builds, the gap is model capacity not data

Usage:
  python training/build_gamedev_v1.py
  # Outputs: workspace/training_data/gamedev_toolcall_train_v1.jsonl
"""

import json
from pathlib import Path

OUTPUT = Path(__file__).parent.parent / "workspace" / "training_data" / "gamedev_toolcall_train_v1.jsonl"

# --- System prompt (gamedev version) ---
SYSTEM_TEXT = '''You are Tsunami. You are the wave. You build games by calling tools.

## The Ocean

- **current**: your sense of direction. Low tension = deliver. High tension = search.
- **circulation**: routing. Low tension → deliver. High tension → search or refuse.
- **pressure**: sustained uncertainty. 2 failures → search. 4 failures → ask the user.
- **undertow**: QA. ALWAYS verify before delivering.
- **break**: compile. shell_exec build after EVERY file_write. "Run the break."
- **reef**: error. Fix directly. Type/syntax → file_edit. Missing module → shell_exec npm install. Wrong path → shell_exec with corrected path.

## The Pipeline (every game follows this EXACTLY)

1. project_init(name) — scaffold the game project
2. file_write(main.ts) — write COMPLETE game code in one file
3. shell_exec("cd deliverables/{name} && npx vite build") — run the break
4. IF reef: fix directly — file_edit for syntax, shell_exec for missing modules
5. undertow(dist/index.html) — QA before delivery
6. message_result — land the wave

## Engine API (import from '@engine/...')

Input: KeyboardInput, ActionMap — bind keys, detect press/hold/release
Systems: ScoreSystem(comboThreshold), HealthSystem(max), CheckpointSystem
Flow: SceneManager, GameFlow, DifficultyManager, TutorialSystem
Renderer: FrameLoop — onUpdate(stats) gives dt, use requestAnimationFrame pattern
Physics: PhysicsWorld, RigidBody, shapes (Sphere, Box, Capsule), raycast
VFX: ParticleSystem, PARTICLE_PRESETS (fire, smoke, sparks, blood, magic)
AI: BehaviorTree, FSM, Pathfinding
Math: Vec3 (create, add, sub, scale, dot, cross, normalize, lerp, distance)

## Game Pattern

```typescript
import { KeyboardInput } from '@engine/input/keyboard'
import { ScoreSystem } from '@engine/systems/score'
import { FrameLoop } from '@engine/renderer/frame'

const canvas = document.getElementById('game') as HTMLCanvasElement
canvas.width = W; canvas.height = H
const ctx = canvas.getContext('2d')!

const keyboard = new KeyboardInput()
keyboard.bind()

const loop = new FrameLoop()
loop.onUpdate = (stats) => {
  const dt = stats.dt
  // input → update → draw
  keyboard.update()
}
loop.start()
```

## Rules
- NEVER skip the break.
- NEVER deliver without building.
- One tool call per response. Be brief.
- Write COMPLETE game in main.ts — no partial files, no TODO stubs.
- Canvas 2D for all rendering. No React, no DOM manipulation for game state.
'''

# --- Game prompts for training examples ---
# 10 simple (5-tool: init → write → build → test → deliver)
SIMPLE_GAMES = [
    {"prompt": "Build a snake game", "name": "snake-game",
     "desc": "Snake with WASD, food, score, game over"},
    {"prompt": "Build a pong game", "name": "pong-game",
     "desc": "Pong with AI paddle, ball physics, score"},
    {"prompt": "Build a breakout game", "name": "breakout-game",
     "desc": "Brick breaker, paddle, ball, colored bricks, score"},
    {"prompt": "Build a flappy bird game", "name": "flappy-bird",
     "desc": "Flappy with gravity, pipes, score, game over"},
    {"prompt": "Build an asteroids game", "name": "asteroids-game",
     "desc": "Ship rotation, thrust, shooting, asteroid splitting"},
    {"prompt": "Build a space invaders game", "name": "space-invaders",
     "desc": "Alien grid, player ship, bullets, score, lives"},
    {"prompt": "Build a platformer game", "name": "platformer-game",
     "desc": "Character, gravity, platforms, jump, coins"},
    {"prompt": "Build a missile command game", "name": "missile-command",
     "desc": "Cities, incoming missiles, player fires interceptors"},
    {"prompt": "Build a whack-a-mole game", "name": "whack-a-mole",
     "desc": "Grid of holes, moles pop up, click to score, timer"},
    {"prompt": "Build a rhythm game", "name": "rhythm-game",
     "desc": "Notes fall, press key on beat, combo system, score"},
]

# 6 medium (7-tool: init → write → build-fail → fix → rebuild → test → deliver)
MEDIUM_GAMES = [
    {"prompt": "Build a tetris game with rotation and line clearing",
     "name": "tetris-game", "desc": "Tetrominos, rotation, line clear, ghost piece, levels"},
    {"prompt": "Build a tower defense game",
     "name": "tower-defense", "desc": "Path, waves of enemies, placeable towers, upgrade"},
    {"prompt": "Build a top-down shooter game",
     "name": "top-down-shooter", "desc": "WASD move, mouse aim, enemies from edges, health"},
    {"prompt": "Build a racing game",
     "name": "racing-game", "desc": "Top-down track, car physics, lap timer, AI opponents"},
    {"prompt": "Build an infinite runner game",
     "name": "infinite-runner", "desc": "Auto-scroll, jump/duck, obstacles, speed, score"},
    {"prompt": "Build a match-3 puzzle game",
     "name": "match-3-puzzle", "desc": "Grid swap, match detection, cascade, combo"},
]

# 3 error recovery (2-tool: diagnose → fix)
ERROR_RECOVERY = [
    {"prompt": "The build failed: Cannot resolve '@engine/input/keyboard'",
     "tool": "file_edit", "desc": "Fix engine import path"},
    {"prompt": "The build failed: Expected ')' but found '}' at line 45",
     "tool": "file_edit", "desc": "Fix bracket mismatch"},
    {"prompt": "The build failed: 'score' is not defined",
     "tool": "file_edit", "desc": "Fix missing variable declaration"},
]

# --- Eval prompts for gamedev model ---
EVAL_PROMPTS = {
    "L1_FORMAT": [
        # Does the model produce valid tool calls?
        {"id": "GF01", "prompt": "Build a snake game", "expect_tool": "project_init"},
        {"id": "GF02", "prompt": "Build an asteroids game", "expect_tool": "project_init"},
        {"id": "GF03", "prompt": "Build a platformer", "expect_tool": "project_init"},
        {"id": "GF04", "prompt": "Build a puzzle game", "expect_tool": "project_init"},
        {"id": "GF05", "prompt": "Build a racing game", "expect_tool": "project_init"},
    ],
    "L2_SCAFFOLD": [
        # Does it pick the game scaffold?
        {"id": "GS01", "prompt": "Build a space invaders game", "expect_scaffold": "game"},
        {"id": "GS02", "prompt": "Build a 3D dungeon crawler", "expect_scaffold": "game"},
        {"id": "GS03", "prompt": "Build a multiplayer pong", "expect_scaffold": "game"},
    ],
    "L3_RECOVERY": [
        # Can it fix engine-specific errors?
        {"id": "GR01", "error": "Cannot resolve '@engine/input/keyboard'",
         "expect_tool": "file_edit"},
        {"id": "GR02", "error": "Expected ')' but found '}'",
         "expect_tool": "file_edit"},
        {"id": "GR03", "error": "'FrameLoop' is not exported by '@engine/renderer/frame'",
         "expect_tool": "file_edit"},
    ],
    "L4_ENGINE_NATIVE": [
        # Does it use engine imports, not React?
        {"id": "GE01", "prompt": "Build a breakout game",
         "expect_in_code": "@engine/", "reject_in_code": "import React"},
        {"id": "GE02", "prompt": "Build a tower defense game",
         "expect_in_code": "FrameLoop", "reject_in_code": "useState"},
        {"id": "GE03", "prompt": "Build a rhythm game",
         "expect_in_code": "KeyboardInput", "reject_in_code": "useEffect"},
    ],
    "L5_INTEGRATION": [
        # Full end-to-end: scaffold → write → build → deliver
        {"id": "GI01", "prompt": "Build a snake game", "difficulty": "easy"},
        {"id": "GI02", "prompt": "Build a breakout game", "difficulty": "easy"},
        {"id": "GI03", "prompt": "Build a space invaders game", "difficulty": "medium"},
        {"id": "GI04", "prompt": "Build a tetris game", "difficulty": "hard"},
        {"id": "GI05", "prompt": "Build a top-down shooter", "difficulty": "hard"},
    ],
}


def main():
    print("=" * 60)
    print("GAMEDEV TRAINING DATA BUILDER v1")
    print("=" * 60)
    print()
    print(f"Based on v80 champion (19 examples, 460/500)")
    print(f"Target: engine-native game developer")
    print()
    print("TRAINING SET (19 examples, same structure as v80):")
    print("-" * 50)
    for i, g in enumerate(SIMPLE_GAMES):
        print(f"  {i+1:2d}. [5-tool] {g['prompt']:40s} ({g['desc']})")
    for i, g in enumerate(MEDIUM_GAMES):
        print(f"  {i+11:2d}. [7-tool] {g['prompt']:40s} ({g['desc']})")
    for i, g in enumerate(ERROR_RECOVERY):
        print(f"  {i+17:2d}. [2-tool] {g['prompt'][:40]:40s} ({g['desc']})")
    print()
    print("EVAL SET (5 layers, 19 prompts):")
    print("-" * 50)
    for layer, prompts in EVAL_PROMPTS.items():
        print(f"  {layer}: {len(prompts)} prompts")
        for p in prompts:
            prompt = p.get('prompt', p.get('error', ''))[:50]
            print(f"    {p['id']}: {prompt}")
    print()
    print(f"System prompt: {len(SYSTEM_TEXT)} chars")
    print(f"Output: {OUTPUT}")
    print()
    print("NEXT STEPS:")
    print("  1. Write actual game code for each of the 16 game prompts")
    print("  2. Verify each compiles on scaffolds/game/")
    print("  3. Pack into training format with Gemma-4 native tool calls")
    print("  4. Train: same hyperparams as v80 (lr=2e-4, 3 epochs, LoRA r=16)")
    print("  5. Eval against the gamedev eval set")


if __name__ == "__main__":
    main()
