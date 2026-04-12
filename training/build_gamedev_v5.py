#!/usr/bin/env python3
"""Gamedev training data v5 -- targeted L3 recovery gaps.

Targets:
  GER04: missing-asset-file -> file_write placeholder (image doesn't exist)
  GER05 variant: wrong path with workspace/ prefix -> shell_exec corrected path
  + 2 variety builds for data balance

Usage:
  python training/build_gamedev_v5.py
  Output: workspace/training_data/gamedev_toolcall_train_v5.jsonl
  Combined: workspace/training_data/gamedev_combined_v5full.jsonl
"""
import json
from pathlib import Path
from transformers import AutoTokenizer

MODEL = "google/gemma-4-e4b-it"
OUT_PATH = "workspace/training_data/gamedev_toolcall_train_v5.jsonl"
COMBINED_PATH = "workspace/training_data/gamedev_combined_v5full.jsonl"

SYSTEM_TEXT = """You are Tsunami. You are the wave. You build games by calling tools.

## The Ocean

- **current**: your sense of direction. Low tension = deliver. High tension = search.
- **circulation**: routing. Low tension -> deliver. High tension -> search or refuse.
- **pressure**: sustained uncertainty. 2 failures -> search. 4 failures -> ask the user.
- **undertow**: QA. ALWAYS verify before delivering.
- **break**: compile. shell_exec build after EVERY file_write.
- **reef**: error. Fix directly. Type/syntax -> file_edit. Missing module -> shell_exec npm install. Wrong path -> shell_exec with corrected path. Missing asset -> file_write placeholder.

## The Pipeline (every game follows this EXACTLY)

1. project_init(name) -- scaffold the game project
2. file_write(src/main.ts) -- write COMPLETE game code in one file
3. shell_exec("cd deliverables/{name} && npm run build") -- run the break
4. IF reef: fix directly -- file_edit for syntax, shell_exec for missing modules
5. undertow(dist/index.html) -- QA before delivery
6. message_result -- land the wave

## Engine API (import from '@engine/...' or 'tsunami-engine')

Input: KeyboardInput, ActionMap -- bind keys, detect press/hold/release
Renderer: FrameLoop -- onUpdate(stats) gives dt
Physics: PhysicsWorld, RigidBody
VFX: ParticleSystem

## Game Pattern

imports -> constants -> state -> keyboard.bind() -> canvas setup -> draw() -> loop.onUpdate -> loop.start()

## Rules
- NEVER skip the break. NEVER deliver without building.
- One tool call per response. Be brief.
- Write COMPLETE game in main.ts -- no partial files, no TODO stubs.
- Canvas 2D for all rendering. No React, no DOM manipulation for game state.
- After project_init succeeds: ALWAYS call file_write next.
- Missing asset file error -> file_write a placeholder SVG/data URI, NOT message_chat.
- Wrong path in shell_exec -> retry shell_exec with corrected path, NOT message_chat.
"""

TOOLS = [
    {"type": "function", "function": {
        "name": "project_init", "description": "Create a game project.",
        "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
    }},
    {"type": "function", "function": {
        "name": "file_write", "description": "Create or overwrite a file.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"}, "content": {"type": "string"},
        }, "required": ["path", "content"]},
    }},
    {"type": "function", "function": {
        "name": "file_edit", "description": "Make targeted modifications to a file.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"},
        }, "required": ["path", "old_text", "new_text"]},
    }},
    {"type": "function", "function": {
        "name": "shell_exec", "description": "Run a shell command.",
        "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]},
    }},
    {"type": "function", "function": {
        "name": "undertow", "description": "QA screenshot test before delivery.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"}, "expect": {"type": "string"},
        }, "required": ["path"]},
    }},
    {"type": "function", "function": {
        "name": "message_result", "description": "Deliver final outcome.",
        "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": []},
    }},
    {"type": "function", "function": {
        "name": "message_chat", "description": "Talk to the user.",
        "parameters": {"type": "object", "properties": {
            "text": {"type": "string"}, "done": {"type": "boolean"},
        }, "required": ["text"]},
    }},
    {"type": "function", "function": {
        "name": "search_web", "description": "Search the web.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    }},
    {"type": "function", "function": {
        "name": "plan_update", "description": "Update the build plan.",
        "parameters": {"type": "object", "properties": {"plan": {"type": "string"}}, "required": ["plan"]},
    }},
]

print("Loading tokenizer (google/gemma-4-e4b-it)...")
tokenizer = AutoTokenizer.from_pretrained(MODEL, trust_remote_code=True)
print("Tokenizer loaded.")


def build_conv(user_prompt, turns):
    msgs = [
        {"role": "system", "content": SYSTEM_TEXT},
        {"role": "user", "content": user_prompt},
    ]
    for name, args, response in turns:
        msgs.append({
            "role": "assistant", "content": "",
            "tool_calls": [{"type": "function", "function": {"name": name, "arguments": json.dumps(args) if isinstance(args, dict) else args}}],
        })
        msgs.append({"role": "tool", "name": name, "content": (response or "OK")[:500]})
    return msgs


def tokenize(msgs):
    return {"text": tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)}


# Placeholder SVG as data URI -- used for missing asset recovery
SHIP_SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32"><polygon points="16,2 30,30 2,30" fill="#4ecca3"/></svg>'
COIN_SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16"><circle cx="8" cy="8" r="7" fill="#f4d03f"/></svg>'

# Simple game code snippets for variety builds
FLAPPY_CODE = (
    "import { FrameLoop, KeyboardInput } from 'tsunami-engine';\n"
    "const W=480,H=640,GRAVITY=900,JUMP=-320,GAP=180,SPEED=180;\n"
    "let by=H/2,vy=0,pipes:number[]=[],score=0,alive=true;\n"
    "const canvas=document.createElement('canvas');canvas.width=W;canvas.height=H;"
    "document.body.appendChild(canvas);\nconst ctx=canvas.getContext('2d')!;\n"
    "const keys=new KeyboardInput();keys.bind();\n"
    "for(let i=0;i<4;i++)pipes.push(W+i*200,Math.random()*(H-GAP-120)+60);\n"
    "const loop=new FrameLoop();\n"
    "loop.onUpdate(({dt})=>{\n"
    "  if(!alive)return;\n"
    "  if(keys.isPressed('Space')||keys.isPressed('ArrowUp'))vy=JUMP;\n"
    "  vy+=GRAVITY*dt;by+=vy*dt;\n"
    "  for(let i=0;i<pipes.length;i+=2){pipes[i]-=SPEED*dt;\n"
    "    if(pipes[i]<-60){pipes[i]=W+60;pipes[i+1]=Math.random()*(H-GAP-120)+60;score++;}\n"
    "    if(pipes[i]<50&&pipes[i]>-20&&(by<pipes[i+1]||by>pipes[i+1]+GAP))alive=false;}\n"
    "  if(by>H||by<0)alive=false;\n"
    "  ctx.fillStyle='#1a237e';ctx.fillRect(0,0,W,H);\n"
    "  ctx.fillStyle='#4caf50';for(let i=0;i<pipes.length;i+=2){"
    "ctx.fillRect(pipes[i]-20,0,40,pipes[i+1]);ctx.fillRect(pipes[i]-20,pipes[i+1]+GAP,40,H);}\n"
    "  ctx.fillStyle='#ffeb3b';ctx.beginPath();ctx.arc(80,by,14,0,Math.PI*2);ctx.fill();\n"
    "  ctx.fillStyle='#fff';ctx.font='24px monospace';ctx.fillText(''+score,20,40);\n"
    "  if(!alive){ctx.fillStyle='rgba(0,0,0,0.6)';ctx.fillRect(0,0,W,H);\n"
    "    ctx.fillStyle='#fff';ctx.font='32px monospace';ctx.fillText('GAME OVER',W/2-100,H/2);}\n"
    "});\nloop.start();\n"
)

TRON_CODE = (
    "import { FrameLoop, KeyboardInput } from 'tsunami-engine';\n"
    "const W=600,H=600,CELL=10,SPEED=8;\n"
    "let p1={x:15,y:30,dx:1,dy:0,trail:[] as {x:number,y:number}[]};\n"
    "let p2={x:44,y:30,dx:-1,dy:0,trail:[] as {x:number,y:number}[]};\n"
    "let alive=true;\n"
    "const canvas=document.createElement('canvas');canvas.width=W;canvas.height=H;"
    "document.body.appendChild(canvas);\nconst ctx=canvas.getContext('2d')!;\n"
    "const keys=new KeyboardInput();keys.bind();\n"
    "const loop=new FrameLoop();\nlet timer=0;\n"
    "loop.onUpdate(({dt})=>{\n"
    "  if(!alive)return;\n"
    "  if(keys.isPressed('ArrowUp')&&p1.dy===0){p1.dx=0;p1.dy=-1;}\n"
    "  if(keys.isPressed('ArrowDown')&&p1.dy===0){p1.dx=0;p1.dy=1;}\n"
    "  if(keys.isPressed('ArrowLeft')&&p1.dx===0){p1.dx=-1;p1.dy=0;}\n"
    "  if(keys.isPressed('ArrowRight')&&p1.dx===0){p1.dx=1;p1.dy=0;}\n"
    "  timer+=dt;if(timer<1/SPEED)return;timer=0;\n"
    "  for(const p of [p1,p2]){"
    "    p.trail.push({x:p.x,y:p.y});p.x+=p.dx;p.y+=p.dy;"
    "    if(p.x<0||p.x>=W/CELL||p.y<0||p.y>=H/CELL)alive=false;"
    "    for(const t of [...p1.trail,...p2.trail])if(t.x===p.x&&t.y===p.y)alive=false;}\n"
    "  ctx.fillStyle='#000';ctx.fillRect(0,0,W,H);\n"
    "  ctx.fillStyle='#0f0';for(const t of p1.trail)ctx.fillRect(t.x*CELL,t.y*CELL,CELL-1,CELL-1);\n"
    "  ctx.fillStyle='#f80';for(const t of p2.trail)ctx.fillRect(t.x*CELL,t.y*CELL,CELL-1,CELL-1);\n"
    "  if(!alive){ctx.fillStyle='rgba(0,0,0,0.7)';ctx.fillRect(0,0,W,H);\n"
    "    ctx.fillStyle='#fff';ctx.font='28px monospace';ctx.fillText('COLLISION',W/2-100,H/2);}\n"
    "});\nloop.start();\n"
)


examples = []

# ────────────────���───────────────────────────────────────────────────────────
# GER04: Missing asset file -> file_write placeholder (NOT message_chat)
# ────────────────────────────────────────────────────────────────────────────

# GER04 variant 1: space shooter -- public/ship.png missing
examples.append(tokenize(build_conv("Build a space shooter game", [
    ("project_init", {"name": "space-shooter"}, "Created game project 'space-shooter'. Write src/main.ts."),
    ("file_write", {"path": "deliverables/space-shooter/src/main.ts",
                    "content": "import { FrameLoop, KeyboardInput } from 'tsunami-engine';\n"
                               "const img=new Image();img.src='public/ship.png';\n"
                               "const canvas=document.createElement('canvas');canvas.width=480;canvas.height=640;\n"
                               "document.body.appendChild(canvas);\nconst ctx=canvas.getContext('2d')!;\n"
                               "const keys=new KeyboardInput();keys.bind();\n"
                               "let px=240,py=560;\n"
                               "const loop=new FrameLoop();\n"
                               "loop.onUpdate(({dt})=>{\n"
                               "  if(keys.isHeld('ArrowLeft'))px-=200*dt;\n"
                               "  if(keys.isHeld('ArrowRight'))px+=200*dt;\n"
                               "  ctx.fillStyle='#0a0a1a';ctx.fillRect(0,0,480,640);\n"
                               "  ctx.drawImage(img,px-16,py-16,32,32);\n"
                               "});\nloop.start();"},
     "Wrote src/main.ts"),
    ("shell_exec", {"command": "cd deliverables/space-shooter && npm run build"},
     "Error: Failed to resolve import 'public/ship.png'. File does not exist."),
    # Fix: write placeholder SVG for the missing asset
    ("file_write", {"path": "deliverables/space-shooter/public/ship.png",
                    "content": SHIP_SVG},
     "Wrote public/ship.png (SVG placeholder)"),
    ("shell_exec", {"command": "cd deliverables/space-shooter && npm run build"},
     "vite built in 71ms. dist/index.html ready."),
    ("undertow", {"path": "deliverables/space-shooter/dist/index.html", "expect": "space shooter"},
     "QA passed: ship visible, moves left/right."),
    ("message_result", {"text": "Space shooter ready. Arrow keys to move."},
     "Delivered."),
])))

# GER04 variant 2: platformer -- coin sprite missing
examples.append(tokenize(build_conv("Build a platformer with coin collectibles", [
    ("project_init", {"name": "platformer-coins"}, "Created game project 'platformer-coins'. Write src/main.ts."),
    ("file_write", {"path": "deliverables/platformer-coins/src/main.ts",
                    "content": "import { FrameLoop, KeyboardInput } from 'tsunami-engine';\n"
                               "const coinImg=new Image();coinImg.src='public/coin.png';\n"
                               "const canvas=document.createElement('canvas');canvas.width=640;canvas.height=480;\n"
                               "document.body.appendChild(canvas);\nconst ctx=canvas.getContext('2d')!;\n"
                               "const keys=new KeyboardInput();keys.bind();\n"
                               "let px=100,py=400,vy=0;const coins=[{x:200,y:380},{x:350,y:350},{x:500,y:380}];\n"
                               "const loop=new FrameLoop();\n"
                               "loop.onUpdate(({dt})=>{\n"
                               "  if(keys.isHeld('ArrowLeft'))px-=180*dt;\n"
                               "  if(keys.isHeld('ArrowRight'))px+=180*dt;\n"
                               "  vy+=980*dt;py+=vy*dt;if(py>400){py=400;vy=0;}\n"
                               "  if(keys.isPressed('Space')&&py>=400)vy=-400;\n"
                               "  ctx.fillStyle='#87ceeb';ctx.fillRect(0,0,640,480);\n"
                               "  ctx.fillStyle='#4a7c59';ctx.fillRect(0,420,640,60);\n"
                               "  for(const c of coins)ctx.drawImage(coinImg,c.x-8,c.y-8,16,16);\n"
                               "  ctx.fillStyle='#e74c3c';ctx.fillRect(px-15,py-30,30,40);\n"
                               "});\nloop.start();"},
     "Wrote src/main.ts"),
    ("shell_exec", {"command": "cd deliverables/platformer-coins && npm run build"},
     "Error: Failed to resolve import 'public/coin.png'. File does not exist."),
    # Fix: write placeholder SVG for coin
    ("file_write", {"path": "deliverables/platformer-coins/public/coin.png",
                    "content": COIN_SVG},
     "Wrote public/coin.png (SVG placeholder)"),
    ("shell_exec", {"command": "cd deliverables/platformer-coins && npm run build"},
     "vite built in 68ms. dist/index.html ready."),
    ("undertow", {"path": "deliverables/platformer-coins/dist/index.html", "expect": "platformer with coins"},
     "QA passed: player jumps, coins visible."),
    ("message_result", {"text": "Platformer ready. Arrow keys + Space to jump. Collect coins!"},
     "Delivered."),
])))

# ────────────────────────────────────────────────────────────────────────────
# GER05 variant: workspace/ prefix in cd path -> shell_exec with corrected path
# ────────────────────────────────────────────────────────────────────────────

# GER05 variant 1: tetris with workspace/ prefix
examples.append(tokenize(build_conv("Build a tetris game", [
    ("project_init", {"name": "tetris"}, "Created game project 'tetris'. Write src/main.ts."),
    ("file_write", {"path": "deliverables/tetris/src/main.ts",
                    "content": "import { FrameLoop, KeyboardInput } from 'tsunami-engine';\n"
                               "// tetris implementation\nconst canvas=document.createElement('canvas');\n"
                               "canvas.width=300;canvas.height=600;document.body.appendChild(canvas);\n"
                               "const ctx=canvas.getContext('2d')!;\n"
                               "const loop=new FrameLoop();\n"
                               "loop.onUpdate(()=>{\n"
                               "  ctx.fillStyle='#1a1a2e';ctx.fillRect(0,0,300,600);\n"
                               "  ctx.fillStyle='#4ecca3';ctx.fillRect(120,240,30,30);\n"
                               "});\nloop.start();"},
     "Wrote src/main.ts"),
    ("shell_exec", {"command": "cd workspace/deliverables/tetris && npm run build"},
     "Error: No such file or directory: workspace/deliverables/tetris"),
    # Fix: remove workspace/ prefix -- correct path is deliverables/tetris
    ("shell_exec", {"command": "cd deliverables/tetris && npm run build"},
     "vite built in 64ms. dist/index.html ready."),
    ("undertow", {"path": "deliverables/tetris/dist/index.html", "expect": "tetris game"},
     "QA passed: tetris piece visible on board."),
    ("message_result", {"text": "Tetris ready."},
     "Delivered."),
])))

# GER05 variant 2: frogger with workspace/ prefix
examples.append(tokenize(build_conv("Build a frogger-style crossing game", [
    ("project_init", {"name": "frogger"}, "Created game project 'frogger'. Write src/main.ts."),
    ("file_write", {"path": "deliverables/frogger/src/main.ts",
                    "content": "import { FrameLoop, KeyboardInput } from 'tsunami-engine';\n"
                               "const W=480,H=480;\n"
                               "let fx=W/2,fy=H-30;\n"
                               "const canvas=document.createElement('canvas');canvas.width=W;canvas.height=H;\n"
                               "document.body.appendChild(canvas);\nconst ctx=canvas.getContext('2d')!;\n"
                               "const keys=new KeyboardInput();keys.bind();\n"
                               "const cars=[{x:0,y:200,speed:120},{x:240,y:280,speed:-90},{x:120,y:350,speed:150}];\n"
                               "const loop=new FrameLoop();\n"
                               "loop.onUpdate(({dt})=>{\n"
                               "  if(keys.isPressed('ArrowUp'))fy-=40;\n"
                               "  if(keys.isPressed('ArrowDown'))fy+=40;\n"
                               "  if(keys.isPressed('ArrowLeft'))fx-=40;\n"
                               "  if(keys.isPressed('ArrowRight'))fx+=40;\n"
                               "  for(const c of cars){c.x+=c.speed*dt;if(c.x>W+30)c.x=-30;if(c.x<-30)c.x=W+30;}\n"
                               "  ctx.fillStyle='#2d5016';ctx.fillRect(0,0,W,H);\n"
                               "  ctx.fillStyle='#333';ctx.fillRect(0,160,W,240);\n"
                               "  ctx.fillStyle='#e74c3c';for(const c of cars)ctx.fillRect(c.x-20,c.y-10,40,20);\n"
                               "  ctx.fillStyle='#2ecc71';ctx.fillRect(fx-15,fy-15,30,30);\n"
                               "});\nloop.start();"},
     "Wrote src/main.ts"),
    ("shell_exec", {"command": "cd workspace/deliverables/frogger && npm run build"},
     "Error: No such file or directory: workspace/deliverables/frogger"),
    # Fix: strip workspace/ prefix
    ("shell_exec", {"command": "cd deliverables/frogger && npm run build"},
     "vite built in 66ms. dist/index.html ready."),
    ("undertow", {"path": "deliverables/frogger/dist/index.html", "expect": "frog crossing road"},
     "QA passed: frog visible, cars moving."),
    ("message_result", {"text": "Frogger ready. Arrow keys to hop."},
     "Delivered."),
])))

# ────────────────────────────────────────────────────────────────────────────
# Variety builds (balance)
# ────────────────────────────────────────────────────────────────────────────

# Flappy bird (variety)
examples.append(tokenize(build_conv("Build a flappy bird game", [
    ("project_init", {"name": "flappy-bird"}, "Created game project 'flappy-bird'. Write src/main.ts."),
    ("file_write", {"path": "deliverables/flappy-bird/src/main.ts", "content": FLAPPY_CODE},
     "Wrote src/main.ts"),
    ("shell_exec", {"command": "cd deliverables/flappy-bird && npm run build"},
     "vite built in 62ms. dist/index.html ready."),
    ("undertow", {"path": "deliverables/flappy-bird/dist/index.html", "expect": "flappy bird flying through pipes"},
     "QA passed: bird jumps, pipes scroll, score increments."),
    ("message_result", {"text": "Flappy Bird ready. Space or Up arrow to flap."}, "Delivered."),
])))

# Tron light cycles (variety)
examples.append(tokenize(build_conv("Build a 2-player Tron light cycles game", [
    ("project_init", {"name": "tron-cycles"}, "Created game project 'tron-cycles'. Write src/main.ts."),
    ("file_write", {"path": "deliverables/tron-cycles/src/main.ts", "content": TRON_CODE},
     "Wrote src/main.ts"),
    ("shell_exec", {"command": "cd deliverables/tron-cycles && npm run build"},
     "vite built in 64ms. dist/index.html ready."),
    ("undertow", {"path": "deliverables/tron-cycles/dist/index.html", "expect": "tron light cycles grid"},
     "QA passed: two cycles visible, trails growing."),
    ("message_result", {"text": "Tron ready. P1: Arrow keys. P2: WASD."}, "Delivered."),
])))


# ────────────────────────────────────────────────────────────────────────────
# Write output
# ────────────────────────────────────────────────────────────────────────────
out = Path(OUT_PATH)
out.parent.mkdir(parents=True, exist_ok=True)
with open(out, "w") as f:
    for ex in examples:
        f.write(json.dumps(ex) + "\n")

print(f"Wrote {len(examples)} examples to {out}")

# Combine with v2+v3+v3b+v4
prev_paths = [
    "workspace/training_data/gamedev_toolcall_train_v2.jsonl",
    "workspace/training_data/gamedev_toolcall_train_v3.jsonl",
    "workspace/training_data/gamedev_toolcall_train_v3b.jsonl",
    "workspace/training_data/gamedev_toolcall_train_v4.jsonl",
]
combined_path = Path(COMBINED_PATH)
total = 0
with open(combined_path, "w") as out_f:
    for p in prev_paths:
        lines = Path(p).read_text().splitlines()
        for line in lines:
            if line.strip():
                out_f.write(line + "\n")
                total += 1
    v5_lines = out.read_text().splitlines()
    for line in v5_lines:
        if line.strip():
            out_f.write(line + "\n")
            total += 1

print(f"Combined: {total} examples -> {combined_path}")
print(f"  Breakdown: v2(17) + v3(16) + v3b(6) + v4(6) + v5({len(examples)}) = {total}")
