import { KeyboardInput } from '@engine/input/keyboard'
import { ScoreSystem } from '@engine/systems/score'
import { FrameLoop } from '@engine/renderer/frame'

const W = 800, H = 500
const GRAVITY = 800, JUMP_VEL = -380, MOVE_SPEED = 220
const PLAYER_W = 24, PLAYER_H = 32

interface Platform { x: number; y: number; w: number; h: number; color: string }
interface Coin { x: number; y: number; collected: boolean }

let px = 100, py = 300, vx = 0, vy = 0
let onGround = false, facing = 1
let cameraX = 0

const keyboard = new KeyboardInput()
keyboard.bind()
const score = new ScoreSystem()

// Level geometry
const platforms: Platform[] = [
  { x: 0, y: 450, w: 300, h: 50, color: '#4a5568' },
  { x: 250, y: 380, w: 120, h: 20, color: '#2d3748' },
  { x: 420, y: 320, w: 150, h: 20, color: '#2d3748' },
  { x: 600, y: 400, w: 200, h: 20, color: '#2d3748' },
  { x: 850, y: 350, w: 100, h: 20, color: '#2d3748' },
  { x: 1000, y: 280, w: 150, h: 20, color: '#2d3748' },
  { x: 1200, y: 450, w: 300, h: 50, color: '#4a5568' },
  { x: 1350, y: 350, w: 120, h: 20, color: '#2d3748' },
  { x: 1550, y: 280, w: 180, h: 20, color: '#2d3748' },
  { x: 1800, y: 380, w: 200, h: 20, color: '#2d3748' },
  { x: 2050, y: 450, w: 400, h: 50, color: '#22c55e' }, // goal
]

const coins: Coin[] = [
  { x: 280, y: 350, collected: false },
  { x: 470, y: 290, collected: false },
  { x: 680, y: 370, collected: false },
  { x: 880, y: 320, collected: false },
  { x: 1050, y: 250, collected: false },
  { x: 1400, y: 320, collected: false },
  { x: 1620, y: 250, collected: false },
  { x: 1880, y: 350, collected: false },
]

function restart() {
  px = 100; py = 300; vx = 0; vy = 0
  onGround = false; cameraX = 0
  score.reset()
  for (const c of coins) c.collected = false
}

const canvas = document.getElementById('game') as HTMLCanvasElement
canvas.width = W; canvas.height = H
Object.assign(canvas.style, { width: `${W}px`, height: `${H}px` })
const ctx = canvas.getContext('2d')!

function draw() {
  ctx.fillStyle = '#1a1a2e'
  ctx.fillRect(0, 0, W, H)

  ctx.save()
  ctx.translate(-cameraX, 0)

  // Platforms
  for (const p of platforms) {
    ctx.fillStyle = p.color
    ctx.fillRect(p.x, p.y, p.w, p.h)
  }

  // Coins
  for (const c of coins) {
    if (c.collected) continue
    ctx.fillStyle = '#fbbf24'
    ctx.beginPath()
    ctx.arc(c.x, c.y, 8, 0, Math.PI * 2)
    ctx.fill()
  }

  // Player
  ctx.fillStyle = '#4a9eff'
  ctx.fillRect(px, py, PLAYER_W, PLAYER_H)
  // Eyes
  ctx.fillStyle = '#fff'
  ctx.fillRect(px + (facing > 0 ? 14 : 4), py + 8, 4, 4)

  ctx.restore()

  // HUD
  ctx.font = '16px JetBrains Mono, monospace'
  ctx.fillStyle = '#fbbf24'
  ctx.fillText(`Coins: ${score.score}/${coins.length}`, 10, 24)

  if (score.score === coins.length) {
    ctx.textAlign = 'center'
    ctx.font = '28px JetBrains Mono, monospace'
    ctx.fillStyle = '#4ade80'
    ctx.fillText('LEVEL COMPLETE!', W / 2, H / 2)
    ctx.font = '14px JetBrains Mono, monospace'
    ctx.fillStyle = '#94a3b8'
    ctx.fillText('SPACE to restart', W / 2, H / 2 + 30)
    ctx.textAlign = 'left'
  }
}

const loop = new FrameLoop()
loop.onUpdate = (stats) => {
  const dt = stats.dt

  if (score.score === coins.length && keyboard.justPressed('Space')) { restart(); return }

  // Horizontal movement
  vx = 0
  if (keyboard.isDown('ArrowLeft') || keyboard.isDown('KeyA')) { vx = -MOVE_SPEED; facing = -1 }
  if (keyboard.isDown('ArrowRight') || keyboard.isDown('KeyD')) { vx = MOVE_SPEED; facing = 1 }

  // Jump
  if ((keyboard.justPressed('ArrowUp') || keyboard.justPressed('KeyW') || keyboard.justPressed('Space')) && onGround) {
    vy = JUMP_VEL
    onGround = false
  }

  // Gravity
  vy += GRAVITY * dt

  // Move X
  px += vx * dt
  for (const p of platforms) {
    if (px + PLAYER_W > p.x && px < p.x + p.w && py + PLAYER_H > p.y && py < p.y + p.h) {
      if (vx > 0) px = p.x - PLAYER_W
      else px = p.x + p.w
    }
  }

  // Move Y
  py += vy * dt
  onGround = false
  for (const p of platforms) {
    if (px + PLAYER_W > p.x && px < p.x + p.w && py + PLAYER_H > p.y && py < p.y + p.h) {
      if (vy > 0) { py = p.y - PLAYER_H; vy = 0; onGround = true }
      else { py = p.y + p.h; vy = 0 }
    }
  }

  // Fall death
  if (py > H + 100) { restart(); return }

  // Coin collection
  for (const c of coins) {
    if (c.collected) continue
    if (Math.hypot(px + PLAYER_W / 2 - c.x, py + PLAYER_H / 2 - c.y) < 20) {
      c.collected = true
      score.addKill()
    }
  }

  // Camera follow
  cameraX = Math.max(0, px - W / 3)

  score.update(dt)
  keyboard.update()
  draw()
}

loop.start()
