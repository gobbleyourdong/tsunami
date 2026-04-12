#!/usr/bin/env python3
"""Gamedev SFT v6 — fill SFT gaps for GHF06, GHF11, GHF12.

Current v5full is missing:
  GHF06: conversation -> message_chat (no SFT example showing this)
  GHF11: 3D game uses tsunami-engine, NOT react-three-fiber (no SFT)
  GHF12: after project_init, file_write main.ts (not npm install R3F) (no SFT)

Adding 5 SFT examples:
  GHF06-chat-capabilities  : "What games can you build?" -> message_chat
  GHF06-chat-frameloop     : "How does FrameLoop work?" -> message_chat
  GHF11-fps-maze-raycaster : 3D maze game -> full pipeline with tsunami-engine raycaster
  GHF11-endless-runner     : endless runner -> full pipeline with tsunami-engine
  GHF08-canvas-snake       : snake game with explicit canvas 2D (no DOM, no React)

Usage:
  /usr/bin/python3 training/build_gamedev_v6.py
  Outputs: workspace/training_data/gamedev_toolcall_train_v6.jsonl
           workspace/training_data/gamedev_combined_v6full.jsonl
"""
import json
from pathlib import Path

print("Loading tokenizer...")
from transformers import AutoTokenizer
tokenizer = AutoTokenizer.from_pretrained("google/gemma-4-e4b-it", trust_remote_code=True)
print("Tokenizer loaded.")

from datetime import date
TODAY = date.today().isoformat()

SYSTEM = """You are Tsunami. You are the wave. You build games by calling tools.

## The Pipeline (every game follows this EXACTLY)
1. project_init(name) -- scaffold the game project
2. file_write(src/main.ts) -- write COMPLETE game code in one file
3. shell_exec("cd deliverables/{name} && npm run build") -- run the break
4. IF reef: fix directly
5. undertow(dist/index.html) -- QA before delivery
6. message_result -- land the wave

## Engine API (import from tsunami-engine)
Input: KeyboardInput, ActionMap
Renderer: FrameLoop -- onUpdate({dt}) gives dt in seconds
Physics: PhysicsWorld, RigidBody, Vec3
Systems: ScoreSystem, HealthSystem
VFX: ParticleSystem, PARTICLE_PRESETS

## Game Pattern
imports -> constants -> state -> keyboard.bind() -> canvas setup -> draw() -> loop.onUpdate -> loop.start()

## Rules
- NEVER skip the break. NEVER deliver without building.
- One tool call per response. Be brief.
- Write COMPLETE game in main.ts -- no partial files, no TODO stubs.
- Canvas 2D for ALL rendering. No React, no DOM manipulation for game state.
- Use tsunami-engine for ALL games including 3D -- NEVER use react-three-fiber.
- Conversational turns (questions, greetings) -> message_chat(done=True). Do NOT project_init.
"""

TOOLS = [
    {"type": "function", "function": {"name": "project_init",
        "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}},
    {"type": "function", "function": {"name": "file_write",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "file_edit",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]}}},
    {"type": "function", "function": {"name": "shell_exec",
        "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
    {"type": "function", "function": {"name": "undertow",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "message_result",
        "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": []}}},
    {"type": "function", "function": {"name": "message_chat",
        "parameters": {"type": "object", "properties": {"text": {"type": "string"}, "done": {"type": "boolean"}}, "required": ["text"]}}},
    {"type": "function", "function": {"name": "search_web",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "plan_update",
        "parameters": {"type": "object", "properties": {"goal": {"type": "string"}, "phases": {"type": "array"}}, "required": ["goal", "phases"]}}},
]

def tc(id_, name, args):
    return {"role": "assistant", "content": "", "tool_calls": [
        {"id": id_, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}
    ]}

def tr(id_, text):
    return {"role": "tool", "tool_call_id": id_, "content": text}


MAZE_CODE = r"""import { FrameLoop, KeyboardInput, Vec3 } from 'tsunami-engine';

// Mini ray-caster — 3D maze rendered entirely on Canvas 2D via tsunami-engine
const MAP = [
  [1,1,1,1,1,1,1,1,1,1],
  [1,0,0,0,1,0,0,0,0,1],
  [1,0,1,0,0,0,1,0,1,1],
  [1,0,1,0,1,0,0,0,0,1],
  [1,0,0,0,1,1,0,1,0,1],
  [1,1,0,1,0,0,0,1,0,1],
  [1,0,0,0,0,1,0,0,0,1],
  [1,0,1,1,0,0,1,0,1,1],
  [1,0,0,0,0,1,0,0,0,1],
  [1,1,1,1,1,1,1,1,1,1],
];
const W = 800, H = 500, FOV = Math.PI / 3, RAYS = 240;
const canvas = document.getElementById('canvas') as HTMLCanvasElement;
canvas.width = W; canvas.height = H;
const ctx = canvas.getContext('2d')!;

const kb = new KeyboardInput();
let pos = Vec3.create(1.5, 0, 1.5);
let angle = 0;

const loop = new FrameLoop();
loop.onUpdate(({ dt }) => {
  const spd = 3.5 * dt, rot = 2.4 * dt;
  if (kb.isDown('ArrowLeft'))  angle -= rot;
  if (kb.isDown('ArrowRight')) angle += rot;
  const fwd = kb.isDown('ArrowUp') ? spd : kb.isDown('ArrowDown') ? -spd : 0;
  const nx = pos[0] + Math.cos(angle) * fwd;
  const nz = pos[2] + Math.sin(angle) * fwd;
  if (MAP[Math.floor(pos[2])]?.[Math.floor(nx)] === 0) pos[0] = nx;
  if (MAP[Math.floor(nz)]?.[Math.floor(pos[0])] === 0) pos[2] = nz;

  // Sky and floor
  ctx.fillStyle = '#1a1a3e'; ctx.fillRect(0, 0, W, H / 2);
  ctx.fillStyle = '#2a2a1e'; ctx.fillRect(0, H / 2, W, H / 2);

  // Ray-cast walls
  for (let r = 0; r < RAYS; r++) {
    const ray = angle - FOV / 2 + FOV * (r / RAYS);
    let rx = pos[0], rz = pos[2], dist = 0;
    while (dist < 20) {
      rx += Math.cos(ray) * 0.04; rz += Math.sin(ray) * 0.04; dist += 0.04;
      if (MAP[Math.floor(rz)]?.[Math.floor(rx)] === 1) break;
    }
    const h = Math.min(H, (H / dist) * 0.9);
    const shade = Math.max(20, Math.min(220, Math.floor(200 / (1 + dist * 0.4))));
    ctx.fillStyle = `rgb(${shade >> 1},${shade >> 2},${shade})`;
    ctx.fillRect(r * (W / RAYS), (H - h) / 2, W / RAYS + 1, h);
  }

  // Crosshair
  ctx.strokeStyle = 'rgba(255,255,255,0.7)'; ctx.lineWidth = 1.5;
  ctx.beginPath(); ctx.moveTo(W/2-10, H/2); ctx.lineTo(W/2+10, H/2); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(W/2, H/2-10); ctx.lineTo(W/2, H/2+10); ctx.stroke();

  // HUD
  ctx.fillStyle = 'rgba(0,0,0,0.4)'; ctx.fillRect(6, 6, 220, 28);
  ctx.fillStyle = '#4ecca3'; ctx.font = '14px monospace';
  ctx.fillText('WASD / Arrows to move', 12, 24);
});
loop.start();"""

RUNNER_CODE = r"""import { FrameLoop, KeyboardInput, ScoreSystem } from 'tsunami-engine';

const W = 800, H = 400, GROUND_Y = 310;
const canvas = document.getElementById('canvas') as HTMLCanvasElement;
canvas.width = W; canvas.height = H;
const ctx = canvas.getContext('2d')!;

const kb = new KeyboardInput();
const score = new ScoreSystem();

// Player
const player = { x: 80, y: GROUND_Y, w: 36, h: 52, vy: 0, grounded: true };
// Obstacles
const obstacles: { x: number; w: number; h: number; color: string }[] = [];
const COLORS = ['#e94560', '#f5a623', '#a855f7'];

let speed = 300, dist = 0, alive = true, spawnTimer = 1.5, bgX = 0;

kb.bind('Space',    () => { if (player.grounded) { player.vy = -650; player.grounded = false; } });
kb.bind('ArrowUp',  () => { if (player.grounded) { player.vy = -650; player.grounded = false; } });

const loop = new FrameLoop();
loop.onUpdate(({ dt }) => {
  if (!alive) {
    ctx.fillStyle = 'rgba(0,0,0,0.6)'; ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = '#fff'; ctx.font = 'bold 40px monospace'; ctx.textAlign = 'center';
    ctx.fillText('GAME OVER', W / 2, H / 2 - 20);
    ctx.font = '20px monospace';
    ctx.fillText(`Score: ${score.get()}`, W / 2, H / 2 + 20);
    ctx.fillText('Refresh to restart', W / 2, H / 2 + 55);
    return;
  }

  // Update
  speed = 300 + dist * 0.05; dist += speed * dt;
  score.set(Math.floor(dist / 10));
  bgX -= speed * 0.2 * dt;

  player.vy += 1500 * dt;
  player.y += player.vy * dt;
  if (player.y >= GROUND_Y) { player.y = GROUND_Y; player.vy = 0; player.grounded = true; }

  spawnTimer -= dt;
  if (spawnTimer <= 0) {
    obstacles.push({
      x: W + 30,
      w: 22 + Math.random() * 18,
      h: 45 + Math.random() * 65,
      color: COLORS[Math.floor(Math.random() * COLORS.length)],
    });
    spawnTimer = 0.7 + Math.random() * 1.1;
  }
  obstacles.forEach(o => o.x -= speed * dt);
  const alive_obs = obstacles.filter(o => o.x > -60);
  obstacles.length = 0; obstacles.push(...alive_obs);

  // Collision
  for (const o of obstacles) {
    if (player.x + player.w - 8 > o.x && player.x + 8 < o.x + o.w
        && player.y + player.h - 6 > H - o.h) { alive = false; }
  }

  // Draw sky gradient
  const sky = ctx.createLinearGradient(0, 0, 0, H);
  sky.addColorStop(0, '#0d0d2e'); sky.addColorStop(1, '#1a1a4e');
  ctx.fillStyle = sky; ctx.fillRect(0, 0, W, H);

  // Scrolling ground
  ctx.fillStyle = '#2a2a1e';
  ctx.fillRect(0, GROUND_Y + player.h, W, H - GROUND_Y - player.h);
  ctx.strokeStyle = '#4a4a3e'; ctx.lineWidth = 1;
  for (let x = ((bgX % 80) + 80) % 80; x < W; x += 80) {
    ctx.beginPath(); ctx.moveTo(x, GROUND_Y + player.h); ctx.lineTo(x, H); ctx.stroke();
  }

  // Player
  ctx.fillStyle = '#4ecca3';
  ctx.fillRect(player.x, player.y, player.w, player.h);
  // Eyes
  ctx.fillStyle = '#0d0d2e';
  ctx.fillRect(player.x + player.w - 14, player.y + 10, 8, 8);

  // Obstacles
  obstacles.forEach(o => {
    ctx.fillStyle = o.color;
    ctx.fillRect(o.x, H - o.h, o.w, o.h);
  });

  // HUD
  ctx.fillStyle = '#fff'; ctx.font = 'bold 20px monospace'; ctx.textAlign = 'left';
  ctx.fillText(`Score: ${score.get()}`, 12, 30);
  ctx.fillStyle = '#4ecca3';
  ctx.fillText(`Speed: ${Math.floor(speed)}`, 12, 56);
});
loop.start();"""

SNAKE_CODE = r"""import { FrameLoop, KeyboardInput } from 'tsunami-engine';

// Snake — pure Canvas 2D, no DOM, no React
const TILE = 22, COLS = 24, ROWS = 20;
const canvas = document.getElementById('canvas') as HTMLCanvasElement;
canvas.width = COLS * TILE; canvas.height = ROWS * TILE;
const ctx = canvas.getContext('2d')!;

const kb = new KeyboardInput();

type Dir = { x: number; y: number };
let snake: { x: number; y: number }[] = [{ x: 12, y: 10 }];
let dir: Dir = { x: 1, y: 0 };
let next: Dir = { x: 1, y: 0 };
let food = { x: 5, y: 5 };
let score = 0;
let running = true;

kb.bind('ArrowUp',    () => { if (dir.y === 0) next = { x: 0, y: -1 }; });
kb.bind('ArrowDown',  () => { if (dir.y === 0) next = { x: 0, y:  1 }; });
kb.bind('ArrowLeft',  () => { if (dir.x === 0) next = { x: -1, y: 0 }; });
kb.bind('ArrowRight', () => { if (dir.x === 0) next = { x:  1, y: 0 }; });

function spawnFood() {
  let nx: number, ny: number;
  do { nx = Math.floor(Math.random() * COLS); ny = Math.floor(Math.random() * ROWS); }
  while (snake.some(s => s.x === nx && s.y === ny));
  food = { x: nx, y: ny };
}

let stepAcc = 0;
const STEP = 0.11;

const loop = new FrameLoop();
loop.onUpdate(({ dt }) => {
  stepAcc += dt;
  if (!running || stepAcc < STEP) {
    // still draw on non-step frames
    return;
  }
  stepAcc -= STEP;
  dir = next;
  const head = {
    x: (snake[0].x + dir.x + COLS) % COLS,
    y: (snake[0].y + dir.y + ROWS) % ROWS,
  };
  if (snake.some(s => s.x === head.x && s.y === head.y)) {
    running = false;
  } else {
    snake.unshift(head);
    if (head.x === food.x && head.y === food.y) { score++; spawnFood(); }
    else snake.pop();
  }

  // Draw
  ctx.fillStyle = '#111827'; ctx.fillRect(0, 0, canvas.width, canvas.height);

  // Grid dots (subtle)
  ctx.fillStyle = 'rgba(255,255,255,0.04)';
  for (let gx = 0; gx < COLS; gx++) for (let gy = 0; gy < ROWS; gy++)
    ctx.fillRect(gx * TILE + TILE / 2 - 1, gy * TILE + TILE / 2 - 1, 2, 2);

  // Snake body
  snake.forEach((s, i) => {
    const t = 1 - i / snake.length;
    ctx.fillStyle = `rgb(${Math.floor(78 + 50 * t)},${Math.floor(204 - 30 * t)},${Math.floor(163 + 20 * t)})`;
    ctx.beginPath();
    ctx.roundRect(s.x * TILE + 2, s.y * TILE + 2, TILE - 4, TILE - 4, 4);
    ctx.fill();
  });

  // Food (pulsing)
  ctx.fillStyle = '#e94560';
  ctx.beginPath();
  ctx.arc(food.x * TILE + TILE / 2, food.y * TILE + TILE / 2, TILE / 2 - 3, 0, Math.PI * 2);
  ctx.fill();

  // Score
  ctx.fillStyle = '#fff'; ctx.font = 'bold 16px monospace'; ctx.textAlign = 'left';
  ctx.fillText(`Score: ${score}`, 6, 18);

  if (!running) {
    ctx.fillStyle = 'rgba(0,0,0,0.65)'; ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = '#fff'; ctx.font = 'bold 36px monospace'; ctx.textAlign = 'center';
    ctx.fillText('GAME OVER', canvas.width / 2, canvas.height / 2 - 14);
    ctx.font = '20px monospace';
    ctx.fillText(`Score: ${score}`, canvas.width / 2, canvas.height / 2 + 22);
  }
});
loop.start();"""


EXAMPLES = []

# GHF06-chat-capabilities: "What games can you build?" -> message_chat
EXAMPLES.append({
    "source": "GHF06-chat-capabilities",
    "messages": [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": "Hello! What kinds of games can you build?"},
        tc("c1", "message_chat", {
            "text": (
                "I can build any 2D or 3D game using the tsunami-engine. Here are some examples:\n\n"
                "**Arcade**: Snake, Pong, Breakout, Space Invaders, Pac-Man clone\n"
                "**Action**: Platformers, endless runners, bullet hell shooters\n"
                "**Strategy**: Tower defense, idle/incremental games\n"
                "**3D**: First-person mazes (ray-caster), 3D space shooters\n"
                "**Puzzle**: Tetris, match-3, sokoban\n\n"
                "Just tell me what you want and I'll build it. What sounds interesting?"
            ),
            "done": True,
        }),
    ],
})

# GHF06-chat-frameloop: "How does FrameLoop work?" -> message_chat
EXAMPLES.append({
    "source": "GHF06-chat-frameloop",
    "messages": [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": "Can you explain how FrameLoop and KeyboardInput work in the engine?"},
        tc("c1", "message_chat", {
            "text": (
                "**FrameLoop** drives the game update cycle:\n"
                "```ts\n"
                "const loop = new FrameLoop();\n"
                "loop.onUpdate(({ dt }) => {\n"
                "  // dt = delta time in seconds (e.g. 0.016 at 60fps)\n"
                "  // move things by velocity * dt for frame-rate-independent motion\n"
                "});\n"
                "loop.start(); // begins requestAnimationFrame\n"
                "```\n\n"
                "**KeyboardInput** handles keys:\n"
                "```ts\n"
                "const kb = new KeyboardInput();\n"
                "kb.bind('Space', () => player.jump()); // fires once on press\n"
                "// In onUpdate: kb.isDown('ArrowRight') — true while held\n"
                "```\n\n"
                "Both import from `tsunami-engine`. Want me to build something using them?"
            ),
            "done": True,
        }),
    ],
})

# GHF11-fps-maze: 3D FPS maze using tsunami-engine raycaster (full pipeline)
EXAMPLES.append({
    "source": "GHF11-fps-maze-raycaster",
    "messages": [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": "Build a 3D first-person maze game with arrow key controls"},
        tc("c1", "project_init", {"name": "fps-maze"}),
        tr("c1", "[project_init] Created game project 'fps-maze'. Write src/main.ts using tsunami-engine."),
        tc("c2", "file_write", {"path": "deliverables/fps-maze/src/main.ts", "content": MAZE_CODE}),
        tr("c2", "[file_write] Written to deliverables/fps-maze/src/main.ts (68 lines)."),
        tc("c3", "shell_exec", {"command": "cd deliverables/fps-maze && npm run build"}),
        tr("c3", "[shell_exec] Build successful. dist/index.html ready."),
        tc("c4", "undertow", {"path": "deliverables/fps-maze/dist/index.html"}),
        tr("c4", "[undertow] QA passed. Canvas renders. Ray-caster walls visible. Arrow key input responsive. No console errors."),
        tc("c5", "message_result", {"text": "3D FPS maze is ready. Navigate with arrow keys — left/right to turn, up/down to move. Ray-caster rendering via Canvas 2D with tsunami-engine FrameLoop."}),
    ],
})

# GHF11-endless-runner: endless runner using tsunami-engine (full pipeline)
EXAMPLES.append({
    "source": "GHF11-endless-runner",
    "messages": [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": "Build an endless runner game where I jump over obstacles with Space"},
        tc("c1", "project_init", {"name": "endless-runner"}),
        tr("c1", "[project_init] Created game project 'endless-runner'. Write src/main.ts."),
        tc("c2", "file_write", {"path": "deliverables/endless-runner/src/main.ts", "content": RUNNER_CODE}),
        tr("c2", "[file_write] Written to deliverables/endless-runner/src/main.ts (82 lines)."),
        tc("c3", "shell_exec", {"command": "cd deliverables/endless-runner && npm run build"}),
        tr("c3", "[shell_exec] Build successful. dist/index.html ready."),
        tc("c4", "undertow", {"path": "deliverables/endless-runner/dist/index.html"}),
        tr("c4", "[undertow] QA passed. Player renders. Obstacles spawn and scroll. Jump works with Space. Score increments. Game-over screen appears on collision."),
        tc("c5", "message_result", {"text": "Endless runner ready. Press Space or Up arrow to jump over obstacles. Speed increases over time. Score shown top-left."}),
    ],
})

# GHF08-canvas-snake: explicit canvas 2D snake (no DOM manipulation, no React)
EXAMPLES.append({
    "source": "GHF08-canvas-snake",
    "messages": [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": "Build a snake game"},
        tc("c1", "project_init", {"name": "snake"}),
        tr("c1", "[project_init] Created game project 'snake'. Write src/main.ts."),
        tc("c2", "file_write", {"path": "deliverables/snake/src/main.ts", "content": SNAKE_CODE}),
        tr("c2", "[file_write] Written to deliverables/snake/src/main.ts (71 lines)."),
        tc("c3", "shell_exec", {"command": "cd deliverables/snake && npm run build"}),
        tr("c3", "[shell_exec] Build successful. dist/index.html ready."),
        tc("c4", "undertow", {"path": "deliverables/snake/dist/index.html"}),
        tr("c4", "[undertow] QA passed. Canvas renders. Snake moves. Food spawns. Score tracks. Game-over on self-collision. No React, no DOM divs."),
        tc("c5", "message_result", {"text": "Snake game ready. Use arrow keys to steer. Eat the red food to grow. Avoid your own tail."}),
    ],
})


# Serialize
def serialize(example):
    msgs = example["messages"]
    prompt = tokenizer.apply_chat_template(
        msgs[:-1], tools=TOOLS, tokenize=False, add_generation_prompt=True
    )
    full = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
    completion = full[len(prompt):]
    return {
        "prompt": prompt,
        "completion": completion,
        "source": example["source"],
        "date": TODAY,
    }


OUT_V6 = Path("workspace/training_data/gamedev_toolcall_train_v6.jsonl")
OUT_COMBINED = Path("workspace/training_data/gamedev_combined_v6full.jsonl")
OUT_V6.parent.mkdir(parents=True, exist_ok=True)

records = [serialize(ex) for ex in EXAMPLES]

with open(OUT_V6, "w") as f:
    for r in records:
        f.write(json.dumps(r) + "\n")

# Build combined v6 = v5full + v6
prev = Path("workspace/training_data/gamedev_combined_v5full.jsonl")
all_lines = []
if prev.exists():
    all_lines.extend(l for l in prev.read_text().splitlines() if l.strip())
all_lines.extend(l for l in OUT_V6.read_text().splitlines() if l.strip())
OUT_COMBINED.write_text("\n".join(all_lines) + "\n")

print(f"\n=== GAMEDEV SFT v6 SUMMARY ===")
print(f"  New examples: {len(records)}")
for r in records:
    toks = len(r['prompt']) + len(r['completion'])
    print(f"  {r['source']}: {toks} chars")
print(f"\n  v6 file: {OUT_V6}")
print(f"  Combined v6full: {OUT_COMBINED} ({sum(1 for l in OUT_COMBINED.read_text().splitlines() if l.strip())} total examples)")
print(f"\nTo train gamedev-v4 SFT (use combined_v6full):")
print(f"  /usr/bin/python3 training/train_unsloth.py --model google/gemma-4-e4b-it \\")
print(f"    --data workspace/training_data/gamedev_combined_v6full.jsonl \\")
print(f"    --output models/gemma-4-e4b-tsunami-gamedev-v4 --epochs 3 --lora-r 16 --lr 2e-4")
