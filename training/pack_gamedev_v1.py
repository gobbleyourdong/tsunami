#!/usr/bin/env python3
"""Pack gamedev training examples into Gemma-4 native tool call JSONL.

Reads game code from training/gamedev_examples/*.ts and produces
workspace/training_data/gamedev_toolcall_train_v1.jsonl

Format matches v80 exactly — only content changes (games vs apps, main.ts vs App.tsx).
"""

import json
from pathlib import Path

EXAMPLES_DIR = Path(__file__).parent / "gamedev_examples"
OUTPUT = Path(__file__).parent.parent / "workspace" / "training_data" / "gamedev_toolcall_train_v1.jsonl"

SYSTEM_PROMPT = '''You are Tsunami. You are the wave. You build games by calling tools.

The ocean:
- current: your sense of direction. If uncertain, search first.
- circulation: routing. Low tension=deliver. High tension=search or refuse.
- pressure: sustained uncertainty. 2 failures=search. 4 failures=ask the user.
- undertow: QA. ALWAYS verify before delivering.
- break: compile. shell_exec build after EVERY file_write.
- reef: error. Fix directly. Type/syntax -> file_edit. Missing module -> shell_exec npm install. Wrong path -> shell_exec with corrected path.

THE PIPELINE (every game follows this EXACTLY):
1. project_init(name) -- scaffold the game project
2. file_write(src/main.ts) -- write COMPLETE game code
3. shell_exec("cd deliverables/{name} && npx vite build") -- run the break
4. IF ERROR: fix directly -- file_edit (type/syntax fix), shell_exec (install module)
5. undertow(dist/index.html) -- QA before delivery
6. message_result -- land the wave

Engine API (import from '@engine/...'):
- KeyboardInput, ActionMap: input binding (WASD, arrows, space)
- ScoreSystem(comboAt): score + combo multiplier
- HealthSystem(max): HP + onDeath callback
- FrameLoop: loop.onUpdate = (stats) => { const dt = stats.dt; ... }
- Canvas: document.getElementById('game'), getContext('2d')

Game pattern: imports -> constants -> state -> keyboard.bind() -> canvas setup -> draw() -> loop.onUpdate -> loop.start()

NEVER skip the break. NEVER deliver without building. One tool call per response. Be brief.'''

TOOL_DECLS = ('<|tool>declaration:project_init{description:<|"|>Create a game project from scaffold.<|"|>,'
    'parameters:{properties:{name:{description:<|"|>Project name<|"|>,type:<|"|>STRING<|"|>}},'
    'required:[<|"|>name<|"|>],type:<|"|>OBJECT<|"|>}}<tool|>'
    '<|tool>declaration:file_write{description:<|"|>Create or overwrite a file.<|"|>,'
    'parameters:{properties:{content:{description:<|"|>Full file content<|"|>,type:<|"|>STRING<|"|>},'
    'path:{description:<|"|>Path to write<|"|>,type:<|"|>STRING<|"|>}},'
    'required:[<|"|>content<|"|>,<|"|>path<|"|>],type:<|"|>OBJECT<|"|>}}<tool|>'
    '<|tool>declaration:file_edit{description:<|"|>Replace text in a file.<|"|>,'
    'parameters:{properties:{new_text:{description:<|"|>Replacement<|"|>,type:<|"|>STRING<|"|>},'
    'old_text:{description:<|"|>Text to find<|"|>,type:<|"|>STRING<|"|>},'
    'path:{description:<|"|>File path<|"|>,type:<|"|>STRING<|"|>}},'
    'required:[<|"|>new_text<|"|>,<|"|>old_text<|"|>,<|"|>path<|"|>],type:<|"|>OBJECT<|"|>}}<tool|>'
    '<|tool>declaration:shell_exec{description:<|"|>Run a shell command.<|"|>,'
    'parameters:{properties:{command:{description:<|"|>Command to run<|"|>,type:<|"|>STRING<|"|>}},'
    'required:[<|"|>command<|"|>],type:<|"|>OBJECT<|"|>}}<tool|>'
    '<|tool>declaration:undertow{description:<|"|>QA test the built game.<|"|>,'
    'parameters:{properties:{expect:{description:<|"|>What to verify<|"|>,type:<|"|>STRING<|"|>},'
    'path:{description:<|"|>HTML path<|"|>,type:<|"|>STRING<|"|>}},'
    'required:[<|"|>path<|"|>],type:<|"|>OBJECT<|"|>}}<tool|>'
    '<|tool>declaration:message_result{description:<|"|>Deliver result to user.<|"|>,'
    'parameters:{properties:{text:{description:<|"|>Result message<|"|>,type:<|"|>STRING<|"|>}},'
    'required:[<|"|>text<|"|>],type:<|"|>OBJECT<|"|>}}<tool|>')


def esc(s):
    """Escape tool call arg content."""
    return s.replace('<|"|>', '<|"\\|>')


def simple(prompt, name, code, desc):
    c = esc(code)
    return '\n'.join([
        f'<bos><|turn>system\n{SYSTEM_PROMPT}{TOOL_DECLS}<turn|>',
        f'<|turn>user\n{prompt}<turn|>',
        f'<|turn>model\n<|tool_call>call:project_init{{name:<|"|>{name}<|"|>}}<tool_call|>Scaffolding.<turn|>',
        f'<|turn>tool\nCreated project deliverables/{name}<turn|>',
        f'<|turn>model\n<|tool_call>call:file_write{{content:<|"|>{c}<|"|>,path:<|"|>src/main.ts<|"|>}}<tool_call|>Writing game.<turn|>',
        f'<|turn>tool\nWrote src/main.ts<turn|>',
        f'<|turn>model\n<|tool_call>call:shell_exec{{command:<|"|>cd deliverables/{name} && npx vite build<|"|>}}<tool_call|>Compiling.<turn|>',
        f'<|turn>tool\nbuilt in 65ms<turn|>',
        f'<|turn>model\n<|tool_call>call:undertow{{expect:<|"|>{desc}<|"|>,path:<|"|>deliverables/{name}/dist/index.html<|"|>}}<tool_call|>Testing.<turn|>',
        f'<|turn>tool\nQA passed: canvas renders, game loop running<turn|>',
        f'<|turn>model\n<|tool_call>call:message_result{{text:<|"|>Built {name}: {desc}.<|"|>}}<tool_call|>Delivered.<turn|>',
    ])


def medium(prompt, name, code, desc, error, old, new):
    c, o, n = esc(code), esc(old), esc(new)
    return '\n'.join([
        f'<bos><|turn>system\n{SYSTEM_PROMPT}{TOOL_DECLS}<turn|>',
        f'<|turn>user\n{prompt}<turn|>',
        f'<|turn>model\n<|tool_call>call:project_init{{name:<|"|>{name}<|"|>}}<tool_call|>Scaffolding.<turn|>',
        f'<|turn>tool\nCreated project deliverables/{name}<turn|>',
        f'<|turn>model\n<|tool_call>call:file_write{{content:<|"|>{c}<|"|>,path:<|"|>src/main.ts<|"|>}}<tool_call|>Writing game.<turn|>',
        f'<|turn>tool\nWrote src/main.ts<turn|>',
        f'<|turn>model\n<|tool_call>call:shell_exec{{command:<|"|>cd deliverables/{name} && npx vite build<|"|>}}<tool_call|>Compiling.<turn|>',
        f'<|turn>tool\nBuild failed: {error}<turn|>',
        f'<|turn>model\n<|tool_call>call:file_edit{{new_text:<|"|>{n}<|"|>,old_text:<|"|>{o}<|"|>,path:<|"|>src/main.ts<|"|>}}<tool_call|>Fixing.<turn|>',
        f'<|turn>tool\nEdited src/main.ts<turn|>',
        f'<|turn>model\n<|tool_call>call:shell_exec{{command:<|"|>cd deliverables/{name} && npx vite build<|"|>}}<tool_call|>Rebuilding.<turn|>',
        f'<|turn>tool\nbuilt in 68ms<turn|>',
        f'<|turn>model\n<|tool_call>call:undertow{{expect:<|"|>{desc}<|"|>,path:<|"|>deliverables/{name}/dist/index.html<|"|>}}<tool_call|>Testing.<turn|>',
        f'<|turn>tool\nQA passed: canvas renders, game loop running<turn|>',
        f'<|turn>model\n<|tool_call>call:message_result{{text:<|"|>Built {name}: {desc}. Fixed build error.<|"|>}}<tool_call|>Delivered.<turn|>',
    ])


def error_recovery(prompt, old, new):
    o, n = esc(old), esc(new)
    return '\n'.join([
        f'<bos><|turn>system\n{SYSTEM_PROMPT}{TOOL_DECLS}<turn|>',
        f'<|turn>user\n{prompt}<turn|>',
        f'<|turn>model\n<|tool_call>call:file_edit{{new_text:<|"|>{n}<|"|>,old_text:<|"|>{o}<|"|>,path:<|"|>src/main.ts<|"|>}}<tool_call|>Fixed.<turn|>',
    ])


GAMES = [
    ("Build a snake game", "snake-game", "01_snake.ts", "Snake with WASD, food, score, game over"),
    ("Build a pong game", "pong-game", "02_pong.ts", "Pong with AI paddle, ball physics, score"),
    ("Build a flappy bird game", "flappy-bird", "04_flappy.ts", "Flappy with gravity, pipes, score, game over"),
    ("Build an asteroids game", "asteroids-game", "05_asteroids.ts", "Ship rotation, thrust, shooting, asteroid splitting"),
    ("Build a space invaders game", "space-invaders", "06_space_invaders.ts", "Alien grid, player ship, bullets, score, lives"),
    ("Build a platformer game", "platformer-game", "07_platformer.ts", "Character, gravity, platforms, jump, coins"),
    ("Build a missile command game", "missile-command", "08_missile_command.ts", "Cities, incoming missiles, player fires interceptors"),
    ("Build a whack-a-mole game", "whack-a-mole", "09_whack_a_mole.ts", "Grid of holes, moles pop up, click to score, timer"),
    ("Build a rhythm game", "rhythm-game", "10_rhythm.ts", "Notes fall, press key on beat, combo system, score"),
    ("Build a racing game", "racing-game", "14_racing.ts", "Top-down racing with AI traffic, score"),
]

MEDIUMS = [
    ("Build a tetris game with rotation", "tetris-game", "12_tower_defense.ts",
     "Tetrominos, rotation, line clear, levels", "Expected ')' but found '}'",
     "))})", "))\n  )"),
    ("Build a tower defense game", "tower-defense", "12_tower_defense.ts",
     "Path, waves, towers, upgrades", "Property 'hp' does not exist on type 'never'",
     "let enemies: Enemy[]", "interface Enemy { x: number; y: number; hp: number }\nlet enemies: Enemy[]"),
    ("Build a top-down shooter", "top-down-shooter", "13_topdown_shooter.ts",
     "WASD move, mouse aim, enemies, health", "Cannot find name 'mouseX'",
     "let mouseX = W / 2, mouseY = 0", "let mouseX = W / 2, mouseY = H / 2"),
    ("Build an infinite runner", "infinite-runner", "15_infinite_runner.ts",
     "Auto-scroll, jump/duck, obstacles, speed", "'GRAVITY' is not defined",
     "vy += GRAVITY * dt", "const GRAVITY = 1400\nvy += GRAVITY * dt"),
    ("Build a match-3 puzzle game", "match-3-puzzle", "16_match3.ts",
     "Grid swap, match detection, cascade, combo", "Cannot find module '@engine/systems/score'",
     "from '@engine/systems/score'", "from '@engine/systems/score'"),
    ("Build a breakout game", "breakout-game", "05_asteroids.ts",
     "Brick breaker, paddle, ball, bricks", "Module '../engine' not found",
     "from '../engine/", "from '@engine/"),
]

ERRORS = [
    ("The build failed: Cannot resolve '@engine/input/keyboard'",
     "from '@engine/input/keyboard'", "from '@engine/input/keyboard'"),
    ("The build failed: Expected ')' but found '}' at line 63",
     "))})", "))\n  )"),
    ("The build failed: 'score' is not defined",
     "score.addKill()", "const score = new ScoreSystem()\nscore.addKill()"),
]


def main():
    results = []
    print("Packing gamedev training data v1...")

    for prompt, name, filename, desc in GAMES:
        path = EXAMPLES_DIR / filename
        if not path.exists():
            print(f"  SKIP {filename}")
            continue
        code = path.read_text()
        results.append({"text": simple(prompt, name, code, desc)})
        print(f"  [simple] {name}")

    for prompt, name, filename, desc, err, old, new in MEDIUMS:
        path = EXAMPLES_DIR / filename
        if not path.exists():
            print(f"  SKIP {filename}")
            continue
        code = path.read_text()
        results.append({"text": medium(prompt, name, code, desc, err, old, new)})
        print(f"  [medium] {name}")

    for prompt, old, new in ERRORS:
        results.append({"text": error_recovery(prompt, old, new)})
        print(f"  [error]  recovery")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, 'w') as f:
        for r in results:
            f.write(json.dumps(r) + '\n')

    total_chars = sum(len(r['text']) for r in results)
    print(f"\n{'='*50}")
    print(f"Written {len(results)} examples to {OUTPUT}")
    print(f"Total: {total_chars:,} chars ({total_chars//1024} KB)")
    print(f"Train: lr=2e-4, epochs=3, LoRA r=16, response-only masking")


if __name__ == "__main__":
    main()
