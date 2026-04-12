#!/usr/bin/env python3
"""Gamedev training data v3b — tsunami-engine imports + graceful degradation.

Targets:
  GX01: "Build multiplayer game" → degrade to single-player, project_init
  GX02: "Build 3D WebGPU game" → degrade to 2D canvas version, project_init
  + tsunami-engine import variants (parallel to @engine/ in v3)
  + GER06: Missing FrameLoop in training (a module path variant)

Usage:
  python training/build_gamedev_v3b.py
  Output: workspace/training_data/gamedev_toolcall_train_v3b.jsonl
"""
import json
from pathlib import Path
from transformers import AutoTokenizer

MODEL = "google/gemma-4-e4b-it"
OUT_PATH = "workspace/training_data/gamedev_toolcall_train_v3b.jsonl"

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
- After project_init succeeds: ALWAYS call file_write next. Never text-respond.
- Multiplayer requires server infrastructure — build single-player first, note the limitation.
- 3D/WebGPU requires advanced rendering — build 2D canvas version first, note the limitation.
"""

TOOLS = [
    {"type": "function", "function": {
        "name": "project_init", "description": "Create a game project.",
        "parameters": {"type": "OBJECT", "properties": {"name": {"type": "STRING"}}, "required": ["name"]},
    }},
    {"type": "function", "function": {
        "name": "file_write", "description": "Create or overwrite a file.",
        "parameters": {"type": "OBJECT", "properties": {
            "path": {"type": "STRING"}, "content": {"type": "STRING"},
        }, "required": ["path", "content"]},
    }},
    {"type": "function", "function": {
        "name": "file_edit", "description": "Make targeted modifications to a file.",
        "parameters": {"type": "OBJECT", "properties": {
            "path": {"type": "STRING"}, "old_text": {"type": "STRING"}, "new_text": {"type": "STRING"},
        }, "required": ["path", "old_text", "new_text"]},
    }},
    {"type": "function", "function": {
        "name": "shell_exec", "description": "Run a shell command.",
        "parameters": {"type": "OBJECT", "properties": {"command": {"type": "STRING"}}, "required": ["command"]},
    }},
    {"type": "function", "function": {
        "name": "undertow", "description": "QA -- screenshot test before delivery.",
        "parameters": {"type": "OBJECT", "properties": {
            "path": {"type": "STRING"}, "expect": {"type": "STRING"},
        }, "required": ["path"]},
    }},
    {"type": "function", "function": {
        "name": "message_result", "description": "Deliver final outcome.",
        "parameters": {"type": "OBJECT", "properties": {"text": {"type": "STRING"}}, "required": []},
    }},
    {"type": "function", "function": {
        "name": "message_chat", "description": "Talk to the user.",
        "parameters": {"type": "OBJECT", "properties": {
            "text": {"type": "STRING"}, "done": {"type": "BOOLEAN"},
        }, "required": ["text"]},
    }},
    {"type": "function", "function": {
        "name": "search_web", "description": "Search the web.",
        "parameters": {"type": "OBJECT", "properties": {"query": {"type": "STRING"}}, "required": ["query"]},
    }},
    {"type": "function", "function": {
        "name": "plan_update", "description": "Update the build plan.",
        "parameters": {"type": "OBJECT", "properties": {"plan": {"type": "STRING"}}, "required": ["plan"]},
    }},
]


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


# ── Tsunami-engine import variants ──────────────────────────────────────────
# Train on both tsunami-engine and @engine/ to normalize both styles

PONG_TE = """import { KeyboardInput, FrameLoop, ScoreSystem } from 'tsunami-engine'

const W = 600, H = 400, PADDLE_H = 80, BALL_R = 8
let p1y = H/2-PADDLE_H/2, p2y = H/2-PADDLE_H/2
let bx = W/2, by = H/2, vx = 220, vy = 140
let s1 = 0, s2 = 0

const keyboard = new KeyboardInput()
keyboard.bind()

const canvas = document.createElement('canvas')
canvas.width = W; canvas.height = H
document.body.appendChild(canvas)
const ctx = canvas.getContext('2d')!

const loop = new FrameLoop()
loop.onUpdate(({ dt }) => {
  if (keyboard.isHeld('KeyW')) p1y = Math.max(0, p1y - 380*dt)
  if (keyboard.isHeld('KeyS')) p1y = Math.min(H-PADDLE_H, p1y + 380*dt)
  if (keyboard.isHeld('ArrowUp')) p2y = Math.max(0, p2y - 380*dt)
  if (keyboard.isHeld('ArrowDown')) p2y = Math.min(H-PADDLE_H, p2y + 380*dt)
  bx += vx*dt; by += vy*dt
  if (by < BALL_R || by > H-BALL_R) vy *= -1
  if (bx < 20+BALL_R && by > p1y && by < p1y+PADDLE_H) vx = Math.abs(vx)
  if (bx > W-20-BALL_R && by > p2y && by < p2y+PADDLE_H) vx = -Math.abs(vx)
  if (bx < 0) { s2++; bx=W/2; by=H/2; vx=220; vy=140 }
  if (bx > W) { s1++; bx=W/2; by=H/2; vx=-220; vy=140 }
  ctx.fillStyle = '#1a1a2e'; ctx.fillRect(0,0,W,H)
  ctx.fillStyle = '#fff'
  ctx.fillRect(10, p1y, 12, PADDLE_H)
  ctx.fillRect(W-22, p2y, 12, PADDLE_H)
  ctx.beginPath(); ctx.arc(bx, by, BALL_R, 0, Math.PI*2); ctx.fill()
  ctx.font = '28px monospace'
  ctx.fillText(`${s1}   ${s2}`, W/2-40, 30)
})
loop.start()
"""

ASTEROIDS_TE = """import { KeyboardInput, FrameLoop, ScoreSystem } from 'tsunami-engine'

const W = 700, H = 500
type Asteroid = { x: number; y: number; vx: number; vy: number; r: number; angle: number }
type Bullet = { x: number; y: number; vx: number; vy: number; life: number }

let px = W/2, py = H/2, pa = 0, vx = 0, vy = 0
let asteroids: Asteroid[] = Array.from({length:5}, () => ({
  x: Math.random()<0.5 ? Math.random()*100 : W-Math.random()*100,
  y: Math.random()<0.5 ? Math.random()*100 : H-Math.random()*100,
  vx: (Math.random()-0.5)*100, vy: (Math.random()-0.5)*100,
  r: 30+Math.random()*20, angle: 0
}))
let bullets: Bullet[] = []
let shootTimer = 0
const score = new ScoreSystem()

const keyboard = new KeyboardInput()
keyboard.bind()
const canvas = document.createElement('canvas')
canvas.width = W; canvas.height = H
document.body.appendChild(canvas)
const ctx = canvas.getContext('2d')!

const loop = new FrameLoop()
loop.onUpdate(({ dt }) => {
  if (keyboard.isHeld('ArrowLeft')) pa -= 3*dt
  if (keyboard.isHeld('ArrowRight')) pa += 3*dt
  if (keyboard.isHeld('ArrowUp')) { vx += Math.cos(pa)*200*dt; vy += Math.sin(pa)*200*dt }
  vx *= 0.99; vy *= 0.99
  px = (px+vx*dt+W)%W; py = (py+vy*dt+H)%H
  shootTimer -= dt
  if (keyboard.wasPressed('Space') && shootTimer < 0) {
    bullets.push({x:px,y:py,vx:Math.cos(pa)*500,vy:Math.sin(pa)*500,life:1.5})
    shootTimer = 0.15
  }
  bullets = bullets.filter(b=>{b.x+=b.vx*dt;b.y+=b.vy*dt;b.life-=dt;return b.life>0})
  for (const a of asteroids) { a.x=(a.x+a.vx*dt+W)%W; a.y=(a.y+a.vy*dt+H)%H; a.angle+=dt }
  const newAsteroids: Asteroid[] = []
  asteroids = asteroids.filter(a => {
    for (const b of bullets) {
      if (Math.hypot(b.x-a.x,b.y-a.y) < a.r) {
        b.life=0; score.add(10)
        if (a.r>15) { for(let i=0;i<2;i++) newAsteroids.push({x:a.x,y:a.y,vx:(Math.random()-0.5)*150,vy:(Math.random()-0.5)*150,r:a.r/2,angle:0}) }
        return false
      }
    }
    return true
  })
  asteroids.push(...newAsteroids)
  bullets = bullets.filter(b=>b.life>0)
  ctx.fillStyle='#0a0a1a'; ctx.fillRect(0,0,W,H)
  ctx.save(); ctx.translate(px,py); ctx.rotate(pa)
  ctx.strokeStyle='#0ff'; ctx.lineWidth=2; ctx.beginPath(); ctx.moveTo(15,0); ctx.lineTo(-10,8); ctx.lineTo(-10,-8); ctx.closePath(); ctx.stroke()
  ctx.restore()
  for (const a of asteroids) { ctx.save(); ctx.translate(a.x,a.y); ctx.rotate(a.angle); ctx.strokeStyle='#888'; ctx.lineWidth=2; ctx.beginPath(); ctx.arc(0,0,a.r,0,Math.PI*2); ctx.stroke(); ctx.restore() }
  bullets.forEach(b=>{ctx.fillStyle='#ff0';ctx.beginPath();ctx.arc(b.x,b.y,3,0,Math.PI*2);ctx.fill()})
  ctx.fillStyle='#fff'; ctx.font='16px monospace'; ctx.fillText('Score: '+score.total, 10, 25)
  if (asteroids.length===0) { ctx.fillStyle='#0f0'; ctx.font='32px monospace'; ctx.fillText('YOU WIN!',W/2-80,H/2) }
})
loop.start()
"""

BATTLE_ROYALE_2D = """import { KeyboardInput, FrameLoop, HealthSystem, ScoreSystem } from 'tsunami-engine'

// Single-player battle royale prototype — zone shrinks over time
const W = 800, H = 600
const ZONE_SHRINK_RATE = 0.5  // pixels/sec
type Enemy = { x: number; y: number; hp: number; angle: number }
type Bullet = { x: number; y: number; vx: number; vy: number; life: number; owner: 'player'|'enemy' }

let px = W/2, py = H/2, pAngle = 0
const health = new HealthSystem(100)
const score = new ScoreSystem()
let zoneX = 0, zoneY = 0, zoneW = W, zoneH = H
let enemies: Enemy[] = Array.from({length:8}, () => ({
  x: Math.random()*W, y: Math.random()*H, hp: 30,
  angle: Math.random()*Math.PI*2
}))
let bullets: Bullet[] = []
let shootTimer = 0, gameTime = 0

const keyboard = new KeyboardInput()
keyboard.bind()
const canvas = document.createElement('canvas')
canvas.width = W; canvas.height = H
document.body.appendChild(canvas)
const ctx = canvas.getContext('2d')!

canvas.addEventListener('mousemove', e => {
  pAngle = Math.atan2(e.offsetY - py, e.offsetX - px)
})
canvas.addEventListener('click', () => {
  if (shootTimer <= 0) {
    bullets.push({ x:px, y:py, vx:Math.cos(pAngle)*500, vy:Math.sin(pAngle)*500, life:1.2, owner:'player' })
    shootTimer = 0.2
  }
})

const loop = new FrameLoop()
loop.onUpdate(({ dt }) => {
  gameTime += dt; shootTimer -= dt
  if (keyboard.isHeld('KeyA') || keyboard.isHeld('ArrowLeft')) px -= 180*dt
  if (keyboard.isHeld('KeyD') || keyboard.isHeld('ArrowRight')) px += 180*dt
  if (keyboard.isHeld('KeyW') || keyboard.isHeld('ArrowUp')) py -= 180*dt
  if (keyboard.isHeld('KeyS') || keyboard.isHeld('ArrowDown')) py += 180*dt

  // Zone shrink
  zoneX += ZONE_SHRINK_RATE*dt; zoneY += ZONE_SHRINK_RATE*dt
  zoneW -= ZONE_SHRINK_RATE*2*dt; zoneH -= ZONE_SHRINK_RATE*2*dt
  if (px<zoneX||px>zoneX+zoneW||py<zoneY||py>zoneY+zoneH) health.damage(dt*10)

  // Enemy AI
  enemies.forEach(e => {
    const dx=px-e.x, dy=py-e.y, dist=Math.hypot(dx,dy)||1
    e.x+=dx/dist*60*dt; e.y+=dy/dist*60*dt; e.angle=Math.atan2(dy,dx)
    if (Math.random()<dt*0.5) bullets.push({x:e.x,y:e.y,vx:Math.cos(e.angle)*300,vy:Math.sin(e.angle)*300,life:1.5,owner:'enemy'})
  })

  bullets = bullets.filter(b => {
    b.x+=b.vx*dt; b.y+=b.vy*dt; b.life-=dt
    if (b.owner==='player') {
      enemies = enemies.filter(e => {
        if (Math.hypot(b.x-e.x,b.y-e.y)<16) { e.hp-=25; b.life=0; if(e.hp<=0)score.add(100); return e.hp>0 }
        return true
      })
    } else if (Math.hypot(b.x-px,b.y-py)<12) { health.damage(15); b.life=0 }
    return b.life>0
  })

  ctx.fillStyle='#1a2e1a'; ctx.fillRect(0,0,W,H)
  // Zone indicator
  ctx.strokeStyle='rgba(255,50,50,0.8)'; ctx.lineWidth=3
  ctx.strokeRect(zoneX,zoneY,zoneW,zoneH)
  // Entities
  enemies.forEach(e=>{ctx.fillStyle='#e74c3c';ctx.beginPath();ctx.arc(e.x,e.y,14,0,Math.PI*2);ctx.fill()})
  bullets.forEach(b=>{ctx.fillStyle=b.owner==='player'?'#f1c40f':'#e74c3c';ctx.beginPath();ctx.arc(b.x,b.y,4,0,Math.PI*2);ctx.fill()})
  ctx.fillStyle='#3498db'; ctx.beginPath(); ctx.arc(px,py,14,0,Math.PI*2); ctx.fill()
  ctx.strokeStyle='#fff'; ctx.lineWidth=2; ctx.beginPath(); ctx.moveTo(px,py); ctx.lineTo(px+Math.cos(pAngle)*20,py+Math.sin(pAngle)*20); ctx.stroke()
  // HUD
  ctx.fillStyle='#e74c3c'; ctx.fillRect(10,10,health.current*2,14)
  ctx.fillStyle='#fff'; ctx.font='14px monospace'
  ctx.fillText('HP:'+Math.floor(health.current)+'  Score:'+score.total+'  Enemies:'+enemies.length, 10, 40)
  if (health.current<=0) { ctx.fillStyle='rgba(0,0,0,0.7)'; ctx.fillRect(0,0,W,H); ctx.fillStyle='#e74c3c'; ctx.font='32px monospace'; ctx.fillText('ELIMINATED',W/2-120,H/2) }
  if (enemies.length===0) { ctx.fillStyle='rgba(0,0,0,0.7)'; ctx.fillRect(0,0,W,H); ctx.fillStyle='#2ecc71'; ctx.font='32px monospace'; ctx.fillText('#1 VICTORY!',W/2-110,H/2) }
})
loop.start()
"""

DUNGEON_3D_AS_2D = """import { KeyboardInput, FrameLoop, HealthSystem, ScoreSystem } from 'tsunami-engine'

// 2D top-down dungeon crawler (3D requires WebGPU — building Canvas 2D version)
const W = 640, H = 480, TILE = 32
type Tile = 0|1  // 0=floor, 1=wall
type Enemy = { x: number; y: number; hp: number; vx: number; vy: number }
type Item = { x: number; y: number; type: 'health'|'key'; collected: boolean }

// Procedural dungeon map
const ROWS = 15, COLS = 20
const map: Tile[][] = Array.from({length:ROWS}, () => Array(COLS).fill(1))
// Carve rooms
const rooms = [{x:1,y:1,w:6,h:5},{x:9,y:1,w:6,h:5},{x:1,y:8,w:6,h:5},{x:9,y:8,w:8,h:5}]
const corridors = [{x:7,y:3,w:2,h:1},{x:7,y:10,w:2,h:1},{x:3,y:6,w:1,h:2},{x:12,y:6,w:1,h:2}]
for (const r of [...rooms,...corridors]) for (let y=r.y;y<r.y+r.h;y++) for (let x=r.x;x<r.x+r.w;x++) map[y][x]=0

let px=2*TILE+TILE/2, py=2*TILE+TILE/2
const health=new HealthSystem(100); const score=new ScoreSystem()
const enemies: Enemy[] = [{x:10*TILE,y:2*TILE,hp:40,vx:0,vy:0},{x:12*TILE,y:10*TILE,hp:60,vx:0,vy:0},{x:3*TILE,y:10*TILE,hp:40,vx:0,vy:0}]
const items: Item[] = [{x:15*TILE,y:4*TILE,type:'health',collected:false},{x:4*TILE,y:10*TILE,type:'key',collected:false}]
let keys=0, attackTimer=0

const keyboard = new KeyboardInput()
keyboard.bind()
const canvas = document.createElement('canvas')
canvas.width = W; canvas.height = H
document.body.appendChild(canvas)
const ctx = canvas.getContext('2d')!

function solid(x:number,y:number){const tx=Math.floor(x/TILE),ty=Math.floor(y/TILE);return tx<0||ty<0||tx>=COLS||ty>=ROWS||map[ty][tx]===1}
function tryMove(ox:number,oy:number,dx:number,dy:number){if(!solid(ox+dx*16,oy)){return{x:ox+dx,y:oy}}; if(!solid(ox,oy+dy*16)){return{x:ox,y:oy+dy}}; return{x:ox,y:oy}}

const loop = new FrameLoop()
loop.onUpdate(({dt})=>{
  attackTimer-=dt
  let dx=0,dy=0
  if(keyboard.isHeld('ArrowLeft')||keyboard.isHeld('KeyA'))dx=-120*dt
  if(keyboard.isHeld('ArrowRight')||keyboard.isHeld('KeyD'))dx=120*dt
  if(keyboard.isHeld('ArrowUp')||keyboard.isHeld('KeyW'))dy=-120*dt
  if(keyboard.isHeld('ArrowDown')||keyboard.isHeld('KeyS'))dy=120*dt
  const m=tryMove(px,py,dx,dy); px=m.x; py=m.y

  enemies.forEach(e=>{
    const dx2=px-e.x,dy2=py-e.y,dist=Math.hypot(dx2,dy2)||1
    if(dist<200){e.vx=dx2/dist*60;e.vy=dy2/dist*60}else{e.vx*=0.9;e.vy*=0.9}
    const me=tryMove(e.x,e.y,e.vx*dt,e.vy*dt);e.x=me.x;e.y=me.y
    if(dist<24&&attackTimer<0){health.damage(8);attackTimer=0.8}
  })
  if(keyboard.wasPressed('Space')&&attackTimer<0){
    enemies.forEach(e=>{if(Math.hypot(e.x-px,e.y-py)<40){e.hp-=35;attackTimer=0.3;if(e.hp<=0)score.add(50)}})
  }
  items.forEach(item=>{if(!item.collected&&Math.hypot(item.x-px,item.y-py)<24){item.collected=true;if(item.type==='health')health.heal(30);else keys++}})

  // Camera offset
  const cx=Math.min(Math.max(px-W/2,0),COLS*TILE-W)
  const cy=Math.min(Math.max(py-H/2,0),ROWS*TILE-H)
  ctx.fillStyle='#111';ctx.fillRect(0,0,W,H)
  ctx.save();ctx.translate(-cx,-cy)
  map.forEach((row,r)=>row.forEach((t,c)=>{ctx.fillStyle=t?'#333':'#555';ctx.fillRect(c*TILE,r*TILE,TILE-1,TILE-1)}))
  items.forEach(item=>{if(!item.collected){ctx.fillStyle=item.type==='health'?'#e74c3c':'#f1c40f';ctx.beginPath();ctx.arc(item.x,item.y,10,0,Math.PI*2);ctx.fill()}})
  enemies.forEach(e=>{if(e.hp>0){ctx.fillStyle='#c0392b';ctx.fillRect(e.x-14,e.y-14,28,28);ctx.fillStyle='#e74c3c';ctx.fillRect(e.x-12,e.y-20,e.hp*24/60,4)}})
  ctx.fillStyle='#3498db';ctx.beginPath();ctx.arc(px,py,12,0,Math.PI*2);ctx.fill()
  ctx.restore()
  ctx.fillStyle='#e74c3c';ctx.fillRect(10,10,health.current*1.5,12)
  ctx.fillStyle='#fff';ctx.font='14px monospace';ctx.fillText('HP:'+Math.floor(health.current)+'  Score:'+score.total+'  Keys:'+keys,10,40)
})
loop.start()
"""

SPACE_INVADERS_TE = """import { KeyboardInput, FrameLoop, HealthSystem, ScoreSystem } from 'tsunami-engine'

const W = 600, H = 550
type Alien = { x: number; y: number; alive: boolean; row: number; col: number }
type Bullet = { x: number; y: number; speed: number; fromPlayer: boolean }

const COLS = 11, ROWS = 5
const aliens: Alien[] = []
for (let r = 0; r < ROWS; r++)
  for (let c = 0; c < COLS; c++)
    aliens.push({ x: 60 + c*50, y: 60 + r*40, alive: true, row: r, col: c })

let px = W/2, py = H-50, dir = 1, alienMoveTimer = 0, alienMoveInterval = 0.6
const bullets: Bullet[] = []
let shootTimer = 0, bossShootTimer = 2
const health = new HealthSystem(3)
const score = new ScoreSystem()
let wave = 1

const keyboard = new KeyboardInput()
keyboard.bind()
const canvas = document.createElement('canvas')
canvas.width = W; canvas.height = H
document.body.appendChild(canvas)
const ctx = canvas.getContext('2d')!

const COLORS = ['#ff4136','#ff851b','#f9c74f','#4cc9f0','#7209b7']

const loop = new FrameLoop()
loop.onUpdate(({ dt }) => {
  if (keyboard.isHeld('ArrowLeft')) px = Math.max(20, px - 280*dt)
  if (keyboard.isHeld('ArrowRight')) px = Math.min(W-20, px + 280*dt)
  shootTimer -= dt
  if (keyboard.wasPressed('Space') && shootTimer < 0) {
    bullets.push({ x:px, y:py-15, speed:-500, fromPlayer:true })
    shootTimer = 0.25
  }

  alienMoveTimer += dt
  if (alienMoveTimer >= alienMoveInterval) {
    alienMoveTimer = 0
    const alive = aliens.filter(a=>a.alive)
    const maxX = Math.max(...alive.map(a=>a.x)), minX = Math.min(...alive.map(a=>a.x))
    if ((dir>0&&maxX>W-40)||(dir<0&&minX<40)) { dir*=-1; alive.forEach(a=>a.y+=20) }
    alive.forEach(a=>a.x+=dir*20)
    alienMoveInterval = Math.max(0.1, 0.6*(alive.length/(COLS*ROWS)))
    // Enemy shoot
    const cols = [...new Set(alive.map(a=>a.col))]
    if (cols.length && Math.random()<0.3) {
      const col = cols[Math.floor(Math.random()*cols.length)]
      const shooter = alive.filter(a=>a.col===col).sort((a,b)=>b.y-a.y)[0]
      if (shooter) bullets.push({x:shooter.x,y:shooter.y+15,speed:300,fromPlayer:false})
    }
  }

  for (const b of bullets) {
    b.y += b.speed * dt
    if (b.fromPlayer) {
      for (const a of aliens) {
        if (a.alive && Math.abs(b.x-a.x)<18 && Math.abs(b.y-a.y)<14) { a.alive=false; b.speed=0; score.add(10+a.row*5); break }
      }
    } else if (Math.abs(b.x-px)<16 && Math.abs(b.y-py)<16) { health.damage(1); b.speed=0 }
  }
  bullets.splice(0, bullets.length, ...bullets.filter(b=>b.speed!==0&&b.y>0&&b.y<H))

  if (!aliens.some(a=>a.alive)) { wave++; aliens.forEach((a,i)=>{ a.alive=true; a.x=60+(i%COLS)*50; a.y=60+Math.floor(i/COLS)*40 }); alienMoveInterval=Math.max(0.1,0.6-wave*0.05) }

  ctx.fillStyle='#0a0a1a'; ctx.fillRect(0,0,W,H)
  aliens.forEach(a=>{ if(!a.alive)return; ctx.fillStyle=COLORS[a.row]; ctx.fillRect(a.x-16,a.y-10,32,20) })
  bullets.forEach(b=>{ ctx.fillStyle=b.fromPlayer?'#0f0':'#f00'; ctx.fillRect(b.x-2,b.y-8,4,16) })
  ctx.fillStyle='#4cc9f0'; ctx.fillRect(px-18,py-10,36,20)
  ctx.fillStyle='#fff'; ctx.font='16px monospace'; ctx.fillText('Score:'+score.total+' HP:'+health.current+' Wave:'+wave, 10, H-10)
})
loop.start()
"""


def examples():
    E = []

    # ── GX01: Multiplayer battle royale → single-player degrade ────────────────
    E.append(("GX01-battle-royale-degrade", "Build a multiplayer battle royale game in the browser", [
        ("project_init", {"name": "battle-royale"}, "Created project deliverables/battle-royale. Write src/main.ts. (Multiplayer requires server infrastructure — building single-player prototype first.)"),
        ("file_write", {"path": "deliverables/battle-royale/src/main.ts", "content": BATTLE_ROYALE_2D}, "Wrote src/main.ts"),
        ("shell_exec", {"command": "cd deliverables/battle-royale && npm run build"}, "vite built in 78ms"),
        ("undertow", {"path": "deliverables/battle-royale/dist/index.html", "expect": "battle royale game with shrinking zone"}, "QA passed: player visible, enemies present, zone shrinks"),
        ("message_result", {"text": "Battle royale prototype ready. Single-player mode: eliminate 8 enemies before the zone closes. WASD to move, mouse to aim, click to shoot. Full multiplayer requires WebSocket server infrastructure."}, "Delivered."),
    ]))

    # ── GX02: 3D WebGPU dungeon → 2D canvas degrade ────────────────────────────
    E.append(("GX02-webgpu-dungeon-degrade", "Build a 3D first-person dungeon crawler using WebGPU", [
        ("project_init", {"name": "dungeon-crawler"}, "Created project deliverables/dungeon-crawler. Write src/main.ts. (3D first-person requires WebGPU — building 2D top-down canvas version first.)"),
        ("file_write", {"path": "deliverables/dungeon-crawler/src/main.ts", "content": DUNGEON_3D_AS_2D}, "Wrote src/main.ts"),
        ("shell_exec", {"command": "cd deliverables/dungeon-crawler && npm run build"}, "vite built in 75ms"),
        ("undertow", {"path": "deliverables/dungeon-crawler/dist/index.html", "expect": "top-down dungeon crawler with rooms and enemies"}, "QA passed: dungeon map visible, player moves, enemies patrol"),
        ("message_result", {"text": "2D dungeon crawler ready. Procedurally generated dungeon with 4 rooms, 3 enemies, health pickups, and keys. Arrow keys/WASD to move, Space to attack. Note: 3D first-person rendering requires WebGPU — upgrading to 3D would need a different renderer."}, "Delivered."),
    ]))

    # ── Tsunami-engine import style variants ────────────────────────────────────
    # Train the model to use 'tsunami-engine' as a valid import style
    E.append(("TE-pong-tsunami-engine", "Build a pong game", [
        ("project_init", {"name": "pong"}, "Created project deliverables/pong. Write src/main.ts."),
        ("file_write", {"path": "deliverables/pong/src/main.ts", "content": PONG_TE}, "Wrote src/main.ts"),
        ("shell_exec", {"command": "cd deliverables/pong && npm run build"}, "vite built in 64ms"),
        ("undertow", {"path": "deliverables/pong/dist/index.html", "expect": "pong with two paddles and ball"}, "QA passed: paddles and ball visible, score counting"),
        ("message_result", {"text": "Pong ready. W/S for left paddle, Arrow Up/Down for right."}, "Delivered."),
    ]))

    E.append(("TE-asteroids-tsunami-engine", "Build an asteroids game", [
        ("project_init", {"name": "asteroids"}, "Created project deliverables/asteroids. Write src/main.ts."),
        ("file_write", {"path": "deliverables/asteroids/src/main.ts", "content": ASTEROIDS_TE}, "Wrote src/main.ts"),
        ("shell_exec", {"command": "cd deliverables/asteroids && npm run build"}, "vite built in 67ms"),
        ("undertow", {"path": "deliverables/asteroids/dist/index.html", "expect": "asteroids with ship rotation and splitting rocks"}, "QA passed: ship visible, asteroids orbiting, bullets working"),
        ("message_result", {"text": "Asteroids ready. Arrow keys to thrust/rotate, Space to shoot. Asteroids split when hit."}, "Delivered."),
    ]))

    E.append(("TE-space-invaders-tsunami-engine", "Build a space invaders game with multiple enemy waves", [
        ("project_init", {"name": "space-invaders"}, "Created project deliverables/space-invaders. Write src/main.ts."),
        ("file_write", {"path": "deliverables/space-invaders/src/main.ts", "content": SPACE_INVADERS_TE}, "Wrote src/main.ts"),
        ("shell_exec", {"command": "cd deliverables/space-invaders && npm run build"}, "vite built in 69ms"),
        ("undertow", {"path": "deliverables/space-invaders/dist/index.html", "expect": "alien grid, player ship, bullets"}, "QA passed: alien formation visible, player can shoot, enemies fire back"),
        ("message_result", {"text": "Space Invaders ready. Arrow keys to move, Space to shoot. Waves speed up as aliens are eliminated."}, "Delivered."),
    ]))

    # ── Mixed import recovery: tsunami-engine path error → file_edit ──────────
    # Model writes 'tsunami-engine/renderer' (sub-path) — fix to 'tsunami-engine'
    E.append(("TE-import-subpath-fix", "Build a tower defense game", [
        ("project_init", {"name": "tower-defense"}, "Created project deliverables/tower-defense"),
        ("file_write", {"path": "deliverables/tower-defense/src/main.ts", "content": "import { KeyboardInput } from 'tsunami-engine/input'\nimport { FrameLoop } from 'tsunami-engine/renderer'\nimport { ScoreSystem } from 'tsunami-engine/systems'\n// tower defense game..."}, "Wrote src/main.ts"),
        ("shell_exec", {"command": "cd deliverables/tower-defense && npm run build"}, "Error: Cannot resolve 'tsunami-engine/input'. Use 'tsunami-engine' (single import)."),
        ("file_edit", {"path": "deliverables/tower-defense/src/main.ts",
                       "old_text": "import { KeyboardInput } from 'tsunami-engine/input'\nimport { FrameLoop } from 'tsunami-engine/renderer'\nimport { ScoreSystem } from 'tsunami-engine/systems'",
                       "new_text": "import { KeyboardInput, FrameLoop, ScoreSystem } from 'tsunami-engine'"}, "OK"),
        ("shell_exec", {"command": "cd deliverables/tower-defense && npm run build"}, "vite built in 72ms"),
        ("undertow", {"path": "deliverables/tower-defense/dist/index.html", "expect": "tower defense game"}, "QA passed: game visible"),
        ("message_result", {"text": "Tower defense ready."}, "Delivered."),
    ]))

    return E


def main():
    print(f"Loading tokenizer ({MODEL})...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL)
    print("Tokenizer loaded.")

    out_path = Path(OUT_PATH)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    written = 0
    failed = 0
    with open(out_path, "w") as f:
        for label, user_prompt, turns in examples():
            msgs = build_conv(user_prompt, turns)
            try:
                text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
                f.write(json.dumps({"text": text, "source": label}) + "\n")
                written += 1
                print(f"  OK  {label}")
            except Exception as e:
                print(f"  ERR {label}: {e}")
                failed += 1

    print(f"\n=== GAMEDEV v3b SUMMARY ===")
    print(f"  Written: {written}  Failed: {failed}")
    print(f"  File: {OUT_PATH}")
    if written > 0:
        combo = "workspace/training_data/gamedev_combined_v3full.jsonl"
        print(f"\nTo create full combined dataset (v2+v3+v3b) and train:")
        print(f"  cat workspace/training_data/gamedev_toolcall_train_v2.jsonl \\")
        print(f"      workspace/training_data/gamedev_toolcall_train_v3.jsonl \\")
        print(f"      workspace/training_data/gamedev_toolcall_train_v3b.jsonl > \\")
        print(f"      {combo}")
        print(f"  python training/train_unsloth.py \\")
        print(f"    --model google/gemma-4-e4b-it \\")
        print(f"    --data {combo} \\")
        print(f"    --output models/gemma-4-e4b-tsunami-gamedev-v3 \\")
        print(f"    --epochs 3 --lora-r 16 --lr 2e-4")


if __name__ == "__main__":
    main()
