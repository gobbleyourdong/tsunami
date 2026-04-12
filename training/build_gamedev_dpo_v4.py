#!/usr/bin/env python3
"""Gamedev DPO pairs v4 — targeting 6 remaining L4 GHF failures.

GHF02: Research gate — reference clone ("like Wordle/Flappy Bird") -> search_web first
GHF03: Stall detection — after 2+ file_reads -> file_write main.ts (not read more)
GHF04: Code-write gate — more pairs (different games from v3)
GHF05: Shell loop — 2 identical build failures -> file_write fix (not retry shell)
GHF07: Engine imports — file_write must use tsunami-engine imports, not React
GHF08: Canvas 2D pattern — game render must use Canvas 2D ctx, not DOM manipulation

Usage:
  /usr/bin/python3 training/build_gamedev_dpo_v4.py
"""
import json
from datetime import date
from pathlib import Path

print("Loading tokenizer...")
from transformers import AutoTokenizer
tokenizer = AutoTokenizer.from_pretrained("google/gemma-4-e4b-it", trust_remote_code=True)
print("Tokenizer loaded.")

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
Renderer: FrameLoop -- onUpdate(stats) gives dt
Physics: PhysicsWorld, RigidBody, Vec3
VFX: ParticleSystem
Systems: ScoreSystem, HealthSystem
AI: BehaviorTree, FSM, Pathfinding

## Rules
- NEVER skip the break.
- NEVER deliver without building.
- One tool call per response.
- Canvas 2D for all rendering. No React, no DOM manipulation for game state.
- For reference clones ("like X", "similar to Y"), search_web FIRST to understand X's mechanics.
- After reading 2+ files, stop reading — write the code.
- After 2 identical build failures, write a fix — don't retry the same shell command.
- Use tsunami-engine for ALL games — NEVER use React, react-three-fiber, or DOM manipulation.
"""

TOOLS = [
    {"type": "function", "function": {"name": "project_init", "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}},
    {"type": "function", "function": {"name": "file_write", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "file_edit", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]}}},
    {"type": "function", "function": {"name": "shell_exec", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
    {"type": "function", "function": {"name": "undertow", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "message_result", "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": []}}},
    {"type": "function", "function": {"name": "message_chat", "parameters": {"type": "object", "properties": {"text": {"type": "string"}, "done": {"type": "boolean"}}, "required": ["text"]}}},
    {"type": "function", "function": {"name": "search_web", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "plan_update", "parameters": {"type": "object", "properties": {"goal": {"type": "string"}, "phases": {"type": "array"}}, "required": ["goal", "phases"]}}},
    {"type": "function", "function": {"name": "file_read", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
]

# Good tsunami-engine code samples

TETRIS_TS = 'import { FrameLoop, KeyboardInput, ScoreSystem } from "tsunami-engine";\nconst W=300,H=600,S=30,COLS=W/S,ROWS=H/S;\nconst SHAPES=[[[0,0],[1,0],[2,0],[3,0]],[[0,0],[1,0],[0,1],[1,1]],[[1,0],[0,1],[1,1],[2,1]],[[0,0],[0,1],[1,1],[2,1]],[[2,0],[0,1],[1,1],[2,1]],[[0,0],[1,0],[1,1],[2,1]],[[1,0],[2,0],[0,1],[1,1]]];\nconst COLORS=["#00f0f0","#f0f000","#a000f0","#0000f0","#f0a000","#00f000","#f00000"];\nconst cv=document.getElementById("canvas") as HTMLCanvasElement;\ncv.width=W; cv.height=H;\nconst ctx=cv.getContext("2d")!;\nconst kb=new KeyboardInput();\nconst score=new ScoreSystem();\nlet grid=Array.from({length:ROWS},()=>Array(COLS).fill(0));\nlet ci=Math.floor(Math.random()*7),piece=SHAPES[ci].map(c=>({x:c[0]+3,y:c[1]})),acc=0,spd=0.5;\nfunction place(){piece.forEach(c=>{if(c.y>=0)grid[c.y][c.x]=ci+1;});\n  for(let r=ROWS-1;r>=0;r--)if(grid[r].every(c=>c>0)){grid.splice(r,1);grid.unshift(Array(COLS).fill(0));score.add(100);r++;}\n  ci=Math.floor(Math.random()*7);piece=SHAPES[ci].map(c=>({x:c[0]+3,y:c[1]}));}\nfunction valid(p:typeof piece,dx=0,dy=0){return p.every(c=>c.x+dx>=0&&c.x+dx<COLS&&c.y+dy<ROWS&&(c.y+dy<0||!grid[c.y+dy][c.x+dx]));}\nconst loop=new FrameLoop();\nkb.bind("ArrowLeft",()=>{if(valid(piece,-1,0))piece.forEach(c=>c.x--);});\nkb.bind("ArrowRight",()=>{if(valid(piece,1,0))piece.forEach(c=>c.x++);});\nkb.bind("ArrowDown",()=>{if(valid(piece,0,1))piece.forEach(c=>c.y++);else place();});\nkb.bind("ArrowUp",()=>{const r=piece.map(c=>({x:SHAPES[ci][0].y-c.y+SHAPES[ci][0].x,y:c.x-SHAPES[ci][0].x+SHAPES[ci][0].y}));if(valid(r))piece.splice(0,piece.length,...r);});\nloop.onUpdate(({dt})=>{\n  acc+=dt;if(acc<spd)return;acc=0;\n  if(valid(piece,0,1))piece.forEach(c=>c.y++);else place();\n  ctx.fillStyle="#111";ctx.fillRect(0,0,W,H);\n  grid.forEach((row,r)=>row.forEach((c,col)=>{if(c){ctx.fillStyle=COLORS[c-1];ctx.fillRect(col*S+1,r*S+1,S-2,S-2);}}));\n  piece.forEach(c=>{ctx.fillStyle=COLORS[ci];ctx.fillRect(c.x*S+1,c.y*S+1,S-2,S-2);});\n  ctx.fillStyle="#fff";ctx.font="14px monospace";ctx.fillText("Score: "+score.get(),4,16);\n});\nloop.start();'

SPACE_INV_TS = 'import { FrameLoop, KeyboardInput, ScoreSystem } from "tsunami-engine";\nconst W=600,H=500;\nconst cv=document.getElementById("canvas") as HTMLCanvasElement;\ncv.width=W; cv.height=H;\nconst ctx=cv.getContext("2d")!;\nconst kb=new KeyboardInput();\nconst score=new ScoreSystem();\nlet player={x:W/2,y:460},bullets:{x:number,y:number}[]=[],enemyBullets:{x:number,y:number}[]=[];\nlet invaders=Array.from({length:5*11},(_,i)=>({x:60+(i%11)*48,y:60+Math.floor(i/11)*40,alive:true}));\nlet dir=1,acc=0,interval=1.2,spawnAcc=0;\nkb.bind("Space",()=>{if(bullets.length<3)bullets.push({x:player.x,y:player.y});});\nconst loop=new FrameLoop();\nloop.onUpdate(({dt})=>{\n  if(kb.isDown("ArrowLeft"))player.x=Math.max(20,player.x-300*dt);\n  if(kb.isDown("ArrowRight"))player.x=Math.min(W-20,player.x+300*dt);\n  bullets.forEach(b=>b.y-=500*dt); bullets=bullets.filter(b=>b.y>0);\n  enemyBullets.forEach(b=>b.y+=300*dt); enemyBullets=enemyBullets.filter(b=>b.y<H);\n  acc+=dt; if(acc>interval){acc=0;interval=Math.max(0.3,interval*0.97);\n    const alive=invaders.filter(i=>i.alive);if(alive.length){const r=alive[Math.floor(Math.random()*alive.length)];enemyBullets.push({x:r.x,y:r.y+10});}}\n  const edge=invaders.filter(i=>i.alive).reduce((e,i)=>(i.x<e.min?{min:i.x,max:e.max}:{min:e.min,max:Math.max(i.x,e.max)}),{min:W,max:0});\n  if(edge.max>W-30||edge.min<30){dir*=-1;invaders.forEach(i=>{if(i.alive)i.y+=10;});}\n  invaders.forEach(i=>{if(i.alive)i.x+=dir*60*dt;});\n  bullets.forEach(b=>{invaders.filter(i=>i.alive).forEach(i=>{if(Math.abs(b.x-i.x)<16&&Math.abs(b.y-i.y)<12){i.alive=false;score.add(10);}});});\n  ctx.fillStyle="#0d0d1a";ctx.fillRect(0,0,W,H);\n  invaders.filter(i=>i.alive).forEach(i=>{ctx.fillStyle="#4ecca3";ctx.fillRect(i.x-14,i.y-10,28,20);});\n  ctx.fillStyle="#e94560";ctx.fillRect(player.x-18,player.y-8,36,16);\n  ctx.fillStyle="#fff";\n  bullets.forEach(b=>{ctx.fillRect(b.x-2,b.y-8,4,12);});\n  enemyBullets.forEach(b=>{ctx.fillStyle="#f59e0b";ctx.fillRect(b.x-2,b.y,4,10);});\n  ctx.fillStyle="#fff";ctx.font="16px monospace";ctx.fillText("Score: "+score.get(),8,20);\n});\nloop.start();'

PLATFORMER_TS = 'import { FrameLoop, KeyboardInput, ScoreSystem } from "tsunami-engine";\nconst W=800,H=480,GR=800;\nconst cv=document.getElementById("canvas") as HTMLCanvasElement;\ncv.width=W; cv.height=H;\nconst ctx=cv.getContext("2d")!;\nconst kb=new KeyboardInput();\nconst score=new ScoreSystem();\nconst PLAT=[{x:0,y:440,w:200},{x:250,y:380,w:150},{x:450,y:320,w:120},{x:620,y:360,w:160},{x:0,y:H,w:W}];\nconst COINS=[{x:275,y:360},{x:310,y:360},{x:470,y:300},{x:640,y:340},{x:680,y:340}];\nlet p={x:60,y:380,vx:0,vy:0,grounded:false};\nconst loop=new FrameLoop();\nloop.onUpdate(({dt})=>{\n  p.vx=0;\n  if(kb.isDown("ArrowLeft")||kb.isDown("KeyA"))p.vx=-220;\n  if(kb.isDown("ArrowRight")||kb.isDown("KeyD"))p.vx=220;\n  if((kb.isDown("Space")||kb.isDown("ArrowUp")||kb.isDown("KeyW"))&&p.grounded){p.vy=-520;p.grounded=false;}\n  p.vy=Math.min(p.vy+GR*dt,900);\n  p.x+=p.vx*dt; p.y+=p.vy*dt;\n  p.grounded=false;\n  PLAT.forEach(pl=>{\n    if(p.x+24>pl.x&&p.x<pl.x+pl.w&&p.y+40>pl.y&&p.y+40<pl.y+20&&p.vy>=0){p.y=pl.y-40;p.vy=0;p.grounded=true;}\n  });\n  p.x=Math.max(0,Math.min(W-28,p.x));\n  COINS.forEach(c=>{if(!c.collected&&Math.abs(p.x+14-c.x)<18&&Math.abs(p.y+20-c.y)<18){c.collected=true;score.add(50);}});\n  ctx.fillStyle="#1a1a2e";ctx.fillRect(0,0,W,H);\n  ctx.fillStyle="#4a4a8a";\n  PLAT.slice(0,-1).forEach(pl=>ctx.fillRect(pl.x,pl.y,pl.w,12));\n  ctx.fillStyle="#2a2a6a";ctx.fillRect(0,440,W,40);\n  ctx.fillStyle="#f59e0b";\n  COINS.filter(c=>!c.collected).forEach(c=>{ctx.beginPath();ctx.arc(c.x,c.y,6,0,Math.PI*2);ctx.fill();});\n  ctx.fillStyle="#4ecca3";ctx.fillRect(p.x,p.y,28,40);\n  ctx.fillStyle="#fff";ctx.font="16px monospace";ctx.fillText("Score: "+score.get(),8,22);\n});\nloop.start();'

# Bad code samples: DOM manipulation instead of Canvas
DOM_SNAKE = 'const gameDiv = document.getElementById("game")!;\nlet snake = [{x:10,y:10}];\nlet dir = {x:1,y:0};\nfunction render() {\n  gameDiv.innerHTML = "";\n  snake.forEach(s => {\n    const d = document.createElement("div");\n    d.style.position = "absolute";\n    d.style.left = (s.x*20)+"px";\n    d.style.top = (s.y*20)+"px";\n    d.style.width = "18px";\n    d.style.height = "18px";\n    d.style.background = "green";\n    gameDiv.appendChild(d);\n  });\n}\ndocument.addEventListener("keydown", e => {\n  if(e.key==="ArrowLeft")dir={x:-1,y:0};\n  if(e.key==="ArrowRight")dir={x:1,y:0};\n});\nsetInterval(()=>{\n  const head={x:snake[0].x+dir.x,y:snake[0].y+dir.y};\n  snake.unshift(head);\n  snake.pop();\n  render();\n},150);'

DOM_PLATFORMER = 'import React, { useState, useEffect } from "react";\nconst GRAVITY = 0.5;\nexport default function Game() {\n  const [py, setPy] = useState(300);\n  const [vy, setVy] = useState(0);\n  const [px, setPx] = useState(100);\n  useEffect(() => {\n    const id = setInterval(() => {\n      setVy(v => v + GRAVITY);\n      setPy(y => {\n        const ny = y + vy;\n        if(ny >= 300) { setVy(0); return 300; }\n        return ny;\n      });\n    }, 16);\n    return () => clearInterval(id);\n  }, [vy]);\n  return (\n    <div style={{position:"relative",width:800,height:480,background:"#1a1a2e"}}>\n      <div style={{position:"absolute",left:px,top:py,width:28,height:40,background:"#4ecca3"}} />\n    </div>\n  );\n}'

# Bad: React rendering instead of tsunami-engine
REACT_TETRIS = 'import React, { useState, useEffect, useCallback } from "react";\nconst COLS=10, ROWS=20;\nexport default function Tetris() {\n  const [grid, setGrid] = useState(Array.from({length:ROWS},()=>Array(COLS).fill(0)));\n  const [score, setScore] = useState(0);\n  useEffect(() => {\n    const id = setInterval(() => {\n      setGrid(g => { return g; }); // tick\n    }, 500);\n    return () => clearInterval(id);\n  }, []);\n  return (\n    <div style={{display:"flex"}}>\n      <div style={{display:"grid",gridTemplateColumns:`repeat(${COLS},24px)`}}>\n        {grid.flat().map((c,i)=>(<div key={i} style={{width:24,height:24,background:c?"red":"#111",border:"1px solid #333"}}/>))}\n      </div>\n      <div>Score: {score}</div>\n    </div>\n  );\n}'


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
    return {"prompt": prompt_text, "chosen": chosen_response, "rejected": rejected_response,
            "images": [], "source_bug": source_bug, "note": note, "date": TODAY}


PAIRS = []

# ── GHF02: Research gate ─────────────────────────────────────────────────────
# "Build something like X" → search_web first, not project_init blindly
for i, (prompt, query) in enumerate([
    ("Build a Wordle clone — word guessing game like the NYT Wordle",
     "Wordle word guessing game mechanics rules green yellow gray tiles"),
    ("Build a Flappy Bird clone",
     "Flappy Bird game mechanics physics pipe gap scoring"),
    ("Build a game similar to 2048 — sliding number tiles",
     "2048 game mechanics tile merging rules scoring"),
]):
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]
    PAIRS.append(make_pair(msgs,
        chosen_fn="search_web", chosen_args={"query": query},
        rejected_fn="project_init", rejected_args={"name": prompt.split()[2].lower().replace(",","")},
        source_bug="GHF02-research-gate",
        note=f"ghf02-{i+1}: reference clone -> search_web first to understand mechanics, not project_init blindly",
    ))

# ── GHF03: Stall detection ───────────────────────────────────────────────────
# After 2 consecutive file_reads, must file_write (not read more)
for i, (game, name, code) in enumerate([
    ("a Tetris game", "tetris", TETRIS_TS),
    ("a Space Invaders game", "space-invaders", SPACE_INV_TS),
    ("a 2D platformer", "platformer", PLATFORMER_TS),
]):
    msgs = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": "Build "+game},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "type": "function",
            "function": {"name": "project_init", "arguments": json.dumps({"name": name})}}]},
        {"role": "tool", "tool_call_id": "c1",
         "content": f"[project_init] Created '{name}'. Write src/main.ts."},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "c2", "type": "function",
            "function": {"name": "file_read", "arguments": json.dumps({"path": f"deliverables/{name}/package.json"})}}]},
        {"role": "tool", "tool_call_id": "c2",
         "content": '{"name":"'+name+'","dependencies":{"tsunami-engine":"^1.0.0"},"scripts":{"build":"tsc && vite build"}}'},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "c3", "type": "function",
            "function": {"name": "file_read", "arguments": json.dumps({"path": f"deliverables/{name}/src/engine/index.ts"})}}]},
        {"role": "tool", "tool_call_id": "c3",
         "content": "export { FrameLoop } from './FrameLoop';\nexport { KeyboardInput } from './KeyboardInput';\nexport { ScoreSystem } from './ScoreSystem';"},
    ]
    PAIRS.append(make_pair(msgs,
        chosen_fn="file_write", chosen_args={"path": f"deliverables/{name}/src/main.ts", "content": code},
        rejected_fn="file_read", rejected_args={"path": f"deliverables/{name}/src/engine/FrameLoop.ts"},
        source_bug="GHF03-stall-detection",
        note=f"ghf03-{i+1}: after 2 file_reads -> file_write main.ts; reading more is stalling",
    ))

# ── GHF04: Code-write gate (additional pairs — different games from v3) ───────
for i, (game, name, code) in enumerate([
    ("a Tetris game with rotation and line clearing", "tetris", TETRIS_TS),
    ("a Space Invaders game with waves and a score system",    "space-invaders", SPACE_INV_TS),
    ("a 2D side-scrolling platformer with jumping and coins",  "platformer",     PLATFORMER_TS),
]):
    msgs = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": "Build "+game},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "type": "function",
            "function": {"name": "project_init", "arguments": json.dumps({"name": name})}}]},
        {"role": "tool", "tool_call_id": "c1",
         "content": f"[project_init] Created game project '{name}'. Write src/main.ts to implement the game."},
    ]
    PAIRS.append(make_pair(msgs,
        chosen_fn="file_write", chosen_args={"path": f"deliverables/{name}/src/main.ts", "content": code},
        rejected_fn="message_result", rejected_args={"text": name+" project scaffolded and ready to play."},
        source_bug="GHF04-code-write-gate",
        note=f"ghf04-v4-{i+1}: after project_init -> file_write main.ts with full game code, NOT deliver empty scaffold",
    ))

# ── GHF05: Shell loop detection ──────────────────────────────────────────────
# After 2 identical build failures → file_write (missing import fix), not retry shell
BUILD_FAIL = "[shell_exec] ERROR: src/main.ts(1,32): error TS2307: Cannot find module 'tsunami-engine' or its corresponding type declarations."
BUILD_FAIL2 = "[shell_exec] ERROR: src/main.ts(3,1): error TS2304: Cannot find name 'FrameLoop'."

FIX_IMPORT = 'import { FrameLoop, KeyboardInput, ScoreSystem } from "tsunami-engine";\n// (rest of game code follows)'

for i, (game, name, fail_msg) in enumerate([
    ("a snake game", "snake-game", BUILD_FAIL),
    ("a Pong game",  "pong-game",  BUILD_FAIL2),
    ("a platformer", "platformer", BUILD_FAIL),
]):
    msgs = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": "Build "+game},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "type": "function",
            "function": {"name": "project_init", "arguments": json.dumps({"name": name})}}]},
        {"role": "tool", "tool_call_id": "c1",
         "content": f"[project_init] Created '{name}'. Write src/main.ts."},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "c2", "type": "function",
            "function": {"name": "file_write", "arguments": json.dumps({"path": f"deliverables/{name}/src/main.ts", "content": "// game code placeholder"})}}]},
        {"role": "tool", "tool_call_id": "c2", "content": "Written."},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "c3", "type": "function",
            "function": {"name": "shell_exec", "arguments": json.dumps({"command": f"cd deliverables/{name} && npm run build"})}}]},
        {"role": "tool", "tool_call_id": "c3", "content": fail_msg},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "c4", "type": "function",
            "function": {"name": "shell_exec", "arguments": json.dumps({"command": f"cd deliverables/{name} && npm run build"})}}]},
        {"role": "tool", "tool_call_id": "c4", "content": fail_msg},
    ]
    PAIRS.append(make_pair(msgs,
        chosen_fn="file_edit", chosen_args={"path": f"deliverables/{name}/src/main.ts",
            "old_text": "// game code placeholder",
            "new_text": FIX_IMPORT},
        rejected_fn="shell_exec", rejected_args={"command": f"cd deliverables/{name} && npm run build"},
        source_bug="GHF05-shell-loop",
        note=f"ghf05-{i+1}: 2 identical build failures -> file_edit to fix missing import, NOT retry shell_exec",
    ))

# ── GHF07: Engine imports ─────────────────────────────────────────────────────
# file_write must use tsunami-engine imports; no React, no vanilla setInterval
REACT_TETRIS_BAD = REACT_TETRIS
DOM_GAME_BAD = DOM_SNAKE

for i, (game, name, good_code, bad_code) in enumerate([
    ("a Tetris game with rotation and line clearing", "tetris",    TETRIS_TS,     REACT_TETRIS_BAD),
    ("a snake game",                                  "snake-game", PLATFORMER_TS, DOM_SNAKE),
    ("a Space Invaders game",                         "space-inv",  SPACE_INV_TS,  DOM_PLATFORMER),
]):
    msgs = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": "Build "+game},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "type": "function",
            "function": {"name": "project_init", "arguments": json.dumps({"name": name})}}]},
        {"role": "tool", "tool_call_id": "c1",
         "content": f"[project_init] Created '{name}'. Write src/main.ts using tsunami-engine imports."},
    ]
    PAIRS.append(make_pair(msgs,
        chosen_fn="file_write", chosen_args={"path": f"deliverables/{name}/src/main.ts", "content": good_code},
        rejected_fn="file_write", rejected_args={"path": f"deliverables/{name}/src/main.ts", "content": bad_code},
        source_bug="GHF07-engine-imports",
        note=f"ghf07-{i+1}: file_write main.ts must use tsunami-engine FrameLoop/KeyboardInput, NOT React state or DOM manipulation",
    ))

# ── GHF08: Canvas 2D pattern ─────────────────────────────────────────────────
# Game rendering must use Canvas 2D ctx.fillRect etc, not DOM manipulation
for i, (game, name, good_code, bad_code) in enumerate([
    ("a snake game",                                  "snake-game",  PLATFORMER_TS,  DOM_SNAKE),
    ("a 2D platformer with jumping and platforms",    "platformer",  PLATFORMER_TS,  DOM_PLATFORMER),
    ("a Space Invaders game with enemy waves",        "space-inv",   SPACE_INV_TS,   DOM_PLATFORMER),
]):
    msgs = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": "Build "+game},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "type": "function",
            "function": {"name": "project_init", "arguments": json.dumps({"name": name})}}]},
        {"role": "tool", "tool_call_id": "c1",
         "content": f"[project_init] Created '{name}'. Write src/main.ts. Use Canvas 2D (ctx.getContext('2d')) for rendering."},
    ]
    PAIRS.append(make_pair(msgs,
        chosen_fn="file_write", chosen_args={"path": f"deliverables/{name}/src/main.ts", "content": good_code},
        rejected_fn="file_write", rejected_args={"path": f"deliverables/{name}/src/main.ts", "content": bad_code},
        source_bug="GHF08-canvas-2d",
        note=f"ghf08-{i+1}: game rendering must use Canvas 2D ctx.fillRect/arc, NOT DOM manipulation (div.style.left, innerHTML, React state)",
    ))


# ── Output ────────────────────────────────────────────────────────────────────
OUT_V4      = Path("workspace/training_data/gamedev_dpo_v4.jsonl")
OUT_COMBINED = Path("workspace/training_data/gamedev_dpo_combined_v3.jsonl")
OUT_V4.parent.mkdir(parents=True, exist_ok=True)

# Write v4 only
with open(OUT_V4, "w") as f:
    for p in PAIRS:
        f.write(json.dumps(p) + "\n")

# Load all previous DPO data and combine
prev_files = [
    Path("workspace/training_data/gamedev_dpo_v1.jsonl"),
    Path("workspace/training_data/gamedev_dpo_v2.jsonl"),
    Path("workspace/training_data/gamedev_dpo_v3.jsonl"),
    OUT_V4,
]
combined = []
for pf in prev_files:
    if pf.exists():
        with open(pf) as f:
            combined.extend(json.loads(l) for l in f if l.strip())

with open(OUT_COMBINED, "w") as f:
    for p in combined:
        f.write(json.dumps(p) + "\n")

print(f"\n=== GAMEDEV DPO v4 SUMMARY ===")
print(f"  v4 pairs: {len(PAIRS)}")
print(f"  Combined pairs: {len(combined)}")
print(f"  Output v4: {OUT_V4}")
print(f"  Output combined: {OUT_COMBINED}")
for p in PAIRS:
    print(f"  {p['source_bug']:30s}  {p['note']}")
