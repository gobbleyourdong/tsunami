import { KeyboardInput } from '@engine/input/keyboard'
import { ScoreSystem } from '@engine/systems/score'
import { FrameLoop } from '@engine/renderer/frame'

const W = 700, H = 400
const GROUND_Y = H - 60
const PLAYER_W = 30, PLAYER_H = 50
const GRAVITY = 1400, JUMP_VEL = -520, DUCK_H = 25
const SCROLL_SPEED_BASE = 280

interface Obstacle { x: number; w: number; h: number; y: number; type: 'low' | 'high' }

let px = 80, py = GROUND_Y - PLAYER_H, vy = 0
let onGround = true, ducking = false
let obstacles: Obstacle[] = []
let scrollSpeed = SCROLL_SPEED_BASE
let spawnTimer = 0, distance = 0
let alive = true

const keyboard = new KeyboardInput()
keyboard.bind()
const score = new ScoreSystem()

function spawnObstacle() {
  const type = Math.random() > 0.3 ? 'low' : 'high'
  if (type === 'low') {
    const h = 30 + Math.random() * 30
    obstacles.push({ x: W + 20, w: 20 + Math.random() * 20, h, y: GROUND_Y - h, type })
  } else {
    obstacles.push({ x: W + 20, w: 50 + Math.random() * 30, h: 20, y: GROUND_Y - PLAYER_H - 10, type })
  }
}

function restart() {
  py = GROUND_Y - PLAYER_H; vy = 0; onGround = true; ducking = false
  obstacles = []; scrollSpeed = SCROLL_SPEED_BASE; spawnTimer = 0; distance = 0
  alive = true; score.reset()
}

const canvas = document.getElementById('game') as HTMLCanvasElement
canvas.width = W; canvas.height = H
Object.assign(canvas.style, { width: `${W}px`, height: `${H}px` })
const ctx = canvas.getContext('2d')!

function draw() {
  // Sky
  ctx.fillStyle = '#1a1a2e'; ctx.fillRect(0, 0, W, GROUND_Y)
  // Ground
  ctx.fillStyle = '#2d3748'; ctx.fillRect(0, GROUND_Y, W, H - GROUND_Y)

  // Ground line detail
  ctx.strokeStyle = '#475569'; ctx.lineWidth = 1
  ctx.beginPath(); ctx.moveTo(0, GROUND_Y); ctx.lineTo(W, GROUND_Y); ctx.stroke()

  // Player
  const pH = ducking ? DUCK_H : PLAYER_H
  const pY = ducking ? GROUND_Y - DUCK_H : py
  ctx.fillStyle = '#4a9eff'
  ctx.fillRect(px, pY, PLAYER_W, pH)
  // Eye
  ctx.fillStyle = '#fff'
  ctx.fillRect(px + PLAYER_W - 8, pY + 6, 4, 4)

  // Obstacles
  for (const o of obstacles) {
    ctx.fillStyle = o.type === 'low' ? '#ef4444' : '#a855f7'
    ctx.fillRect(o.x, o.y, o.w, o.h)
  }

  // HUD
  ctx.font = '18px JetBrains Mono, monospace'; ctx.fillStyle = '#e2e8f0'
  ctx.fillText(`${Math.floor(distance)}m`, W / 2 - 30, 30)
  ctx.font = '12px JetBrains Mono, monospace'; ctx.fillStyle = '#94a3b8'
  ctx.fillText(`Speed: ${Math.floor(scrollSpeed)}`, 10, 24)

  if (!alive) {
    ctx.fillStyle = 'rgba(0,0,0,0.5)'; ctx.fillRect(0, 0, W, H)
    ctx.textAlign = 'center'; ctx.font = '28px JetBrains Mono, monospace'
    ctx.fillStyle = '#ef4444'; ctx.fillText('CRASHED', W / 2, H / 2 - 10)
    ctx.font = '14px JetBrains Mono, monospace'; ctx.fillStyle = '#94a3b8'
    ctx.fillText(`${Math.floor(distance)}m | SPACE to restart`, W / 2, H / 2 + 20)
    ctx.textAlign = 'left'
  }
}

const loop = new FrameLoop()
loop.onUpdate = (stats) => {
  const dt = stats.dt
  if (!alive) { if (keyboard.justPressed('Space')) restart(); keyboard.update(); draw(); return }

  distance += scrollSpeed * dt * 0.05
  scrollSpeed += dt * 8 // gradually speed up

  // Jump
  if ((keyboard.justPressed('Space') || keyboard.justPressed('ArrowUp') || keyboard.justPressed('KeyW')) && onGround) {
    vy = JUMP_VEL; onGround = false
  }

  // Duck
  ducking = keyboard.isDown('ArrowDown') || keyboard.isDown('KeyS')

  // Gravity
  if (!onGround) {
    vy += GRAVITY * dt
    py += vy * dt
    if (py >= GROUND_Y - PLAYER_H) { py = GROUND_Y - PLAYER_H; vy = 0; onGround = true }
  }

  // Spawn obstacles
  spawnTimer += dt
  const rate = Math.max(0.6, 1.8 - distance * 0.01)
  if (spawnTimer >= rate) { spawnTimer = 0; spawnObstacle() }

  // Move obstacles
  for (const o of obstacles) o.x -= scrollSpeed * dt

  // Score passed obstacles
  for (const o of obstacles) {
    if (o.x + o.w < px && o.x + o.w > px - scrollSpeed * dt) score.addKill()
  }
  obstacles = obstacles.filter(o => o.x + o.w > -10)

  // Collision
  const pH = ducking ? DUCK_H : PLAYER_H
  const pY = ducking ? GROUND_Y - DUCK_H : py
  for (const o of obstacles) {
    if (px + PLAYER_W > o.x && px < o.x + o.w && pY + pH > o.y && pY < o.y + o.h) {
      alive = false; break
    }
  }

  score.update(dt); keyboard.update(); draw()
}

loop.start()
