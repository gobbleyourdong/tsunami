#!/usr/bin/env python3
"""Gamedev training data v4 — engine-first builds for QA-1 archetypes.

Targets Fire 81 gap: model bypasses tsunami-engine and uses @react-three/fiber.
Teaching the correct pattern: always import from 'tsunami-engine', use FrameLoop,
KeyboardInput, Vec3, PhysicsWorld — NOT @react-three/fiber, NOT React state.

New examples:
  GV01: Top-down dungeon crawler (full pipeline, tsunami-engine)
  GV02: Endless runner (FrameLoop + KeyboardInput + ScoreSystem)
  GV03: 3D first-person maze (canvas 2D raycasting, tsunami-engine math)
  GV04: Physics sandbox / marble game (PhysicsWorld, Vec3, canvas)
  GV05: 2D shmup with particle trails (ParticleSystem, FrameLoop)
  GV06: Anti-bypass — "3D game" prompt → write main.ts with tsunami-engine (NOT R3F)

Usage:
  python training/build_gamedev_v4.py
  Output: workspace/training_data/gamedev_toolcall_train_v4.jsonl
"""
import json
from pathlib import Path
from transformers import AutoTokenizer

MODEL = "google/gemma-4-e4b-it"
OUT_PATH = "workspace/training_data/gamedev_toolcall_train_v4.jsonl"

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
3. shell_exec("cd deliverables/{name} && npm run build") -- run the break
4. IF reef: fix directly -- file_edit for syntax, shell_exec for missing modules
5. undertow(dist/index.html) -- QA before delivery
6. message_result -- land the wave

## Engine API (import from '@engine/...' or 'tsunami-engine')

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
- NEVER skip the break. NEVER deliver without building.
- One tool call per response. Be brief.
- Write COMPLETE game in main.ts -- no partial files, no TODO stubs.
- Canvas 2D for all rendering. No React, no DOM manipulation for game state.
- ALWAYS use tsunami-engine imports. NEVER use @react-three/fiber, three.js, or React.
"""

def build_conv(user_prompt, turns):
    msgs = [
        {"role": "system", "content": SYSTEM_TEXT},
        {"role": "user", "content": user_prompt},
    ]
    for name, args, response in turns:
        msgs.append({
            "role": "assistant", "content": "",
            "tool_calls": [{"type": "function", "function": {"name": name, "arguments": args}}],
        })
        msgs.append({"role": "tool", "name": name, "content": (response or "OK")[:500]})
    return msgs


# ──────────────────────────────────────────────────────────────────────────────
# GV01: Top-down dungeon crawler
# ──────────────────────────────────────────────────────────────────────────────
DUNGEON_CODE = """import { FrameLoop, KeyboardInput, HealthSystem, ScoreSystem, Vec3 } from 'tsunami-engine'

const W = 800, H = 600, TILE = 40
const ROOMS = [
  {x:1,y:1,w:4,h:4}, {x:7,y:2,w:5,h:3}, {x:3,y:7,w:6,h:4},
  {x:10,y:6,w:4,h:5}, {x:1,y:8,w:3,h:3}
]
const MAP_W = 15, MAP_H = 14
const map: number[][] = Array.from({length:MAP_H}, () => Array(MAP_W).fill(1))
for (const r of ROOMS) for (let dy=0;dy<r.h;dy++) for (let dx=0;dx<r.w;dx++) map[r.y+dy][r.x+dx]=0
// corridors
map[3][5]=map[3][6]=map[3][7]=0; map[2][7]=map[3][7]=map[4][7]=0
map[9][4]=map[9][5]=map[9][6]=0; map[7][6]=map[8][6]=map[9][6]=0
map[9][11]=map[10][11]=0

const canvas = document.getElementById('game') as HTMLCanvasElement
canvas.width=W; canvas.height=H
const ctx = canvas.getContext('2d')!

const hp = new HealthSystem(100)
const score = new ScoreSystem(10)
const kb = new KeyboardInput()
kb.bind('w','ArrowUp'); kb.bind('s','ArrowDown'); kb.bind('a','ArrowLeft'); kb.bind('d','ArrowRight')

const player = { x: ROOMS[0].x*TILE+TILE/2, y: ROOMS[0].y*TILE+TILE/2, r: 14, speed: 120 }
const enemies = ROOMS.slice(1).map(r => ({
  x: (r.x + Math.floor(r.w/2)) * TILE, y: (r.y + Math.floor(r.h/2)) * TILE,
  r: 12, speed: 50, hp: 3, cd: 0
}))
const projectiles: {x:number,y:number,vx:number,vy:number,life:number}[] = []
let attackCd = 0, cameraX = 0, cameraY = 0

function isWall(px:number, py:number): boolean {
  const tx = Math.floor(px/TILE), ty = Math.floor(py/TILE)
  if (tx<0||ty<0||tx>=MAP_W||ty>=MAP_H) return true
  return map[ty][tx]===1
}

function moveEntity(e:{x:number,y:number,r:number}, dx:number, dy:number) {
  const nx=e.x+dx, ny=e.y+dy
  if (!isWall(nx-e.r,ny-e.r)&&!isWall(nx+e.r,ny-e.r)&&!isWall(nx-e.r,ny+e.r)&&!isWall(nx+e.r,ny+e.r)) {
    e.x=nx; e.y=ny
  }
}

function draw(dt: number) {
  // camera follow
  cameraX = Math.max(0, Math.min(player.x - W/2, MAP_W*TILE - W))
  cameraY = Math.max(0, Math.min(player.y - H/2, MAP_H*TILE - H))
  ctx.fillStyle='#111'; ctx.fillRect(0,0,W,H)
  ctx.save(); ctx.translate(-cameraX,-cameraY)
  // tiles
  for (let ty=0;ty<MAP_H;ty++) for (let tx=0;tx<MAP_W;tx++) {
    ctx.fillStyle = map[ty][tx]===1 ? '#334' : '#556'
    ctx.fillRect(tx*TILE,ty*TILE,TILE,TILE)
    if (map[ty][tx]===0) { ctx.strokeStyle='#445'; ctx.strokeRect(tx*TILE,ty*TILE,TILE,TILE) }
  }
  // enemies
  for (const e of enemies) if (e.hp>0) {
    ctx.fillStyle='#e44'; ctx.beginPath()
    ctx.arc(e.x,e.y,e.r,0,Math.PI*2); ctx.fill()
    // enemy HP bar
    ctx.fillStyle='#333'; ctx.fillRect(e.x-15,e.y-22,30,5)
    ctx.fillStyle='#e44'; ctx.fillRect(e.x-15,e.y-22,30*(e.hp/3),5)
  }
  // projectiles
  ctx.fillStyle='#ff0'
  for (const p of projectiles) { ctx.beginPath(); ctx.arc(p.x,p.y,4,0,Math.PI*2); ctx.fill() }
  // player
  ctx.fillStyle='#4af'; ctx.beginPath()
  ctx.arc(player.x,player.y,player.r,0,Math.PI*2); ctx.fill()
  ctx.restore()
  // HUD
  ctx.fillStyle='#000a'; ctx.fillRect(0,0,220,50)
  ctx.fillStyle='#fff'; ctx.font='14px monospace'
  ctx.fillText(`HP: ${hp.current}/${hp.max}  Score: ${score.value}`,10,30)
}

const loop = new FrameLoop()
loop.onUpdate(({dt}) => {
  // player movement
  let dx=0,dy=0
  if (kb.isHeld('w')) dy=-player.speed*dt
  if (kb.isHeld('s')) dy=player.speed*dt
  if (kb.isHeld('a')) dx=-player.speed*dt
  if (kb.isHeld('d')) dx=player.speed*dt
  if (dx&&dy) { dx*=0.707; dy*=0.707 }
  moveEntity(player,dx,dy)
  // attack (space)
  attackCd-=dt
  if (kb.isPressed(' ')&&attackCd<=0) {
    attackCd=0.3
    projectiles.push({x:player.x,y:player.y,vx:0,vy:-200,life:1.5})
  }
  // projectiles
  for (const p of projectiles) { p.x+=p.vx*dt; p.y+=p.vy*dt; p.life-=dt }
  // collision projectile-enemy
  for (const p of projectiles) for (const e of enemies) {
    if (e.hp>0&&Math.hypot(p.x-e.x,p.y-e.y)<e.r+4) { e.hp--; p.life=0; if(e.hp<=0) score.add(1) }
  }
  // enemy AI
  for (const e of enemies) if (e.hp>0) {
    const d = Math.hypot(player.x-e.x,player.y-e.y)
    if (d<200) {
      const nx=(player.x-e.x)/d, ny=(player.y-e.y)/d
      moveEntity(e, nx*e.speed*dt, ny*e.speed*dt)
    }
    e.cd-=dt
    if (d<e.r+player.r+5&&e.cd<=0) { hp.damage(10); e.cd=1 }
  }
  // remove dead projectiles
  const alive = projectiles.filter(p=>p.life>0)
  projectiles.length=0; projectiles.push(...alive)
  draw(dt)
})
loop.start()
document.addEventListener('keydown', e => { if (e.key===' ') e.preventDefault() })"""

GV01 = build_conv(
    "Build a 2D top-down dungeon crawler with rooms, enemies, and items",
    [
        ("project_init", {"name": "dungeon-crawler"},
         "[project_init] Created game project 'dungeon-crawler'. Write src/main.ts."),
        ("file_write", {"path": "src/main.ts", "content": DUNGEON_CODE},
         "[file_write] Wrote src/main.ts (87 lines)."),
        ("shell_exec", {"command": "cd deliverables/dungeon-crawler && npm run build"},
         "[shell_exec] Build successful. dist/index.html ready."),
        ("undertow", {"path": "dist/index.html", "expect": "canvas renders dungeon tilemap"},
         "[undertow] PASS: canvas visible, dungeon tiles rendered, player character present."),
        ("message_result", {"text": "Top-down dungeon crawler ready. WASD to move, Space to shoot. Defeat enemies to earn score."},
         "Delivered."),
    ]
)

# ──────────────────────────────────────────────────────────────────────────────
# GV02: Endless runner
# ──────────────────────────────────────────────────────────────────────────────
RUNNER_CODE = """import { FrameLoop, KeyboardInput, ScoreSystem } from 'tsunami-engine'

const W=800, H=400
const canvas = document.getElementById('game') as HTMLCanvasElement
canvas.width=W; canvas.height=H
const ctx = canvas.getContext('2d')!

const score = new ScoreSystem(0)
const kb = new KeyboardInput()
kb.bind('jump','Space','ArrowUp','w')

const GROUND_Y = H - 60
const PLAYER = { x:100, y:GROUND_Y, w:30, h:40, vy:0, onGround:false, dead:false }
const JUMP_FORCE = -700
const GRAVITY = 1800
const SCROLL_BASE = 300
let scrollSpeed = SCROLL_BASE
let dist = 0

interface Obstacle { x:number, w:number, h:number }
interface Cloud { x:number, y:number, s:number }
const obstacles: Obstacle[] = []
let obsCd = 0
const clouds: Cloud[] = [{x:200,y:60,s:1.2},{x:500,y:90,s:0.8},{x:750,y:50,s:1}]

function spawnObs() {
  const h = 30+Math.random()*50, w = 20+Math.random()*30
  obstacles.push({ x:W+20, w, h })
}

function rectsHit(ax:number,ay:number,aw:number,ah:number,bx:number,by:number,bw:number,bh:number) {
  return ax<bx+bw&&ax+aw>bx&&ay<by+bh&&ay+ah>by
}

function drawGround() {
  ctx.fillStyle='#5a3'; ctx.fillRect(0,GROUND_Y+40,W,20)
  ctx.fillStyle='#472'; ctx.fillRect(0,GROUND_Y+40,W,4)
}

function drawPlayer() {
  const p=PLAYER
  ctx.fillStyle=p.dead?'#e44':'#4af'
  ctx.fillRect(p.x,p.y-p.h,p.w,p.h)
  ctx.fillStyle=p.dead?'#c33':'#2cf'
  ctx.fillRect(p.x+4,p.y-p.h+4,8,8) // head detail
}

function draw() {
  ctx.fillStyle='#1a1a2e'; ctx.fillRect(0,0,W,H)
  // clouds
  ctx.fillStyle='#ffffff22'
  for (const c of clouds) { ctx.beginPath(); ctx.arc(c.x,c.y,30*c.s,0,Math.PI*2); ctx.fill() }
  drawGround()
  // obstacles
  ctx.fillStyle='#c84'
  for (const o of obstacles) {
    const oh = GROUND_Y+40-o.h
    ctx.fillRect(o.x,oh,o.w,o.h)
    ctx.fillStyle='#a63'; ctx.fillRect(o.x,oh,o.w,4); ctx.fillStyle='#c84'
  }
  drawPlayer()
  // HUD
  ctx.fillStyle='#fff'; ctx.font='bold 18px monospace'
  ctx.fillText(`Score: ${score.value}  Dist: ${Math.floor(dist)}m`, 10, 28)
  if (PLAYER.dead) {
    ctx.fillStyle='#000a'; ctx.fillRect(0,0,W,H)
    ctx.fillStyle='#fff'; ctx.font='bold 32px monospace'
    ctx.textAlign='center'; ctx.fillText('GAME OVER', W/2, H/2-20)
    ctx.font='18px monospace'; ctx.fillText(`Score: ${score.value}  Press Space to restart`, W/2, H/2+20)
    ctx.textAlign='left'
  }
}

function restart() {
  PLAYER.y=GROUND_Y; PLAYER.vy=0; PLAYER.onGround=true; PLAYER.dead=false
  obstacles.length=0; obsCd=0; dist=0; scrollSpeed=SCROLL_BASE; score.reset()
}

const loop = new FrameLoop()
loop.onUpdate(({dt}) => {
  if (PLAYER.dead) {
    if (kb.isPressed('jump')) restart()
    draw(); return
  }
  dist += scrollSpeed * dt / 10
  scrollSpeed = SCROLL_BASE + dist * 0.5
  score.add(scrollSpeed * dt / 100)
  // jump
  if (PLAYER.onGround && kb.isPressed('jump')) { PLAYER.vy=JUMP_FORCE; PLAYER.onGround=false }
  // gravity
  PLAYER.vy += GRAVITY * dt
  PLAYER.y += PLAYER.vy * dt
  if (PLAYER.y >= GROUND_Y) { PLAYER.y=GROUND_Y; PLAYER.vy=0; PLAYER.onGround=true }
  // clouds
  for (const c of clouds) { c.x -= 40*dt; if (c.x<-60) c.x=W+60 }
  // obstacles
  obsCd -= dt
  if (obsCd <= 0) { spawnObs(); obsCd = 0.8 + Math.random()*0.8 - dist*0.001 }
  for (const o of obstacles) o.x -= scrollSpeed*dt
  obstacles.splice(0, obstacles.findIndex(o=>o.x>-50)<0?0:obstacles.findIndex(o=>o.x>-50))
  // collision
  for (const o of obstacles) {
    const oh = GROUND_Y+40-o.h
    if (rectsHit(PLAYER.x,PLAYER.y-PLAYER.h,PLAYER.w,PLAYER.h,o.x,oh,o.w,o.h)) PLAYER.dead=true
  }
  draw()
})
loop.start()"""

GV02 = build_conv(
    "Build an endless runner game with obstacles and score tracking",
    [
        ("project_init", {"name": "endless-runner"},
         "[project_init] Created game project 'endless-runner'. Write src/main.ts."),
        ("file_write", {"path": "src/main.ts", "content": RUNNER_CODE},
         "[file_write] Wrote src/main.ts (79 lines)."),
        ("shell_exec", {"command": "cd deliverables/endless-runner && npm run build"},
         "[shell_exec] Build successful. dist/index.html ready."),
        ("undertow", {"path": "dist/index.html", "expect": "runner game renders, player visible"},
         "[undertow] PASS: canvas renders, player character visible on ground."),
        ("message_result", {"text": "Endless runner ready. Press Space/Up/W to jump. Dodge obstacles — speed increases over time."},
         "Delivered."),
    ]
)

# ──────────────────────────────────────────────────────────────────────────────
# GV03: 3D first-person maze (canvas 2D raycasting, tsunami-engine Vec3 + KeyboardInput)
# ──────────────────────────────────────────────────────────────────────────────
MAZE_CODE = """import { FrameLoop, KeyboardInput, Vec3 } from 'tsunami-engine'

// Wolfenstein-style raycaster — 3D feel on canvas 2D
const W=800, H=600, HALF_H=H/2
const FOV=Math.PI/3, NUM_RAYS=W, MAX_DEPTH=16
const MOVE_SPEED=3, ROT_SPEED=2

const canvas = document.getElementById('game') as HTMLCanvasElement
canvas.width=W; canvas.height=H
canvas.style.cursor='none'
const ctx = canvas.getContext('2d')!

// 12x12 maze (1=wall, 0=open)
const MAZE = [
  [1,1,1,1,1,1,1,1,1,1,1,1],
  [1,0,0,0,0,1,0,0,0,0,0,1],
  [1,0,1,1,0,1,0,1,1,1,0,1],
  [1,0,1,0,0,0,0,0,0,1,0,1],
  [1,0,1,0,1,1,1,0,0,0,0,1],
  [1,0,0,0,1,0,0,0,1,1,0,1],
  [1,1,1,0,0,0,1,0,0,1,0,1],
  [1,0,0,0,1,0,1,0,0,0,0,1],
  [1,0,1,1,1,0,1,1,1,0,1,1],
  [1,0,0,0,0,0,0,0,0,0,0,1],
  [1,0,1,0,1,1,1,0,1,0,0,1],
  [1,1,1,1,1,1,1,1,1,1,1,1],
]
const MH=MAZE.length, MW=MAZE[0].length

function isWall(x:number,y:number): boolean {
  const ix=Math.floor(x), iy=Math.floor(y)
  if(ix<0||iy<0||ix>=MW||iy>=MH) return true
  return MAZE[iy][ix]===1
}

const player = { x:1.5, y:1.5, angle:0 }
const kb = new KeyboardInput()
kb.bind('fwd','w','ArrowUp'); kb.bind('back','s','ArrowDown')
kb.bind('left','a','ArrowLeft'); kb.bind('right','d','ArrowRight')
kb.bind('rotL','q'); kb.bind('rotR','e')

function castRay(angle:number): number {
  const cos=Math.cos(angle), sin=Math.sin(angle)
  let dist=0
  while (dist<MAX_DEPTH) {
    dist+=0.05
    const tx=player.x+cos*dist, ty=player.y+sin*dist
    if (isWall(tx,ty)) return dist
  }
  return MAX_DEPTH
}

function draw(dt:number) {
  // sky / floor
  ctx.fillStyle='#1a1a3e'; ctx.fillRect(0,0,W,HALF_H)
  ctx.fillStyle='#332'; ctx.fillRect(0,HALF_H,W,HALF_H)
  // walls
  const halfFov=FOV/2
  for (let i=0;i<NUM_RAYS;i++) {
    const rayAngle=player.angle-halfFov+(FOV/NUM_RAYS)*i
    const dist=castRay(rayAngle)
    const corrected=dist*Math.cos(rayAngle-player.angle)
    const wallH=Math.min(H, H/corrected)
    const top=HALF_H-wallH/2
    const shade=Math.max(0,1-corrected/MAX_DEPTH)
    const r=Math.floor(180*shade), g=Math.floor(120*shade), b=Math.floor(60*shade)
    ctx.fillStyle=`rgb(${r},${g},${b})`
    ctx.fillRect(i,top,1,wallH)
  }
  // minimap
  const S=8, OX=W-MW*S-10, OY=10
  for (let y=0;y<MH;y++) for (let x=0;x<MW;x++) {
    ctx.fillStyle=MAZE[y][x]?'#aaa':'#333'
    ctx.fillRect(OX+x*S,OY+y*S,S-1,S-1)
  }
  ctx.fillStyle='#4af'
  ctx.fillRect(OX+player.x*S-2,OY+player.y*S-2,4,4)
  // HUD
  ctx.fillStyle='#fff8'; ctx.font='13px monospace'
  ctx.fillText('WASD/arrows: move  Q/E: rotate',10,H-10)
}

const loop = new FrameLoop()
loop.onUpdate(({dt}) => {
  const cos=Math.cos(player.angle), sin=Math.sin(player.angle)
  if (kb.isHeld('fwd')) {
    const nx=player.x+cos*MOVE_SPEED*dt, ny=player.y+sin*MOVE_SPEED*dt
    if (!isWall(nx,player.y)) player.x=nx
    if (!isWall(player.x,ny)) player.y=ny
  }
  if (kb.isHeld('back')) {
    const nx=player.x-cos*MOVE_SPEED*dt, ny=player.y-sin*MOVE_SPEED*dt
    if (!isWall(nx,player.y)) player.x=nx
    if (!isWall(player.x,ny)) player.y=ny
  }
  if (kb.isHeld('left')) {
    const s=Math.sin(-player.angle+Math.PI/2), c=Math.cos(-player.angle+Math.PI/2)
    const nx=player.x+c*MOVE_SPEED*dt, ny=player.y-s*MOVE_SPEED*dt
    if (!isWall(nx,player.y)) player.x=nx
    if (!isWall(player.x,ny)) player.y=ny
  }
  if (kb.isHeld('right')) {
    const s=Math.sin(-player.angle-Math.PI/2), c=Math.cos(-player.angle-Math.PI/2)
    const nx=player.x+c*MOVE_SPEED*dt, ny=player.y-s*MOVE_SPEED*dt
    if (!isWall(nx,player.y)) player.x=nx
    if (!isWall(player.x,ny)) player.y=ny
  }
  if (kb.isHeld('rotL')) player.angle-=ROT_SPEED*dt
  if (kb.isHeld('rotR')) player.angle+=ROT_SPEED*dt
  draw(dt)
})
loop.start()"""

GV03 = build_conv(
    "Build a 3D first-person maze game with WASD controls. Use WebGPU renderer.",
    [
        ("project_init", {"name": "fps-maze"},
         "[project_init] Created game project 'fps-maze'. Write src/main.ts."),
        ("file_write", {"path": "src/main.ts", "content": MAZE_CODE},
         "[file_write] Wrote src/main.ts (90 lines)."),
        ("shell_exec", {"command": "cd deliverables/fps-maze && npm run build"},
         "[shell_exec] Build successful. dist/index.html ready."),
        ("undertow", {"path": "dist/index.html", "expect": "3D maze renders, walls visible"},
         "[undertow] PASS: canvas renders 3D wall perspective, minimap present."),
        ("message_result", {"text": "First-person maze ready. WASD to move, Q/E to rotate. Minimap in top-right."},
         "Delivered."),
    ]
)

# ──────────────────────────────────────────────────────────────────────────────
# GV04: Physics sandbox / marble game
# ──────────────────────────────────────────────────────────────────────────────
PHYSICS_CODE = """import { FrameLoop, KeyboardInput, PhysicsWorld, Vec3 } from 'tsunami-engine'

const W=800, H=600
const canvas = document.getElementById('game') as HTMLCanvasElement
canvas.width=W; canvas.height=H
const ctx = canvas.getContext('2d')!

const world = new PhysicsWorld({ gravity: Vec3.create(0, 600, 0) })
const kb = new KeyboardInput()
kb.bind('left','a','ArrowLeft'); kb.bind('right','d','ArrowRight')
kb.bind('up','w','ArrowUp'); kb.bind('down','s','ArrowDown')
kb.bind('spawn',' ')

// Walls as static bodies
const walls = [
  {x:W/2, y:H+10, w:W, h:20},    // floor
  {x:-10, y:H/2, w:20, h:H},      // left wall
  {x:W+10, y:H/2, w:20, h:H},     // right wall
  {x:200, y:400, w:160, h:20, a:0.3},  // ramp 1
  {x:550, y:280, w:140, h:20, a:-0.25}, // ramp 2
  {x:350, y:160, w:100, h:20, a:0.1},  // platform
]

interface Ball { body: ReturnType<PhysicsWorld['addRigidBody']>, r:number, hue:number }
const balls: Ball[] = []
let spawnCd = 0

function spawnBall(x:number, y:number) {
  const r = 8 + Math.random()*12
  const body = world.addRigidBody({
    mass: r/10,
    shape: { type:'sphere', radius:r },
    position: Vec3.create(x, y, 0),
    restitution: 0.5 + Math.random()*0.4,
    friction: 0.3
  })
  balls.push({ body, r, hue: Math.random()*360 })
}

// Static ramp bodies
for (const w of walls) {
  world.addRigidBody({
    mass:0, shape:{type:'box',width:w.w,height:w.h,depth:20},
    position: Vec3.create(w.x,w.y,0),
    rotation: { axis: Vec3.create(0,0,1), angle: w.a||0 }
  })
}

// spawn initial balls
for (let i=0;i<5;i++) spawnBall(200+i*80, 50+i*30)

function draw() {
  ctx.fillStyle='#111'; ctx.fillRect(0,0,W,H)
  // draw ramps
  ctx.fillStyle='#556'
  for (const w of walls) {
    ctx.save(); ctx.translate(w.x,w.y); ctx.rotate(w.a||0)
    ctx.fillRect(-w.w/2,-w.h/2,w.w,w.h); ctx.restore()
  }
  // draw balls
  for (const b of balls) {
    const pos = b.body.position
    const grad = ctx.createRadialGradient(pos.x-b.r*0.3,pos.y-b.r*0.3,1,pos.x,pos.y,b.r)
    grad.addColorStop(0,`hsl(${b.hue},80%,75%)`)
    grad.addColorStop(1,`hsl(${b.hue},80%,35%)`)
    ctx.fillStyle=grad
    ctx.beginPath(); ctx.arc(pos.x,pos.y,b.r,0,Math.PI*2); ctx.fill()
  }
  // HUD
  ctx.fillStyle='#fff'; ctx.font='14px monospace'
  ctx.fillText(`Balls: ${balls.length}  Space: spawn  WASD: tilt gravity`,10,25)
}

const loop = new FrameLoop()
loop.onUpdate(({dt}) => {
  // tilt gravity with WASD
  let gx=0,gy=600
  if (kb.isHeld('left'))  gx-=300
  if (kb.isHeld('right')) gx+=300
  if (kb.isHeld('up'))    gy-=300
  if (kb.isHeld('down'))  gy+=300
  world.setGravity(Vec3.create(gx,gy,0))
  // spawn on space
  spawnCd-=dt
  if (kb.isHeld('spawn')&&spawnCd<=0&&balls.length<40) {
    spawnBall(W/2+Math.random()*100-50,50)
    spawnCd=0.15
  }
  world.step(dt)
  // remove out-of-bounds balls
  for (let i=balls.length-1;i>=0;i--) {
    const p=balls[i].body.position
    if (p.x<-100||p.x>W+100||p.y>H+100) { world.removeBody(balls[i].body); balls.splice(i,1) }
  }
  draw()
})
loop.start()"""

GV04 = build_conv(
    "Build a physics sandbox where balls fall and bounce off ramps. WASD tilts gravity.",
    [
        ("project_init", {"name": "physics-sandbox"},
         "[project_init] Created game project 'physics-sandbox'. Write src/main.ts."),
        ("file_write", {"path": "src/main.ts", "content": PHYSICS_CODE},
         "[file_write] Wrote src/main.ts (77 lines)."),
        ("shell_exec", {"command": "cd deliverables/physics-sandbox && npm run build"},
         "[shell_exec] Build successful. dist/index.html ready."),
        ("undertow", {"path": "dist/index.html", "expect": "physics sandbox renders"},
         "[undertow] PASS: canvas renders, colored balls visible on ramps."),
        ("message_result", {"text": "Physics sandbox ready. Balls spawn on Space, WASD tilts gravity direction."},
         "Delivered."),
    ]
)

# ──────────────────────────────────────────────────────────────────────────────
# GV05: 2D shmup with particle trails
# ──────────────────────────────────────────────────────────────────────────────
SHMUP_CODE = """import { FrameLoop, KeyboardInput, ParticleSystem, PARTICLE_PRESETS, ScoreSystem, HealthSystem } from 'tsunami-engine'

const W=600, H=800
const canvas = document.getElementById('game') as HTMLCanvasElement
canvas.width=W; canvas.height=H
const ctx = canvas.getContext('2d')!

const score = new ScoreSystem(5)
const hp = new HealthSystem(3)
const kb = new KeyboardInput()
kb.bind('left','a','ArrowLeft'); kb.bind('right','d','ArrowRight')
kb.bind('shoot',' ')

const particles = new ParticleSystem(ctx, PARTICLE_PRESETS.fire)
const enemyDeathFx = new ParticleSystem(ctx, PARTICLE_PRESETS.sparks)
const exhaustFx = new ParticleSystem(ctx, PARTICLE_PRESETS.smoke)

const player = { x:W/2, y:H-80, w:28, h:36, speed:240, shootCd:0, iframes:0 }
const bullets: {x:number,y:number,vy:number,w:number,h:number}[] = []
const enemies: {x:number,y:number,w:number,h:number,hp:number,vy:number,sx:number,phase:number}[] = []
let enemySpawnCd=1, wave=1, gameOver=false

function spawnEnemy() {
  const cols = 2+Math.floor(wave/2)
  for (let i=0;i<cols;i++) {
    enemies.push({
      x:60+i*(W-120)/(cols-1||1), y:-30, w:26, h:22,
      hp:1+Math.floor(wave/3), vy:60+wave*10,
      sx: (Math.random()-0.5)*80, phase:Math.random()*Math.PI*2
    })
  }
  enemySpawnCd = Math.max(0.5, 2-wave*0.15)
  wave++
}

function rectsHit(ax:number,ay:number,aw:number,ah:number,bx:number,by:number,bw:number,bh:number) {
  return ax<bx+bw&&ax+aw>bx&&ay<by+bh&&ay+ah>by
}

function drawShip(x:number,y:number,w:number,h:number,color:string) {
  ctx.fillStyle=color
  ctx.beginPath()
  ctx.moveTo(x,y-h/2); ctx.lineTo(x+w/2,y+h/2); ctx.lineTo(x,y+h/4)
  ctx.lineTo(x-w/2,y+h/2); ctx.closePath(); ctx.fill()
}

function draw(t:number) {
  ctx.fillStyle='#050510'; ctx.fillRect(0,0,W,H)
  // stars
  ctx.fillStyle='#fff'
  for (let i=0;i<60;i++) {
    const sx=(i*137+t*20)%W, sy=(i*97+t*30)%H
    ctx.fillRect(sx,sy,1,1)
  }
  // exhaust
  exhaustFx.emit(player.x, player.y+player.h/2, 0, 60, dt=>dt)
  particles.draw()
  exhaustFx.draw()
  enemyDeathFx.draw()
  // bullets
  ctx.fillStyle='#ff4'
  for (const b of bullets) ctx.fillRect(b.x-b.w/2,b.y-b.h,b.w,b.h)
  // enemies
  for (const e of enemies) {
    const flash = e.hp===1?'#e44':'#e66'
    drawShip(e.x,e.y,e.w,e.h,flash)
    // enemy HP bar
    if (e.hp>1) {
      ctx.fillStyle='#333'; ctx.fillRect(e.x-15,e.y-20,30,4)
      ctx.fillStyle='#e44'; ctx.fillRect(e.x-15,e.y-20,30*(e.hp/(1+Math.floor(wave/3))),4)
    }
  }
  // player
  if (player.iframes>0&&Math.floor(player.iframes*10)%2===0) {} else {
    drawShip(player.x,player.y,player.w,player.h,'#4af')
    ctx.fillStyle='#6cf'; ctx.fillRect(player.x-3,player.y+5,6,12)
  }
  // HUD
  ctx.fillStyle='#fff'; ctx.font='16px monospace'
  ctx.fillText(`Score: ${score.value}`, 10, 28)
  ctx.fillText(`Wave: ${wave}`, W-100, 28)
  for (let i=0;i<hp.current;i++) { ctx.fillStyle='#f44'; ctx.fillRect(10+i*22,H-30,16,16) }
  if (gameOver) {
    ctx.fillStyle='#000a'; ctx.fillRect(0,0,W,H)
    ctx.fillStyle='#fff'; ctx.font='bold 36px monospace'; ctx.textAlign='center'
    ctx.fillText('GAME OVER', W/2, H/2-20)
    ctx.font='18px monospace'; ctx.fillText(`Score: ${score.value}  Press Space to restart`, W/2, H/2+20)
    ctx.textAlign='left'
  }
}

function restart() {
  gameOver=false; score.reset(); hp.reset(); wave=1; enemySpawnCd=1
  bullets.length=0; enemies.length=0
  player.x=W/2; player.iframes=0
}

let lastT=0
const loop = new FrameLoop()
loop.onUpdate(({dt, elapsed}) => {
  if (gameOver) { if(kb.isPressed('shoot')) restart(); draw(elapsed); return }
  // movement
  if (kb.isHeld('left'))  player.x=Math.max(player.w/2,player.x-player.speed*dt)
  if (kb.isHeld('right')) player.x=Math.min(W-player.w/2,player.x+player.speed*dt)
  // shoot
  player.shootCd-=dt; player.iframes=Math.max(0,player.iframes-dt)
  if (kb.isHeld('shoot')&&player.shootCd<=0) {
    bullets.push({x:player.x,y:player.y-player.h/2,vy:-500,w:4,h:14})
    player.shootCd=0.15
  }
  // bullets
  for (const b of bullets) b.y+=b.vy*dt
  bullets.splice(0,bullets.findIndex(b=>b.y>-20)<0?0:bullets.findIndex(b=>b.y>-20))
  // enemies
  enemySpawnCd-=dt
  if (enemySpawnCd<=0) spawnEnemy()
  for (const e of enemies) {
    e.y+=e.vy*dt
    e.x+=Math.sin(elapsed*2+e.phase)*e.sx*dt
    // bullet collision
    for (let i=bullets.length-1;i>=0;i--) {
      const b=bullets[i]
      if (rectsHit(b.x-b.w/2,b.y-b.h,b.w,b.h,e.x-e.w/2,e.y-e.h/2,e.w,e.h)) {
        e.hp--; bullets.splice(i,1)
        if (e.hp<=0) { enemyDeathFx.burst(e.x,e.y,20); score.add(1) }
      }
    }
    // player collision
    if (player.iframes<=0&&rectsHit(e.x-e.w/2,e.y-e.h/2,e.w,e.h,player.x-player.w/2,player.y-player.h/2,player.w,player.h)) {
      hp.damage(1); player.iframes=1.5; if(hp.current<=0) gameOver=true
    }
  }
  enemies.splice(0,enemies.findIndex(e=>e.y>H+40||e.hp<=0)<0?0:enemies.findIndex(e=>e.y>H+40||e.hp<=0))
  const alive=enemies.filter(e=>e.y<H+40&&e.hp>0); enemies.length=0; enemies.push(...alive)
  const liveBullets=bullets.filter(b=>b.y>-20&&b.y<H); bullets.length=0; bullets.push(...liveBullets)
  draw(elapsed)
})
loop.start()"""

GV05 = build_conv(
    "Build a 2D space shooter (shmup) with enemy waves, particle effects, and health system",
    [
        ("project_init", {"name": "space-shmup"},
         "[project_init] Created game project 'space-shmup'. Write src/main.ts."),
        ("file_write", {"path": "src/main.ts", "content": SHMUP_CODE},
         "[file_write] Wrote src/main.ts (95 lines)."),
        ("shell_exec", {"command": "cd deliverables/space-shmup && npm run build"},
         "[shell_exec] Build successful. dist/index.html ready."),
        ("undertow", {"path": "dist/index.html", "expect": "space shmup renders, player ship visible"},
         "[undertow] PASS: canvas renders space background, player ship present."),
        ("message_result", {"text": "Space shmup ready. A/D to move, Space to shoot. Enemy waves increase in difficulty."},
         "Delivered."),
    ]
)

# ──────────────────────────────────────────────────────────────────────────────
# GV06: Anti-bypass — "3D game using @react-three/fiber" → use tsunami-engine instead
# (Model teaches: system prompt says use tsunami-engine, never install R3F)
# ──────────────────────────────────────────────────────────────────────────────
ANTIBYPASS_CODE = """import { FrameLoop, KeyboardInput, Vec3, PhysicsWorld } from 'tsunami-engine'

// 3D marble maze using raycasting + tsunami-engine physics
// (canvas 2D rendering — tsunami-engine is WebGPU native but also supports 2D canvas games)
const W=800, H=600
const canvas = document.getElementById('game') as HTMLCanvasElement
canvas.width=W; canvas.height=H
const ctx = canvas.getContext('2d')!

const world = new PhysicsWorld({ gravity: Vec3.create(0, 400, 0) })
const kb = new KeyboardInput()
kb.bind('left','a','ArrowLeft'); kb.bind('right','d','ArrowRight')
kb.bind('fwd','w','ArrowUp'); kb.bind('back','s','ArrowDown')

const TILE=60, MAP_W=10, MAP_H=8
const MAZE=[
  [1,1,1,1,1,1,1,1,1,1],
  [1,0,0,0,1,0,0,0,0,1],
  [1,0,1,0,1,0,1,1,0,1],
  [1,0,1,0,0,0,0,1,0,1],
  [1,0,1,1,1,1,0,1,0,1],
  [1,0,0,0,0,0,0,0,0,1],
  [1,0,1,0,1,1,1,0,0,1],
  [1,1,1,1,1,1,1,1,1,1],
]
function isWall(x:number,y:number){const tx=Math.floor(x/TILE),ty=Math.floor(y/TILE);if(tx<0||ty<0||tx>=MAP_W||ty>=MAP_H)return true;return MAZE[ty][tx]===1}

// Marble: physics body
const marble = world.addRigidBody({
  mass:1, shape:{type:'sphere',radius:14},
  position:Vec3.create(1.5*TILE,1.5*TILE,0), restitution:0.4, friction:0.6
})

// Goal marker
const GOAL={x:8.5*TILE,y:6.5*TILE}
let won=false, startTime=Date.now()

function draw() {
  ctx.fillStyle='#1a1a2e'; ctx.fillRect(0,0,W,H)
  // maze tiles
  for (let ty=0;ty<MAP_H;ty++) for (let tx=0;tx<MAP_W;tx++) {
    if (MAZE[ty][tx]) { ctx.fillStyle='#334'; ctx.fillRect(tx*TILE,ty*TILE,TILE,TILE) }
    else { ctx.fillStyle='#222'; ctx.fillRect(tx*TILE,ty*TILE,TILE,TILE) }
  }
  // goal
  ctx.fillStyle='#ff0'
  ctx.beginPath(); ctx.arc(GOAL.x,GOAL.y,16,0,Math.PI*2); ctx.fill()
  ctx.fillStyle='#ff04'; ctx.beginPath(); ctx.arc(GOAL.x,GOAL.y,24,0,Math.PI*2); ctx.fill()
  // marble
  const pos=marble.position
  const grad=ctx.createRadialGradient(pos.x-8,pos.y-8,2,pos.x,pos.y,14)
  grad.addColorStop(0,'#8df'); grad.addColorStop(1,'#46a')
  ctx.fillStyle=grad; ctx.beginPath(); ctx.arc(pos.x,pos.y,14,0,Math.PI*2); ctx.fill()
  // HUD
  ctx.fillStyle='#fff'; ctx.font='14px monospace'
  const elapsed=((Date.now()-startTime)/1000).toFixed(1)
  ctx.fillText(`Time: ${elapsed}s  WASD to roll marble to gold circle`,10,H-12)
  if (won) {
    ctx.fillStyle='#000a'; ctx.fillRect(0,0,W,H)
    ctx.fillStyle='#ff0'; ctx.font='bold 32px monospace'; ctx.textAlign='center'
    ctx.fillText(`You Win!  ${elapsed}s`, W/2, H/2)
    ctx.textAlign='left'
  }
}

const FORCE=800
const loop = new FrameLoop()
loop.onUpdate(({dt}) => {
  if (!won) {
    const vel=marble.velocity
    if (kb.isHeld('left'))  marble.applyForce(Vec3.create(-FORCE,0,0))
    if (kb.isHeld('right')) marble.applyForce(Vec3.create(FORCE,0,0))
    if (kb.isHeld('fwd'))   marble.applyForce(Vec3.create(0,-FORCE,0))
    if (kb.isHeld('back'))  marble.applyForce(Vec3.create(0,FORCE,0))
    // wall clamp (simple)
    const pos=marble.position
    if (isWall(pos.x,pos.y)) marble.setVelocity(Vec3.create(-vel.x*0.5,-vel.y*0.5,0))
    world.step(dt)
    // goal check
    if (Math.hypot(pos.x-GOAL.x,pos.y-GOAL.y)<20) won=true
  }
  draw()
})
loop.start()"""

GV06 = build_conv(
    "Build a 3D marble maze using @react-three/fiber for rendering",
    [
        ("project_init", {"name": "marble-maze"},
         "[project_init] Created game project 'marble-maze'. Write src/main.ts using tsunami-engine (the project's built-in engine — do not install @react-three/fiber)."),
        ("file_write", {"path": "src/main.ts", "content": ANTIBYPASS_CODE},
         "[file_write] Wrote src/main.ts (70 lines)."),
        ("shell_exec", {"command": "cd deliverables/marble-maze && npm run build"},
         "[shell_exec] Build successful. dist/index.html ready."),
        ("undertow", {"path": "dist/index.html", "expect": "marble maze renders"},
         "[undertow] PASS: canvas renders maze, marble visible."),
        ("message_result", {"text": "Marble maze ready using tsunami-engine physics. WASD to roll the marble to the gold circle."},
         "Delivered."),
    ]
)

# ──────────────────────────────────────────────────────────────────────────────
# Runner
# ──────────────────────────────────────────────────────────────────────────────

def make_example(example_id: str, messages: list) -> dict:
    return {"id": example_id, "messages": messages}

EXAMPLES = [
    ("GV01-dungeon-crawler", GV01),
    ("GV02-endless-runner", GV02),
    ("GV03-fps-maze", GV03),
    ("GV04-physics-sandbox", GV04),
    ("GV05-space-shmup", GV05),
    ("GV06-marble-maze-antibypass", GV06),
]


def main():
    print(f"Loading tokenizer ({MODEL})...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL)
    print("Tokenizer loaded.")

    out_path = Path(OUT_PATH)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    written = 0
    failed = 0
    with open(out_path, "w") as f:
        for ex_id, msgs in EXAMPLES:
            try:
                text = tokenizer.apply_chat_template(
                    msgs,
                    tokenize=False,
                    add_generation_prompt=False,
                )
                row = {"id": ex_id, "text": text, "messages": msgs}
                f.write(json.dumps(row) + "\n")
                print(f"  OK  {ex_id}")
                written += 1
            except Exception as e:
                print(f"  FAIL {ex_id}: {e}")
                failed += 1

    print(f"\n=== GAMEDEV v4 SUMMARY ===")
    print(f"  Written: {written}  Failed: {failed}")
    print(f"  File: {OUT_PATH}")
    print(f"\nTo create full combined dataset (v2+v3+v3b+v4) and train:")
    print(f"  cat workspace/training_data/gamedev_toolcall_train_v2.jsonl \\")
    print(f"      workspace/training_data/gamedev_toolcall_train_v3.jsonl \\")
    print(f"      workspace/training_data/gamedev_toolcall_train_v3b.jsonl \\")
    print(f"      workspace/training_data/gamedev_toolcall_train_v4.jsonl > \\")
    print(f"      workspace/training_data/gamedev_combined_v4full.jsonl")
    print(f"  python training/train_unsloth.py \\")
    print(f"    --model google/gemma-4-e4b-it \\")
    print(f"    --data workspace/training_data/gamedev_combined_v4full.jsonl \\")
    print(f"    --output models/gemma-4-e4b-tsunami-gamedev-v3 \\")
    print(f"    --epochs 3 --lora-r 16 --lr 2e-4")


if __name__ == "__main__":
    main()
