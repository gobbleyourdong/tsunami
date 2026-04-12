#!/usr/bin/env python3
"""Gamedev DPO pairs v3 — targeting 5 uncovered L4 GHF scenarios.

GHF01: Auto-scaffold — simple game prompt -> project_init immediately
GHF04: Code-write gate — after project_init -> file_write code (not empty scaffold)
GHF06: Conversation — greeting/question -> message_chat(done=True)
GHF11: Anti-R3F bypass — 3D game main.ts must use tsunami-engine, NOT react-three-fiber
GHF12: No R3F npm install — after project_init, file_write (don't npm install R3F)

Usage:
  /usr/bin/python3 training/build_gamedev_dpo_v3.py
"""
import json
from datetime import date
from pathlib import Path

print("Loading tokenizer (google/gemma-4-e4b-it)...")
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
- Use tsunami-engine for ALL games including 3D -- NEVER use react-three-fiber.
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

SNAKE = 'import { FrameLoop, KeyboardInput } from "tsunami-engine";\nconst T=20,C=20,R=20;\nlet sn=[{x:10,y:10}],dir={x:1,y:0},food={x:5,y:5},sc=0,run=true;\nconst cv=document.getElementById("canvas") as HTMLCanvasElement;\ncv.width=C*T; cv.height=R*T;\nconst ctx=cv.getContext("2d")!;\nconst kb=new KeyboardInput();\nkb.bind("ArrowUp",()=>{if(dir.y===0)dir={x:0,y:-1}});\nkb.bind("ArrowDown",()=>{if(dir.y===0)dir={x:0,y:1}});\nkb.bind("ArrowLeft",()=>{if(dir.x===0)dir={x:-1,y:0}});\nkb.bind("ArrowRight",()=>{if(dir.x===0)dir={x:1,y:0}});\nfunction spawnFood(){food={x:Math.floor(Math.random()*C),y:Math.floor(Math.random()*R)};}\nlet acc=0;\nconst loop=new FrameLoop();\nloop.onUpdate(({dt})=>{\n  if(!run)return;\n  acc+=dt; if(acc<0.12)return; acc=0;\n  const head={x:(sn[0].x+dir.x+C)%C,y:(sn[0].y+dir.y+R)%R};\n  if(sn.some(s=>s.x===head.x&&s.y===head.y)){run=false;return;}\n  sn.unshift(head);\n  if(head.x===food.x&&head.y===food.y){sc++;spawnFood();}else{sn.pop();}\n  ctx.fillStyle="#1a1a2e"; ctx.fillRect(0,0,cv.width,cv.height);\n  ctx.fillStyle="#4ecca3"; sn.forEach(s=>ctx.fillRect(s.x*T+1,s.y*T+1,T-2,T-2));\n  ctx.fillStyle="#e94560"; ctx.fillRect(food.x*T+2,food.y*T+2,T-4,T-4);\n  ctx.fillStyle="#fff"; ctx.font="16px monospace"; ctx.fillText("Score: "+sc,8,20);\n});\nloop.start();'

PONG = 'import { FrameLoop, KeyboardInput } from "tsunami-engine";\nconst W=800,H=500,PW=10,PH=80,BR=8,SPD=400;\nconst cv=document.getElementById("canvas") as HTMLCanvasElement;\ncv.width=W; cv.height=H;\nconst ctx=cv.getContext("2d")!;\nconst kb=new KeyboardInput();\nlet p1={y:H/2-PH/2},p2={y:H/2-PH/2},ball={x:W/2,y:H/2,vx:SPD,vy:200},s1=0,s2=0;\nconst loop=new FrameLoop();\nloop.onUpdate(({dt})=>{\n  if(kb.isDown("KeyW"))p1.y=Math.max(0,p1.y-500*dt);\n  if(kb.isDown("KeyS"))p1.y=Math.min(H-PH,p1.y+500*dt);\n  if(kb.isDown("ArrowUp"))p2.y=Math.max(0,p2.y-500*dt);\n  if(kb.isDown("ArrowDown"))p2.y=Math.min(H-PH,p2.y+500*dt);\n  ball.x+=ball.vx*dt; ball.y+=ball.vy*dt;\n  if(ball.y<=BR||ball.y>=H-BR)ball.vy*=-1;\n  if(ball.x<=12+PW&&ball.y>=p1.y&&ball.y<=p1.y+PH)ball.vx=Math.abs(ball.vx);\n  if(ball.x>=W-12-PW&&ball.y>=p2.y&&ball.y<=p2.y+PH)ball.vx=-Math.abs(ball.vx);\n  if(ball.x<0){s2++;ball={x:W/2,y:H/2,vx:SPD,vy:200};}\n  if(ball.x>W){s1++;ball={x:W/2,y:H/2,vx:-SPD,vy:200};}\n  ctx.fillStyle="#111"; ctx.fillRect(0,0,W,H);\n  ctx.fillStyle="#fff";\n  ctx.fillRect(12,p1.y,PW,PH); ctx.fillRect(W-12-PW,p2.y,PW,PH);\n  ctx.beginPath(); ctx.arc(ball.x,ball.y,BR,0,Math.PI*2); ctx.fill();\n  ctx.font="bold 32px monospace"; ctx.textAlign="center";\n  ctx.fillText(s1+" : "+s2,W/2,40);\n});\nloop.start();'

BREAKOUT = 'import { FrameLoop, KeyboardInput, ScoreSystem } from "tsunami-engine";\nconst W=640,H=480,BW=60,BH=18,PAD=100;\nconst cv=document.getElementById("canvas") as HTMLCanvasElement;\ncv.width=W; cv.height=H;\nconst ctx=cv.getContext("2d")!;\nconst kb=new KeyboardInput();\nconst score=new ScoreSystem();\nconst COLS2=["#e94560","#f5a623","#f8e71c","#7ed321","#4a90e2"];\nlet bricks=Array.from({length:5},(_,r)=>Array.from({length:8},(_,c)=>({x:c*64+20,y:r*22+60,alive:true,col:COLS2[r%5]})));\nlet pad={x:W/2-PAD/2,y:H-30},ball={x:W/2,y:H-60,vx:220,vy:-280};\nconst loop=new FrameLoop();\nloop.onUpdate(({dt})=>{\n  if(kb.isDown("ArrowLeft"))pad.x=Math.max(0,pad.x-480*dt);\n  if(kb.isDown("ArrowRight"))pad.x=Math.min(W-PAD,pad.x+480*dt);\n  ball.x+=ball.vx*dt; ball.y+=ball.vy*dt;\n  if(ball.x<=8||ball.x>=W-8)ball.vx*=-1;\n  if(ball.y<=8)ball.vy*=-1;\n  if(ball.y>=H)ball={x:W/2,y:H-60,vx:220,vy:-280};\n  if(ball.y+8>=pad.y&&ball.x>=pad.x&&ball.x<=pad.x+PAD)ball.vy=-Math.abs(ball.vy);\n  bricks.flat().filter(b=>b.alive).forEach(b=>{\n    if(ball.x>b.x&&ball.x<b.x+BW&&ball.y>b.y&&ball.y<b.y+BH){b.alive=false;ball.vy*=-1;score.add(10);}\n  });\n  ctx.fillStyle="#0d0d1a"; ctx.fillRect(0,0,W,H);\n  bricks.flat().filter(b=>b.alive).forEach(b=>{ctx.fillStyle=b.col;ctx.fillRect(b.x,b.y,BW,BH);});\n  ctx.fillStyle="#4ecca3"; ctx.fillRect(pad.x,pad.y,PAD,12);\n  ctx.beginPath(); ctx.arc(ball.x,ball.y,8,0,Math.PI*2); ctx.fillStyle="#fff"; ctx.fill();\n  ctx.fillStyle="#fff"; ctx.font="16px monospace"; ctx.textAlign="left";\n  ctx.fillText("Score: "+score.get(),8,24);\n});\nloop.start();'

# Raycaster maze using tsunami-engine FrameLoop (no R3F)
MAZE_TS = 'import { FrameLoop, KeyboardInput, Vec3 } from "tsunami-engine";\nconst MAP=[[1,1,1,1,1,1,1,1],[1,0,0,0,0,0,0,1],[1,0,1,1,0,1,0,1],[1,0,0,1,0,0,0,1],[1,0,1,0,0,1,0,1],[1,0,0,0,1,0,0,1],[1,0,1,0,0,0,0,1],[1,1,1,1,1,1,1,1]];\nconst W=800,H=500,FOV=Math.PI/3,RAYS=200;\nconst cv=document.getElementById("canvas") as HTMLCanvasElement;\ncv.width=W; cv.height=H;\nconst ctx=cv.getContext("2d")!;\nconst kb=new KeyboardInput();\nlet pos=Vec3.create(1.5,0,1.5),angle=0;\nconst loop=new FrameLoop();\nloop.onUpdate(({dt})=>{\n  const spd=3*dt,rot=2.2*dt;\n  if(kb.isDown("ArrowLeft"))angle-=rot;\n  if(kb.isDown("ArrowRight"))angle+=rot;\n  const fwd=kb.isDown("ArrowUp")?spd:kb.isDown("ArrowDown")?-spd:0;\n  const nx=pos[0]+Math.cos(angle)*fwd, nz=pos[2]+Math.sin(angle)*fwd;\n  if(MAP[Math.floor(nz)]?.[Math.floor(nx)]===0){pos[0]=nx;pos[2]=nz;}\n  ctx.fillStyle="#111"; ctx.fillRect(0,0,W,H/2);\n  ctx.fillStyle="#333"; ctx.fillRect(0,H/2,W,H/2);\n  for(let r=0;r<RAYS;r++){\n    const ray=angle-FOV/2+FOV*(r/RAYS);\n    let rx=pos[0],rz=pos[2],dist=0;\n    while(dist<20){rx+=Math.cos(ray)*0.05;rz+=Math.sin(ray)*0.05;dist+=0.05;\n      if(MAP[Math.floor(rz)]?.[Math.floor(rx)]===1)break;}\n    const h=Math.min(H,(H/dist)*0.8),sh=Math.floor(255/(1+dist*0.5));\n    ctx.fillStyle="rgb("+sh+","+(sh>>1)+","+(sh>>2)+")";\n    ctx.fillRect(r*(W/RAYS),H/2-h/2,W/RAYS+1,h);\n  }\n});\nloop.start();'

RUNNER_TS = 'import { FrameLoop, KeyboardInput, ScoreSystem } from "tsunami-engine";\nconst W=800,H=400,GND=320;\nconst cv=document.getElementById("canvas") as HTMLCanvasElement;\ncv.width=W; cv.height=H;\nconst ctx=cv.getContext("2d")!;\nconst kb=new KeyboardInput();\nconst score=new ScoreSystem();\nlet player={x:80,y:GND,vy:0,grounded:true},obs:{x:number,w:number,h:number}[]=[];\nlet speed=280,dist=0,alive=true,spawn=1.2;\nkb.bind("Space",()=>{if(player.grounded){player.vy=-620;player.grounded=false;}});\nkb.bind("ArrowUp",()=>{if(player.grounded){player.vy=-620;player.grounded=false;}});\nconst loop=new FrameLoop();\nloop.onUpdate(({dt})=>{\n  if(!alive)return;\n  speed=280+dist*0.04; dist+=speed*dt; score.set(Math.floor(dist/10));\n  player.vy+=1400*dt; player.y+=player.vy*dt;\n  if(player.y>=GND){player.y=GND;player.vy=0;player.grounded=true;}\n  spawn-=dt;\n  if(spawn<=0){obs.push({x:W+20,w:20+Math.random()*20,h:40+Math.random()*60});spawn=0.8+Math.random()*1.2;}\n  obs.forEach(o=>o.x-=speed*dt);\n  obs=obs.filter(o=>o.x>-60);\n  for(const o of obs){if(player.x+26>o.x&&player.x+6<o.x+o.w&&player.y+44>H-o.h)alive=false;}\n  ctx.fillStyle="#1a1a2e"; ctx.fillRect(0,0,W,H);\n  ctx.fillStyle="#4ecca3"; ctx.fillRect(player.x,player.y,32,48);\n  ctx.fillStyle="#e94560"; obs.forEach(o=>ctx.fillRect(o.x,H-o.h,o.w,o.h));\n  ctx.fillStyle="#fff"; ctx.font="18px monospace"; ctx.textAlign="left";\n  ctx.fillText("Score: "+score.get(),8,28);\n});\nloop.start();'

# Rejected: react-three-fiber approach
R3F_MAZE = 'import { Canvas } from "react-three-fiber";\nimport { useRef } from "react";\nimport * as THREE from "three";\nexport default function App() {\n  return (\n    <Canvas camera={{ fov: 75, position: [0, 5, 5] }}>\n      <ambientLight />\n      <mesh position={[0,0,0]}><boxGeometry args={[1,1,1]}/><meshStandardMaterial color="gray"/></mesh>\n    </Canvas>\n  );\n}'

R3F_RUNNER = 'import { Canvas, useFrame } from "react-three-fiber";\nimport { useRef } from "react";\nfunction Player() {\n  const ref = useRef<any>(null);\n  useFrame((_state, delta) => { if(ref.current) ref.current.position.y += delta; });\n  return <mesh ref={ref}><boxGeometry args={[0.5,1,0.3]}/><meshStandardMaterial color="cyan"/></mesh>;\n}\nexport default function App() {\n  return <Canvas><ambientLight intensity={0.5}/><Player/></Canvas>;\n}'


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

# GHF01: Auto-scaffold
for i, (game, name) in enumerate([
    ("a snake game", "snake"),
    ("a Pong game", "pong"),
    ("a Breakout game", "breakout"),
]):
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": "Build "+game}]
    PAIRS.append(make_pair(msgs,
        chosen_fn="project_init", chosen_args={"name": name},
        rejected_fn="search_web", rejected_args={"query": game+" typescript canvas tutorial"},
        source_bug="GHF01-auto-scaffold",
        note=f"ghf01-{i+1}: simple game prompt -> project_init immediately, not search_web",
    ))

# GHF04: Code-write gate
for i, (game, name, code) in enumerate([
    ("a snake game",    "snake",    SNAKE),
    ("a pong game",     "pong",     PONG),
    ("a breakout game", "breakout", BREAKOUT),
]):
    msgs = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": "Build "+game},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "type": "function",
            "function": {"name": "project_init", "arguments": json.dumps({"name": name})}}]},
        {"role": "tool", "tool_call_id": "c1",
         "content": f"[project_init] Created game project '{name}'. Write src/main.ts."},
    ]
    PAIRS.append(make_pair(msgs,
        chosen_fn="file_write", chosen_args={"path": f"deliverables/{name}/src/main.ts", "content": code},
        rejected_fn="message_result", rejected_args={"text": name+" scaffolded and ready."},
        source_bug="GHF04-code-write-gate",
        note=f"ghf04-{i+1}: after project_init -> file_write main.ts, NOT message_result empty scaffold",
    ))

# GHF06: Conversation
for i, (prompt, reply) in enumerate([
    ("Hello! What kinds of games can you build?",
     "I can build any 2D or 3D game: platformers, shooters, puzzle games, RPGs, endless runners, and more. Just tell me what you want."),
    ("Nice work on that snake game!",
     "Thanks! Let me know if you want to add features or build something new."),
    ("Can you explain how the FrameLoop works?",
     "FrameLoop drives the update cycle. Register your update with loop.onUpdate(({dt}) => { ... }) then call loop.start(). dt is delta time in seconds, synced to requestAnimationFrame."),
]):
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]
    PAIRS.append(make_pair(msgs,
        chosen_fn="message_chat", chosen_args={"text": reply, "done": True},
        rejected_fn="project_init", rejected_args={"name": "game"},
        source_bug="GHF06-conversation",
        note=f"ghf06-{i+1}: greeting/question -> message_chat(done=True), NOT project_init",
    ))

# GHF11: Anti-R3F bypass
for i, (game, name, good_code, bad_code) in enumerate([
    ("a 3D first-person maze game with WASD controls", "fps-maze",       MAZE_TS,   R3F_MAZE),
    ("an endless runner game",                          "endless-runner", RUNNER_TS, R3F_RUNNER),
    ("a 3D space shooter with asteroids",               "space-shooter",  MAZE_TS,   R3F_MAZE),
]):
    msgs = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": "Build "+game},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "type": "function",
            "function": {"name": "project_init", "arguments": json.dumps({"name": name})}}]},
        {"role": "tool", "tool_call_id": "c1",
         "content": f"[project_init] Created game project '{name}'. Write src/main.ts using tsunami-engine."},
    ]
    PAIRS.append(make_pair(msgs,
        chosen_fn="file_write", chosen_args={"path": f"deliverables/{name}/src/main.ts", "content": good_code},
        rejected_fn="file_write", rejected_args={"path": f"deliverables/{name}/src/main.ts", "content": bad_code},
        source_bug="GHF11-anti-r3f-bypass",
        note=f"ghf11-{i+1}: 3D game main.ts must use tsunami-engine, NOT react-three-fiber",
    ))

# GHF12: No R3F npm install
for i, (game, name, good_code, npm_bad) in enumerate([
    ("a 3D first-person maze",    "fps-maze",       MAZE_TS,   "cd deliverables/fps-maze && npm install react-three-fiber three"),
    ("an endless runner",          "endless-runner", RUNNER_TS, "cd deliverables/endless-runner && npm install react-three-fiber three"),
    ("a 3D space shooter",         "space-shooter",  MAZE_TS,   "cd deliverables/space-shooter && npm install react-three-fiber three"),
]):
    msgs = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": "Build "+game},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "type": "function",
            "function": {"name": "project_init", "arguments": json.dumps({"name": name})}}]},
        {"role": "tool", "tool_call_id": "c1",
         "content": f"[project_init] Created game project '{name}'. Write src/main.ts."},
    ]
    PAIRS.append(make_pair(msgs,
        chosen_fn="file_write", chosen_args={"path": f"deliverables/{name}/src/main.ts", "content": good_code},
        rejected_fn="shell_exec", rejected_args={"command": npm_bad},
        source_bug="GHF12-no-r3f-npm",
        note=f"ghf12-{i+1}: after project_init -> file_write main.ts with tsunami-engine, NOT npm install react-three-fiber",
    ))


OUT_V3 = Path("workspace/training_data/gamedev_dpo_v3.jsonl")
OUT_COMBINED = Path("workspace/training_data/gamedev_dpo_combined_v2.jsonl")
OUT_V3.parent.mkdir(parents=True, exist_ok=True)

with open(OUT_V3, "w") as f:
    for p in PAIRS:
        f.write(json.dumps(p) + "\n")

existing = Path("workspace/training_data/gamedev_dpo_combined_v1.jsonl")
all_lines = []
if existing.exists():
    all_lines.extend(existing.read_text().splitlines())
all_lines.extend(OUT_V3.read_text().splitlines())
OUT_COMBINED.write_text("\n".join(l for l in all_lines if l.strip()) + "\n")

counts = {
    "ghf01-auto-scaffold":   sum(1 for p in PAIRS if "ghf01" in p["note"]),
    "ghf04-code-write-gate": sum(1 for p in PAIRS if "ghf04" in p["note"]),
    "ghf06-conversation":    sum(1 for p in PAIRS if "ghf06" in p["note"]),
    "ghf11-anti-r3f":        sum(1 for p in PAIRS if "ghf11" in p["note"]),
    "ghf12-no-r3f-npm":      sum(1 for p in PAIRS if "ghf12" in p["note"]),
}
print(f"\n=== GAMEDEV DPO v3 SUMMARY ===")
print(f"  New pairs: {len(PAIRS)}")
print(f"  v3 file: {OUT_V3}")
combined_count = sum(1 for l in OUT_COMBINED.read_text().splitlines() if l.strip())
print(f"  Combined v2: {OUT_COMBINED} ({combined_count} total pairs)")
for k, v in counts.items():
    print(f"  {k}: {v}")
